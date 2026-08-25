#!/usr/bin/env python3
"""Build the fail-closed Freshmile direct tariff overlay used by TCC V8.

The input is the recovered national Freshmile CPO scan from data-lab. The
source scan's `tccRankable` flag is only a pre-filter: this builder applies a
stricter semantic gate and publishes only formulas TCC V8 can reproduce
without dropping a tariff clause.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MONEY_RE = re.compile(r"(?:€\s*([0-9]+(?:[.,][0-9]+)?)|([0-9]+(?:[.,][0-9]+)?)\s*€)", re.I)
SESSION_PATTERNS = [
    re.compile(r"([0-9]+(?:[.,][0-9]+)?)\s*€\s*(?:à|a)\s*la\s*connexion", re.I),
    re.compile(r"€\s*([0-9]+(?:[.,][0-9]+)?)\s*(?:upon|at|for)\s*(?:the\s*)?connection", re.I),
    re.compile(r"([0-9]+(?:[.,][0-9]+)?)\s*€\s*(?:upon|at|for)\s*(?:the\s*)?connection", re.I),
    re.compile(r"(?:forfait(?: de)?|flat rate of)\s*€?\s*([0-9]+(?:[.,][0-9]+)?)\s*€?\s*(?:par|per)\s*session", re.I),
    re.compile(r"([0-9]+(?:[.,][0-9]+)?)\s*€\s*(?:par|per)\s*session", re.I),
]
ENERGY_PATTERNS = [
    re.compile(r"(?:€\s*)?([0-9]+(?:[.,][0-9]+)?)\s*(?:€\s*)?(?:par|per|/)\s*kwh(?:\s*(entam[eé]|started|starded|used|consumed|delivered|or part thereof|ou partie))?", re.I),
]
TIME_MIN_PATTERNS = [
    re.compile(r"(?:€\s*)?([0-9]+(?:[.,][0-9]+)?)\s*(?:€\s*)?(?:par|per|/)\s*(?:(started)\s+)?minute(?:\s*(entam[eé]e?))?", re.I),
]
TIME_HOUR_BY_MIN_PATTERNS = [
    re.compile(r"([0-9]+(?:[.,][0-9]+)?)\s*€\s*(?:par|/)\s*heure\s*,?\s*factur[eé]s?\s*[aà]\s*la\s*minute", re.I),
    re.compile(r"€\s*([0-9]+(?:[.,][0-9]+)?)\s*(?:per|/)\s*hour\s*,?\s*billed\s*(?:by|per)\s*minute", re.I),
]
FORBIDDEN = [
    r"\b(?:de|from|entre|between)\s*\d{1,2}(?::\d{2}|h\d{0,2})?\s*(?:am|pm)?\s*(?:à|a|to|-)\s*\d{1,2}",
    r"\b(?:le reste du temps|rest of the time|daytime|nighttime|nuit|jour)\b",
    r"\b(?:par tranche|per block|every\s+\d+\s+minutes?|toutes? les\s+\d+\s+minutes?)\b",
    r"\b(?:moins de|between\s+\d+\s*(?:kw|kwh)|entre\s+\d+\s*(?:kw|kwh)|au-del[aà] de\s+\d+\s*kw)\b",
    r"\b(?:sans consommation|without (?:energy )?consumption)\b",
    r"\b(?:une fois la charge terminée|once (?:the )?vehicle is recharged|once charging is complete|after (?:the )?end of (?:the )?charge|from the end of the charge|après la fin de la charge)\b",
    r"\b(?:gratuit(?:e|es|s)?|free for|free minutes?|premi[eè]res?|first\s+\d+\s+(?:minutes?|hours?))\b",
    r"\b(?:plafond|cap(?:ped)?|minimum fee|minimum de facturation)\b",
    r"\b(?:suppl[eé]mentaire|additional)\b",
]
DELAY_WORD = re.compile(r"\b(?:apr[eè]s|after|au-del[aà]|beyond|[aà] partir de)\b", re.I)
PLAIN_HOUR = re.compile(r"(?:€\s*\d+(?:[.,]\d+)?|\d+(?:[.,]\d+)?\s*€)\s*(?:par|per|/)\s*(?:heure|hour)", re.I)


def norm(value: Any) -> str:
    text = str(value or "").replace("\r", " ").replace("\n", " ").replace("\u202f", " ").replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip().lower()


def amount(value: Any) -> float:
    return float(str(value).replace(",", "."))


def unique_matches(patterns: list[re.Pattern[str]], text: str) -> list[re.Match[str]]:
    matches: dict[tuple[int, int, str], re.Match[str]] = {}
    for pattern in patterns:
        for match in pattern.finditer(text):
            matches[(match.start(), match.end(), match.group(0))] = match
    return list(matches.values())


def parse_exact_tariff(tariff: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
    if not tariff.get("sourceValidated") or not tariff.get("tccRankable"):
        return None, "source_not_rankable"
    if tariff.get("isPreferential"):
        return None, "preferential"
    if tariff.get("currency") != "EUR":
        return None, "non_eur"
    components = tariff.get("components") or {}
    if components.get("status") != "parsed":
        return None, "not_parsed"

    raw = str(components.get("raw") or "").strip()
    text = norm(raw)
    if tariff.get("isFree"):
        if float((tariff.get("maxPrice") or {}).get("amount") or 0) != 0:
            return None, "free_with_nonzero_cap"
        return {"currency": "EUR", "free": True, "maxPriceEur": 0.0}, "accepted_free"
    if not raw:
        return None, "blank_nonfree"

    if re.search(r"termin|finished|complete|from the end of charg|end of charging|recharg|fini de charger", text, re.I):
        return None, "post_charge_fee_not_published"
    complex_cues = [
        r"\bfrom\s+\d", r"\bde\s+\d{1,2}(?:h|:)\d*", r"\bentre\s+\d", r"\bbetween\s+\d",
        r"\bafter\b", r"\bapr[eè]s\b", r"\b(?:a|à) partir d?[’']?\s*\d",
        r"\bfirst\s+(?:hour|minute)", r"\bpremi[eè]re?s?\s+(?:heure|minute)",
        r"\bsuppl[eé]ment\b", r"\badditional\b", r"\bnon[- ]?abonn", r"\bnon[- ]?subscriber",
        r"tarif pr[eé]f[eé]rentiel", r"preferential tariff", r"\bcentime",
    ]
    if any(re.search(pattern, text, re.I) for pattern in complex_cues):
        return None, "conditional_clause_not_published"
    for pattern in FORBIDDEN:
        if re.search(pattern, text, re.I):
            return None, "unsupported_condition"
    if DELAY_WORD.search(text):
        return None, "threshold_or_tier"

    session = unique_matches(SESSION_PATTERNS, text)
    energy = unique_matches(ENERGY_PATTERNS, text)
    time_min = unique_matches(TIME_MIN_PATTERNS, text)
    time_hour = unique_matches(TIME_HOUR_BY_MIN_PATTERNS, text)
    if len(session) > 1 or len(energy) > 1 or len(time_min) > 1 or len(time_hour) > 1:
        return None, "multiple_formula_components"
    if PLAIN_HOUR.search(text) and not time_hour:
        return None, "ambiguous_hour_billing"
    if not (session or energy or time_min or time_hour):
        return None, "no_supported_formula"

    exact: dict[str, Any] = {"currency": "EUR", "free": False}
    explained: list[float] = []
    if session:
        fee = amount(session[0].group(1)); exact["sessionFeeEur"] = fee; explained.append(fee)
    if energy:
        match = energy[0]; price = amount(match.group(1))
        billing = "started_kwh" if re.search(r"entam|started|starded|part thereof|ou partie", match.group(0), re.I) else "linear_kwh"
        exact["energy"] = {"amount": price, "billing": billing}; explained.append(price)
    if time_min:
        match = time_min[0]; price = amount(match.group(1))
        occupied_cues = (
            components.get("continuesWhilePluggedIn")
            or re.search(r"tarification continue tant|facturation continue tant|billing continues as long|pricing continues as long|charging continues as long|charge applies as long", text, re.I)
            or re.search(r"temps de branchement|dur[eé]e de branchement|temps de parking|connection time|duration of (?:the )?connection|parking time|time the vehicle is plugged", text, re.I)
        )
        exact["time"] = {"amount": price, "billing": "started_minute", "appliesTo": "occupied" if occupied_cues else "charge"}; explained.append(price)
    if time_hour:
        match = time_hour[0]; hourly = amount(match.group(1))
        occupied_cues = (
            components.get("continuesWhilePluggedIn")
            or re.search(r"tarification continue tant|facturation continue tant|billing continues as long|pricing continues as long|charging continues as long|charge applies as long", text, re.I)
            or re.search(r"temps de branchement|dur[eé]e de branchement|temps de parking|connection time|duration of (?:the )?connection|parking time|time the vehicle is plugged", text, re.I)
        )
        exact["time"] = {"amount": hourly / 60.0, "billing": "started_minute", "appliesTo": "occupied" if occupied_cues else "charge", "sourceHourlyAmount": hourly}; explained.append(hourly)

    source_money = sorted(round(amount(m.group(1) or m.group(2)), 6) for m in MONEY_RE.finditer(text))
    explained_money = sorted(round(value, 6) for value in explained)
    if source_money != explained_money:
        return None, "unaccounted_monetary_clause"
    max_price = (tariff.get("maxPrice") or {}).get("amount")
    if max_price is not None:
        try: max_price = float(max_price)
        except (TypeError, ValueError): max_price = None
        if max_price is not None and max_price > 0: exact["maxPriceEur"] = max_price
    exact["sourceDescription"] = raw
    exact["sourceDescriptionSha256"] = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return exact, "accepted"


def display_rule(exact: dict[str, Any]) -> dict[str, Any]:
    rule = {"scope":"allDay","start":"00:00","end":"24:00","billing":"kwh","currency":"EUR","pricePerKwh":0.0,"chargePerMinute":0.0,"connectionFee":float(exact.get("sessionFeeEur") or 0),"idlePerMinute":0.0,"afterMinutesRate":0.0,"afterMinutesThreshold":0.0,"afterMinutesCap":0.0,"afterMinutesCapStart":"00:00","afterMinutesCapEnd":"24:00"}
    if exact.get("free"): return rule
    energy = exact.get("energy") or {}; time = exact.get("time") or {}
    if energy: rule["pricePerKwh"] = float(energy["amount"])
    if time: rule["chargePerMinute"] = float(time["amount"])
    if not energy and time: rule["billing"] = "minute"
    return rule


def read_gzip(path: Path) -> dict[str, Any]:
    with gzip.open(path, "rt", encoding="utf-8") as handle: return json.load(handle)


def write_gzip(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    with gzip.GzipFile(filename="", mode="wb", fileobj=path.open("wb"), mtime=0) as gz: gz.write(raw)


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("input", type=Path); parser.add_argument("output", type=Path); args = parser.parse_args()
    source = read_gzip(args.input)
    rejection = Counter(); source_rankable = 0; accepted_records = 0; conflicting_points = 0; station_rows = []; accepted_evse = 0; published_configs = 0
    for station in source.get("stations") or []:
        exact_points = []
        for point in station.get("chargePoints") or []:
            rankable_on_point = sum(1 for tariff in (point.get("tariffs") or []) if tariff.get("sourceValidated") and tariff.get("tccRankable")); source_rankable += rankable_on_point
            point_kind = str(point.get("kind") or "").upper()
            if point_kind not in {"AC", "DC"}: rejection["unsupported_connector_kind"] += rankable_on_point; continue
            formulas: dict[str, dict[str, Any]] = {}; metadata: dict[str, dict[str, Any]] = defaultdict(lambda: {"tariffIds": set(), "tariffRefs": set(), "names": set()})
            for tariff in point.get("tariffs") or []:
                exact, reason = parse_exact_tariff(tariff)
                if exact is None:
                    if tariff.get("sourceValidated") and tariff.get("tccRankable"): rejection[reason] += 1
                    continue
                accepted_records += 1; key = json.dumps(exact, sort_keys=True, ensure_ascii=False, separators=(",", ":")); formulas[key] = exact
                metadata[key]["tariffIds"].add(tariff.get("tariffId"))
                if tariff.get("tariffRef"): metadata[key]["tariffRefs"].add(str(tariff["tariffRef"]))
                if tariff.get("name"): metadata[key]["names"].add(str(tariff["name"]))
            if len(formulas) != 1:
                if len(formulas) > 1: conflicting_points += 1; rejection["conflicting_current_formulas"] += len(formulas)
                continue
            key, exact = next(iter(formulas.items())); meta = metadata[key]
            exact_points.append({"evseId":point.get("evseId"),"kind":str(point.get("kind") or "AC").upper(),"powerKw":float(point.get("powerKw") or 0),"freshmileEvseId":point.get("freshmileEvseId"),"freshmileCustomRef":point.get("freshmileCustomRef"),"tariffIds":sorted(v for v in meta["tariffIds"] if v is not None),"tariffRefs":sorted(meta["tariffRefs"]),"tariffNames":sorted(meta["names"]),"exact":exact}); accepted_evse += 1
        if not exact_points: continue
        groups: dict[str, dict[str, Any]] = {}
        for point in exact_points:
            formula_key = json.dumps(point["exact"], sort_keys=True, ensure_ascii=False, separators=(",", ":")); group_key = f"{point['kind']}|{point['powerKw']:.3f}|{formula_key}"
            if group_key not in groups: groups[group_key] = {"kind":point["kind"],"powerKw":point["powerKw"],"exact":point["exact"],"evseIds":[],"freshmileEvseIds":[],"freshmileCustomRefs":[],"tariffIds":[],"tariffRefs":[],"tariffNames":[]}
            group = groups[group_key]; group["evseIds"].append(point["evseId"])
            if point["freshmileEvseId"] is not None: group["freshmileEvseIds"].append(point["freshmileEvseId"])
            if point["freshmileCustomRef"]: group["freshmileCustomRefs"].append(point["freshmileCustomRef"])
            group["tariffIds"].extend(point["tariffIds"]); group["tariffRefs"].extend(point["tariffRefs"]); group["tariffNames"].extend(point["tariffNames"])
        configs = []; power_variants = Counter((g["kind"], round(g["powerKw"], 3)) for g in groups.values())
        for idx, group in enumerate(groups.values()):
            refs = sorted(set(str(v) for v in group["freshmileCustomRefs"] if v)); provider = "Freshmile direct"
            if power_variants[(group["kind"], round(group["powerKw"], 3))] > 1 and refs: provider += f" (PDC {', '.join(refs)})"
            exact = group["exact"]
            configs.append({"id":f"freshmile-direct-{station.get('stationId')}-{idx}","label":f"{provider} · {group['kind']} {group['powerKw']:g} kW","kind":group["kind"],"powerKw":group["powerKw"],"stalls":len(set(group["evseIds"])),"pricing":{"type":"rules","rules":[display_rule(exact)],"freshmileExact":exact},"offerProvider":provider,"offerType":"operator_direct","freshmileDirect":True,"freshmileVerified":True,"freshmileStrictExact":True,"freshmileStationId":station.get("stationId"),"freshmileEvseIds":sorted(set(str(v) for v in group["evseIds"] if v)),"freshmileInternalEvseIds":sorted(set(group["freshmileEvseIds"])),"freshmileCustomRefs":refs,"freshmileTariffIds":sorted(set(group["tariffIds"])),"freshmileTariffRefs":sorted(set(group["tariffRefs"])),"freshmileTariffNames":sorted(set(group["tariffNames"]))})
        published_configs += len(configs); coords = station.get("coordinates") or {}
        station_rows.append({"stationId":station.get("stationId"),"name":station.get("name"),"address":station.get("address"),"latitude":float(coords.get("latitude")),"longitude":float(coords.get("longitude")),"configurations":configs})
    payload = {"schemaVersion":"1.0.0","dataset":"freshmile-direct-tcc-v8-france","generatedAt":datetime.now(timezone.utc).isoformat(),"sourceDataset":source.get("dataset"),"sourceGeneratedAt":source.get("generatedAt"),"scope":{"countryCode":"FR","onlyDirectCpo":True,"roamingIncluded":False,"configuredRegionalNetworksIncluded":False,"regionalNetworkCandidatesMayRemain":bool((source.get("scope") or {}).get("regionalNetworkCandidatesMayRemain")),"preferentialTariffsIncluded":False,"onlyStrictTccExact":True,"unsupportedTariffsRemainNonRankable":True},"counts":{"sourceStations":int((source.get("stats") or {}).get("stationsInInventory") or 0),"sourceEvse":int((source.get("stats") or {}).get("chargePointsInInventory") or 0),"sourceRankableTariffRecords":source_rankable,"strictAcceptedTariffRecordsBeforeConflictGate":accepted_records,"strictPublishedStations":len(station_rows),"strictPublishedEvse":accepted_evse,"strictPublishedConfigurations":published_configs,"conflictingEvseExcluded":conflicting_points,"rejectedRankableRecords":sum(rejection.values())},"rejectionReasons":dict(sorted(rejection.items())),"sourceSafety":{"freshmileRecoveryEvseMatchRatePct":(source.get("quality") or {}).get("finalEvseMatchRatePct"),"freshmileSourceValidatedTariffRatePct":(source.get("quality") or {}).get("sourceValidatedTariffRatePct"),"regionalNetworkConfiguredExclusions":(source.get("regionalNetworkAudit") or {}).get("configuredNetworkCount"),"regionalNetworkCandidatesMayRemain":bool((source.get("scope") or {}).get("regionalNetworkCandidatesMayRemain")),"nearestStationSubstitutionAllowed":False,"exactEvseCustomRefRequiredBySourcePipeline":True},"stations":station_rows}
    write_gzip(args.output, payload); print(json.dumps({"output":str(args.output),"counts":payload["counts"],"rejectionReasons":payload["rejectionReasons"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__": main()
