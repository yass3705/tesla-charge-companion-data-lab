#!/usr/bin/env python3
"""Extended Freshmile tariff parser layered on the strict direct collector.

This module keeps the exact station-ref + EVSE-custom_ref identity rules from
``freshmile_direct_tariffs.py`` and extends tariff semantics for:
- non-EUR currencies such as XPF (kept in native currency, never mislabeled EUR)
- progressive time tiers (kept structured but non-rankable until TCC supports them)

``validated`` means the source tariff was extracted and structurally understood.
``tccRankable`` is intentionally stricter and remains false for unsupported
currency/tier models.
"""
from __future__ import annotations

import re
from typing import Any

import freshmile_direct_tariffs as base

NUMBER = r"([0-9]+(?:[.,][0-9]+)?)"
CURRENCY_TOKEN = r"(€|EUR|XPF)"


def number(value: str) -> float:
    return float(value.replace(",", "."))


def normalized_currency(token: str | None, declared: str | None) -> str | None:
    if declared:
        return str(declared).upper()
    token = (token or "").upper()
    if token == "€":
        return "EUR"
    return token or None


def generic_amount(amount: float, currency: str | None, unit: str, billing: str | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {"amount": amount, "currency": currency, "unit": unit}
    if billing:
        out["billing"] = billing
    return out


def parse_extended(description: str | None, declared_currency: str | None) -> dict[str, Any]:
    raw = str(description or "")
    text = " ".join(raw.replace("\r", "\n").split())
    out: dict[str, Any] = {"raw": description}
    currency = normalized_currency(None, declared_currency)
    if not text:
        out["status"] = "missing"
        return out

    # Progressive French time tariff, e.g.:
    # Deux premières heures gratuites, puis 3 € par heure entamée pendant deux
    # heures, puis 5 € par heure entamée supplémentaire.
    tier = re.search(
        rf"deux\s+premi[eè]res\s+heures\s+gratuites?.*?"
        rf"{NUMBER}\s*{CURRENCY_TOKEN}\s*par\s+heure\s+entam[eé]e\s+pendant\s+deux\s+heures.*?"
        rf"{NUMBER}\s*{CURRENCY_TOKEN}\s*par\s+heure\s+entam[eé]e\s+suppl[eé]mentaire",
        text,
        re.I,
    )
    if tier:
        c1 = normalized_currency(tier.group(2), declared_currency)
        c2 = normalized_currency(tier.group(4), declared_currency)
        if c1 == c2:
            out["currency"] = c1
            out["timeTiers"] = [
                {"fromMinutes": 0, "untilMinutes": 120, "price": generic_amount(0.0, c1, "hour", "started_hour")},
                {"fromMinutes": 120, "untilMinutes": 240, "price": generic_amount(number(tier.group(1)), c1, "hour", "started_hour")},
                {"fromMinutes": 240, "untilMinutes": None, "price": generic_amount(number(tier.group(3)), c1, "hour", "started_hour")},
            ]
            out["status"] = "parsed_complex_tiers"
            out["sourceValidated"] = True
            out["tccModelSupported"] = False
            return out

    # Generic energy component, preserving native currency.
    energy = re.search(
        rf"(?:{CURRENCY_TOKEN}\s*)?{NUMBER}\s*(?:{CURRENCY_TOKEN})?\s*(?:/|per|par)\s*(?:started\s*)?kwh(?:\s*(?:started|entam[eé]e?))?",
        text,
        re.I,
    )
    if energy:
        prefix_cur, amount_s, suffix_cur = energy.group(1), energy.group(2), energy.group(3)
        component_currency = normalized_currency(prefix_cur or suffix_cur, declared_currency)
        out["energyPrice"] = generic_amount(number(amount_s), component_currency, "kWh", "started_kwh")
        if component_currency == "EUR":
            out["energyEurPerKwh"] = number(amount_s)
        currency = component_currency or currency

    # Generic time component. Convert hourly rates to a structured hourly unit;
    # only simple per-minute EUR gets the legacy convenience field.
    time_match = re.search(
        rf"(?:{CURRENCY_TOKEN}\s*)?{NUMBER}\s*(?:{CURRENCY_TOKEN})?\s*(?:/|per|par)\s*(?:started\s*)?(minute|min|heure|hour)s?(?:\s*entam[eé]e)?",
        text,
        re.I,
    )
    if time_match:
        prefix_cur, amount_s, suffix_cur, unit_token = time_match.groups()
        component_currency = normalized_currency(prefix_cur or suffix_cur, declared_currency)
        unit = "minute" if unit_token.lower() in {"minute", "min"} else "hour"
        billing = "started_minute" if unit == "minute" else "started_hour"
        out["timePrice"] = generic_amount(number(amount_s), component_currency, unit, billing)
        if component_currency == "EUR" and unit == "minute":
            out["timeEurPerMinute"] = number(amount_s)
        currency = component_currency or currency

    # Flat/session fee.
    session = re.search(
        rf"(?:{CURRENCY_TOKEN}\s*)?{NUMBER}\s*(?:{CURRENCY_TOKEN})?\s*(?:/|per|par)\s*(session|charge)",
        text,
        re.I,
    )
    if session:
        prefix_cur, amount_s, suffix_cur, _ = session.groups()
        component_currency = normalized_currency(prefix_cur or suffix_cur, declared_currency)
        out["sessionPrice"] = generic_amount(number(amount_s), component_currency, "session")
        if component_currency == "EUR":
            out["sessionFeeEur"] = number(amount_s)
        currency = component_currency or currency

    threshold = re.search(
        rf"(?:after|apr[eè]s)\s+{NUMBER}\s*(minutes?|mins?|hours?|hrs?|heures?|h)\b",
        text,
        re.I,
    )
    if threshold:
        threshold_minutes = base.duration_minutes(threshold.group(1), threshold.group(2))
        out["timeFeeStartsAfterMinutes"] = threshold_minutes

        flat = re.search(
            rf"(?:after|apr[eè]s)\s+{NUMBER}\s*(minutes?|mins?|hours?|hrs?|heures?|h)\b.{{0,120}}?"
            rf"(?:{CURRENCY_TOKEN}\s*)?{NUMBER}\s*(?:{CURRENCY_TOKEN})?\s*(?:flat\s*fee|fee\b|forfait)",
            text,
            re.I,
        )
        if flat:
            # groups: threshold number/unit, optional prefix currency, fee amount, optional suffix currency
            fee_currency = normalized_currency(flat.group(3) or flat.group(5), declared_currency)
            fee_amount = number(flat.group(4))
            out.pop("timeFeeStartsAfterMinutes", None)
            out["delayedFlatFee"] = {
                "afterMinutes": base.duration_minutes(flat.group(1), flat.group(2)),
                "price": generic_amount(fee_amount, fee_currency, "session"),
            }
            if fee_currency == "EUR":
                out["delayedFlatFee"]["amountEur"] = fee_amount
            currency = fee_currency or currency

    if re.search(
        r"continues as long as .*plugged|pricing continues as long as .*plugged|"
        r"facturation .* tant que .*branch|tarification .* tant que .*branch",
        text,
        re.I,
    ):
        out["continuesWhilePluggedIn"] = True

    understood = any(key in out for key in ("energyPrice", "timePrice", "sessionPrice", "delayedFlatFee"))
    out["currency"] = currency
    out["status"] = "parsed" if understood else "unparsed"
    out["sourceValidated"] = understood
    out["tccModelSupported"] = understood and currency == "EUR"
    return out


def tariff_from_connector(connector: dict[str, Any]) -> dict[str, Any] | None:
    tariff = connector.get("tariff")
    if not isinstance(tariff, dict):
        return None

    is_free = bool(tariff.get("is_free"))
    is_preferential = bool(tariff.get("is_preferential"))
    currency = tariff.get("currency")
    if is_free:
        components: dict[str, Any] = {
            "free": True,
            "status": "parsed",
            "currency": currency,
            "sourceValidated": True,
            "tccModelSupported": True,
        }
        source_validated = True
        tcc_model_supported = True
    else:
        components = parse_extended(tariff.get("description"), currency)
        source_validated = bool(components.get("sourceValidated"))
        tcc_model_supported = bool(components.get("tccModelSupported"))

    # Exact-source validation and TCC usability are intentionally separate.
    validated = source_validated and not is_preferential
    tcc_rankable = validated and tcc_model_supported and currency in {None, "EUR"}

    return {
        "tariffId": tariff.get("id"),
        "tariffRef": tariff.get("custom_ref") or tariff.get("origin_ref"),
        "name": tariff.get("name"),
        "currency": currency,
        "isFree": is_free,
        "isPreferential": is_preferential,
        "commissionedAt": tariff.get("commissioned_at"),
        "components": components,
        "provisionHold": base.money(tariff.get("provision")),
        "paymentAuthorizationHold": base.money(tariff.get("payment_authorization_amount")),
        "maxPrice": base.money(tariff.get("max_price")),
        "validated": validated,
        "sourceValidated": validated,
        "tccModelSupported": tcc_model_supported,
        "tccRankable": tcc_rankable,
        "source": "freshmile_public_driver_api",
        "connector": {
            "id": connector.get("id"),
            "powerKw": connector.get("power"),
            "standard": connector.get("standard"),
        },
    }


# Patch only parsing semantics. The strict location/EVSE identity logic and all
# network I/O remain in the audited base collector.
base.tariff_from_connector = tariff_from_connector


if __name__ == "__main__":
    base.main()
