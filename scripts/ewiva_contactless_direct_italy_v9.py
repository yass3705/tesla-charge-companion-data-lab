#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import json
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup

POS_LIST_URL = "https://ewiva.com/pos-elenco-siti/"
PRICE_URL = "https://ewiva.com/nuova-tariffa-agosto-2026/"
DIRECT_EUR_PER_KWH = 0.80
VALID_FROM = "2026-08-01"
USER_AGENT = "tesla-charge-companion-data-lab/ewiva-contactless-v9"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_gz(path: Path) -> dict[str, Any]:
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        value = json.load(fh)
    if not isinstance(value, dict):
        raise RuntimeError("expected object payload")
    return value


def save_gz(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
    path.write_bytes(gzip.compress(raw, compresslevel=9, mtime=0))


def norm(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode("ascii")
    text = text.casefold().replace("’", "'")
    text = re.sub(r"\b(via|viale|corso|piazza|strada|strada statale|strada provinciale|ss|sp)\b", " ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def street_core(value: Any) -> str:
    # Remove house-number-only tokens so harmless civico formatting differences do not break joins.
    return " ".join(t for t in norm(value).split() if not re.fullmatch(r"\d+[a-z]?", t))


def get(url: str) -> str:
    r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=45)
    r.raise_for_status()
    return r.text


def validate_current_price() -> None:
    html = get(PRICE_URL)
    text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True).replace(",", ".")
    if "0.80" not in text and "0,80" not in html:
        raise RuntimeError("current Ewiva official tariff page no longer confirms 0.80 EUR/kWh")
    if "1 agosto 2026" not in text.casefold() and "1° agosto 2026" not in text.casefold() and "1 august 2026" not in text.casefold():
        raise RuntimeError("current Ewiva official tariff page no longer confirms 2026-08-01 effective date")


def extract_pos_sites() -> list[dict[str, str]]:
    html = get(POS_LIST_URL)
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    # Current Ewiva page renders one city heading followed by the station address.
    for heading in soup.find_all(["h4", "h5", "h6"]):
        city = heading.get_text(" ", strip=True)
        if not city or len(city) > 120:
            continue
        next_text = ""
        node = heading
        for _ in range(5):
            node = node.find_next_sibling()
            if node is None:
                break
            candidate = node.get_text(" ", strip=True)
            if candidate and candidate.casefold() not in {"vai al sito", "go to site"}:
                next_text = candidate
                break
        if not next_text:
            # Some WordPress layouts wrap heading/address in nested cards rather than siblings.
            parent = heading.parent
            if parent:
                texts = [x.strip() for x in parent.stripped_strings if x.strip()]
                try:
                    idx = texts.index(city)
                except ValueError:
                    idx = -1
                for candidate in texts[idx + 1 : idx + 5] if idx >= 0 else []:
                    if candidate.casefold() not in {"vai al sito", "go to site"}:
                        next_text = candidate
                        break
        if not next_text:
            continue
        key = (norm(city), norm(next_text))
        if not key[0] or not key[1] or key in seen:
            continue
        # Exclude generic section headings accidentally captured as cities.
        if any(term in key[0] for term in ("dove trovo", "pagamento", "scopri", "region", "stazioni")):
            continue
        seen.add(key)
        rows.append({"city": city, "address": next_text})

    if len(rows) < 50:
        raise RuntimeError(f"Ewiva POS page parser found only {len(rows)} candidate sites")
    return rows


def station_matches(pos: dict[str, str], station: dict[str, Any]) -> bool:
    pc = norm(pos.get("city"))
    sc = norm(station.get("city"))
    if not pc or not sc:
        return False
    # The Ewiva heading may contain province in parentheses. City must still contain one another.
    if not (pc == sc or pc.startswith(sc + " ") or sc.startswith(pc + " ")):
        return False
    pa = street_core(pos.get("address"))
    sa = street_core(station.get("address"))
    if not pa or not sa:
        return False
    if pa == sa or pa in sa or sa in pa:
        return True
    p_tokens, s_tokens = set(pa.split()), set(sa.split())
    union = p_tokens | s_tokens
    return bool(union) and len(p_tokens & s_tokens) / len(union) >= 0.80


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pun", default="data/national/pun_italy_national.json.gz")
    ap.add_argument("--out", default="data/national/ewiva_contactless_direct_italy_candidate.json.gz")
    ap.add_argument("--report", default="data/reports/ewiva_contactless_direct_italy_report.json")
    args = ap.parse_args()

    validate_current_price()
    pos_sites = extract_pos_sites()
    pun = load_gz(Path(args.pun))
    stations = [s for s in pun.get("stations", []) if isinstance(s, dict)]
    evses = [e for e in pun.get("evses", []) if isinstance(e, dict)]

    ewiva_stations = [s for s in stations if str(s.get("partyId") or "").upper() == "EWI" or "ewiva" in str(s.get("operator") or "").casefold()]
    evses_by_station: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for e in evses:
        if str(e.get("partyId") or "").upper() == "EWI" or "ewiva" in str(e.get("operator") or "").casefold():
            evses_by_station[str(e.get("stationId") or "")].append(e)

    matched_station_ids: set[str] = set()
    ambiguous: list[dict[str, Any]] = []
    unmatched: list[dict[str, Any]] = []
    match_rows: list[dict[str, Any]] = []

    for pos in pos_sites:
        candidates = [s for s in ewiva_stations if station_matches(pos, s)]
        if len(candidates) == 1:
            station = candidates[0]
            sid = str(station.get("stationId") or "")
            matched_station_ids.add(sid)
            match_rows.append({
                "officialCity": pos["city"],
                "officialAddress": pos["address"],
                "stationId": sid,
                "punCity": station.get("city"),
                "punAddress": station.get("address"),
            })
        elif len(candidates) > 1:
            ambiguous.append({"official": pos, "stationIds": [s.get("stationId") for s in candidates]})
        else:
            unmatched.append(pos)

    entries: list[dict[str, Any]] = []
    for station in ewiva_stations:
        sid = str(station.get("stationId") or "")
        if sid not in matched_station_ids:
            continue
        for evse in evses_by_station.get(sid, []):
            eid = str(evse.get("evseId") or "")
            if not eid:
                continue
            entries.append({
                "evseId": eid,
                "stationId": sid,
                "operator": "Ewiva",
                "partyId": "EWI",
                "directTariff": {
                    "channel": "operator_direct",
                    "operator": "Ewiva",
                    "paymentMethod": "contactless_pos",
                    "currency": "EUR",
                    "energyEurPerKwh": DIRECT_EUR_PER_KWH,
                    "validFrom": VALID_FROM,
                    "rankable": True,
                    "eligibility": "official_ewiva_pos_enabled_site_exact_station_match",
                    "tariffSource": PRICE_URL,
                    "eligibilitySource": POS_LIST_URL,
                },
            })

    counts = {
        "officialPosSiteRows": len(pos_sites),
        "punEwivaStations": len(ewiva_stations),
        "matchedPosStations": len(matched_station_ids),
        "rankableDirectEvse": len(entries),
        "ambiguousOfficialSites": len(ambiguous),
        "unmatchedOfficialSites": len(unmatched),
    }
    payload = {
        "schemaVersion": "1.0.0",
        "dataset": "ewiva-contactless-direct-italy-candidate",
        "generatedAt": now_iso(),
        "country": "IT",
        "operator": "Ewiva",
        "partyId": "EWI",
        "price": {"eurPerKwh": DIRECT_EUR_PER_KWH, "validFrom": VALID_FROM},
        "sources": {"tariff": PRICE_URL, "eligibleSites": POS_LIST_URL},
        "rules": {
            "directOnlyOnOfficialPosEnabledSites": True,
            "unmatchedSitesFailClosed": True,
            "ambiguousSitesFailClosed": True,
            "neverExpandPriceToAllEwivaStations": True,
        },
        "counts": counts,
        "entries": entries,
    }
    save_gz(Path(args.out), payload)
    report = {
        "generatedAt": payload["generatedAt"],
        "counts": counts,
        "rules": payload["rules"],
        "matchSample": match_rows[:100],
        "unmatchedSample": unmatched[:100],
        "ambiguousSample": ambiguous[:50],
    }
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
