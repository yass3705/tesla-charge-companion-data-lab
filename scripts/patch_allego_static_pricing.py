#!/usr/bin/env python3
from pathlib import Path

TARGET = Path("scripts/allego_official.py")

HELPER = r'''
def static_country_pricing_block(url: str, country: str = "France") -> tuple[str, dict]:
    """Map one country to Allego's ordered static tariff blocks.

    Allego ships all tariff blocks in the source HTML while the browser UI hides
    them behind a country selector. The selector options and tariff blocks are in
    the same order, so this maps the selected country by index without relying on
    client-side JavaScript rendering.
    """
    status, raw = fetch(url)
    if status != 200:
        raise RuntimeError(f"Allego pricing: unexpected HTTP status {status}")

    selects = re.findall(r"<select\b[^>]*>.*?</select>", raw, flags=re.I | re.S)
    country_select = None
    for candidate in selects:
        ctext = norm(text_from_html(candidate))
        if "france" in ctext and "allemagne" in ctext and "pays-bas" in ctext:
            country_select = candidate
            break
    if country_select is None:
        raise RuntimeError("Allego pricing: country selector not found in official HTML")

    labels = []
    for option_html in re.findall(r"<option\b[^>]*>(.*?)</option>", country_select, flags=re.I | re.S):
        label = text_from_html(option_html).strip()
        nl = norm(label)
        if not label or "choisissez" in nl or "select" in nl:
            continue
        labels.append(label)

    country_index = next((i for i, label in enumerate(labels) if norm(label) == norm(country)), None)
    if country_index is None:
        raise RuntimeError(f"Allego pricing: {country} missing from country selector")

    ntext = norm(text_from_html(raw))
    marker = norm("Chargement ultra-rapide")
    starts = [m.start() for m in re.finditer(re.escape(marker), ntext)]
    if len(starts) != len(labels):
        raise RuntimeError(
            f"Allego pricing: tariff block count {len(starts)} differs from country option count {len(labels)}"
        )

    blocks = []
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

'''


def main() -> None:
    source = TARGET.read_text(encoding="utf-8")

    if "def static_country_pricing_block(" not in source:
        anchor = "\ndef parse_country_direct(text: str) -> dict:\n"
        if anchor not in source:
            raise SystemExit("parse_country_direct anchor missing")
        source = source.replace(anchor, "\n" + HELPER + "def parse_country_direct(text: str) -> dict:\n", 1)

    old = 'pricing_fr, pricing_render_meta = browser_select_country(SOURCES["pricing"], "France")'
    new = 'pricing_fr, pricing_render_meta = static_country_pricing_block(SOURCES["pricing"], "France")'
    if old in source:
        source = source.replace(old, new, 1)
    elif new not in source:
        raise SystemExit("Allego pricing selection call not found")

    source = source.replace(
        "# Browser selection is deliberate: Allego's pricing page contains multiple countries\n"
        "    # in the HTML, while only one country block is visible to a real user.\n",
        "# Allego publishes all country tariff blocks in static HTML; map France by the official selector order.\n",
        1,
    )

    TARGET.write_text(source, encoding="utf-8")


if __name__ == "__main__":
    main()
