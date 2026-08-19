#!/usr/bin/env python3
"""Run the Allego extractor with a static official-HTML country selector.

Allego's pricing page ships all country tariff blocks in its HTML source, while
its client-side UI may fail to render the selected block on a GitHub runner.
This wrapper maps the official country selector order to the ordered tariff
blocks and monkeypatches only the pricing-page country selection.
"""
from __future__ import annotations

import re

import allego_official as a


def static_country_pricing_block(url: str, country: str = "France") -> tuple[str, dict]:
    status, raw = a.fetch(url)
    if status != 200:
        raise RuntimeError(f"Allego pricing: unexpected HTTP status {status}")

    selects = re.findall(r"<select\b[^>]*>.*?</select>", raw, flags=re.I | re.S)
    country_select = None
    for candidate in selects:
        ctext = a.norm(a.text_from_html(candidate))
        if "france" in ctext and "allemagne" in ctext and "pays-bas" in ctext:
            country_select = candidate
            break
    if country_select is None:
        raise RuntimeError("Allego pricing: official country selector not found in static HTML")

    labels: list[str] = []
    for option_html in re.findall(r"<option\b[^>]*>(.*?)</option>", country_select, flags=re.I | re.S):
        label = a.text_from_html(option_html).strip()
        nl = a.norm(label)
        if not label or "choisissez" in nl or "select" in nl:
            continue
        labels.append(label)

    country_index = next((i for i, label in enumerate(labels) if a.norm(label) == a.norm(country)), None)
    if country_index is None:
        raise RuntimeError(f"Allego pricing: {country} missing from official selector")

    ntext = a.norm(a.text_from_html(raw))
    marker = a.norm("Chargement ultra-rapide")
    starts = [m.start() for m in re.finditer(re.escape(marker), ntext)]
    if len(starts) != len(labels):
        raise RuntimeError(
            f"Allego pricing: tariff block count {len(starts)} differs from country option count {len(labels)}"
        )

    blocks: list[str] = []
    for i, start in enumerate(starts):
        end = starts[i + 1] if i + 1 < len(starts) else len(ntext)
        blocks.append(ntext[start:end])

    block = blocks[country_index]
    if "kwh" not in block:
        raise RuntimeError(f"Allego pricing: mapped {country} block contains no kWh tariff")

    return block, {
        "accessMode": "official_static_html_country_index",
        "selectedCountry": labels[country_index],
        "countryIndex": country_index,
        "countryOptionCount": len(labels),
        "tariffBlockCount": len(starts),
    }


_original_browser_select_country = a.browser_select_country


def country_selector(url: str, country: str = "France") -> tuple[str, dict]:
    if url == a.SOURCES["pricing"]:
        return static_country_pricing_block(url, country)
    return _original_browser_select_country(url, country)


a.browser_select_country = country_selector

if __name__ == "__main__":
    a.main()
