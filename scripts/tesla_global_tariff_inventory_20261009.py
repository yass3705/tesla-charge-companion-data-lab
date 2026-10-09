#!/usr/bin/env python3
"""Read-only census of the REAL Tesla global tariff catalogue used by TCC V9.

Separate source from the non-Tesla Data Lab files. No V9 price publication,
currency conversion or assertion that an example simulated amount is reliable.
"""
from __future__ import annotations
import collections
import datetime as dt
import hashlib
import json
import os
import pathlib
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/tariff-scenarios"
SCOPE = ("FR", "IT", "CH", "DE", "ES", "NL", "UK", "MA", "BE")
REF = os.environ.get("TCC_TESLA_SOURCE_REF", "main")
URL = f"https://raw.githubusercontent.com/yass3705/tesla-charge-companion-stable/{REF}/data/tesla_stations.json"

def country_code(code):
    x = str(code or "").upper().strip()
    return "UK" if x == "GB" else x

def json_write(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def read_catalogue():
    with urllib.request.urlopen(
        urllib.request.Request(URL, headers={"User-Agent": "TCC-Scenario-Audit/1.0"}),
        timeout=90,
    ) as res:
        raw = res.read(20_000_001)
    if len(raw) > 20_000_000:
        raise ValueError("Tesla catalogue exceeds 20 MB read limit")
    stations = json.loads(raw)
    if not isinstance(stations, list) or not stations:
        raise ValueError("Expected a non-empty Tesla global stations array")
    return stations, hashlib.sha256(raw).hexdigest(), len(raw)

def validate_power_bands(bands):
    if not isinstance(bands, list) or not bands:
        return "missing_power_bands"
    values = []
    try:
        for band in bands:
            low, high, rate = float(band["minKw"]), float(band["maxKw"]), float(band["ratePerMinute"])
            if high <= low or rate < 0:
                return "invalid_power_band_bounds_or_rate"
            values.append((low, high, rate))
    except (TypeError, ValueError, KeyError):
        return "invalid_power_band_fields"
    ordered = sorted(values)
    for prev, nxt in zip(ordered, ordered[1:]):
        if prev[1] < nxt[0]:
            return "power_band_gap"
        if prev[1] > nxt[0]:
            return "power_band_overlap"
    return None

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    stations, digest, size = read_catalogue()
    counts = collections.defaultdict(collections.Counter)
    country_billing = collections.defaultdict(collections.Counter)
    country_currency = collections.defaultdict(collections.Counter)
    country_source_vintage = collections.defaultdict(collections.Counter)
    external = collections.Counter()
    issues = collections.Counter()
    examples = collections.defaultdict(list)
    complete_configs = collections.defaultdict(list)
    age_histogram = collections.defaultdict(collections.Counter)
    scope_audit = collections.defaultdict(collections.Counter)
    scope_gaps = []
    sample_count = 0
    for station in stations:
        if not isinstance(station, dict):
            issues["station_not_object"] += 1
            continue
        cc = country_code(station.get("countryCode"))
        if cc not in SCOPE:
            external[cc or "UNKNOWN"] += 1
            continue
        counts[cc]["stations"] += 1
        # Source-age != workflow run age. Do not silently qualify old Mac observations as live.
        raw_age = str(station.get('lastUpdated') or '').strip()
        try:
            then = dt.date.fromisoformat(raw_age[:10])
            days_old = (dt.datetime.now(dt.timezone.utc).date()-then).days
            bucket = 'future_source_date' if days_old<0 else 'under_10d' if days_old<10 else '10_to_29d' if days_old<30 else '30d_plus'
        except (ValueError, TypeError):
            bucket = 'source_date_unavailable'
        age_histogram[cc][bucket] += 1
        configs = station.get("chargingConfigurations")
        if not isinstance(configs, list) or not configs:
            configs = [station]
        for cfg in configs:
            if not isinstance(cfg, dict):
                issues["invalid_configuration"] += 1
                continue
            counts[cc]["charging_configurations"] += 1
            pricing = cfg.get("pricing") or station.get("pricing")
            if not isinstance(pricing, dict) or not isinstance(pricing.get("rules"), list):
                counts[cc]["configurations_without_structured_pricing"] += 1
                continue
            counts[cc]["configurations_with_structured_pricing"] += 1
            valid_rules = [r for r in pricing['rules'] if isinstance(r,dict)]
            modes=','.join(sorted(set(str(r.get('billing') or '') for r in valid_rules)))
            windows=','.join(sorted(set(str(r.get('scope') or '') for r in valid_rules)))
            currencies=','.join(sorted(set(str(r.get('currency') or pricing.get('currency') or station.get('currency') or '') for r in valid_rules)))
            sig=f'{cc}|{modes}|{windows}|{currencies}|{len(valid_rules)}'
            if len(complete_configs[sig]) < 5:
                complete_configs[sig].append({
                   'country':cc,'stationId':station.get('id'),'configurationId':cfg.get('id'),
                   'configurationPowerKw':cfg.get('powerKw',station.get('powerKw')),
                   'source':station.get('source'),'stationLastUpdated':station.get('lastUpdated'),
                   'pricing':pricing})
            def clock_minute(s,default):
                try:
                    hh,mm=map(int,str(s).split(':'))
                    if 0<=hh<=24 and 0<=mm<=59 and (hh!=24 or mm==0):return hh*60+mm
                except (TypeError,ValueError):pass
                return default
            def within(r,m):
                if r.get('scope')=='allDay':return True
                a=clock_minute(r.get('start'),0);b=clock_minute(r.get('end'),1440)
                return True if a==b else a<=m<b if a<b else m>=a or m<b
            if any(r.get('scope')=='allDay' for r in valid_rules):
                scope_audit[cc]['full_clock_coverage']+=1
            elif valid_rules and all(r.get('scope')=='timeWindow' for r in valid_rules):
                # Full 1440-minute clock coverage, distinct from date/holiday restrictions.
                missing=0;overlapping=0
                for minute in range(1440):
                    n=sum(within(rule,minute) for rule in valid_rules)
                    missing += n==0
                    overlapping += n>1
                if missing:
                    scope_audit[cc]['clock_gap_configurations']+=1
                    scope_audit[cc]['uncovered_clock_minutes']+=missing
                    if len(scope_gaps)<100:scope_gaps.append({'country':cc,'stationId':station.get('id'),
                       'configurationId':cfg.get('id'),'uncoveredMinutes':missing})
                else:scope_audit[cc]['full_clock_coverage']+=1
                if overlapping:scope_audit[cc]['overlapping_rule_configurations']+=1
            else:scope_audit[cc]['clock_scope_not_directly_verifiable']+=1
            for rule in pricing["rules"]:
                if not isinstance(rule, dict):
                    issues["invalid_rule"] += 1
                    continue
                billing = str(rule.get("billing") or "UNDECLARED")
                country_billing[cc][billing] += 1
                currency = str(rule.get("currency") or pricing.get("currency") or station.get("currency") or "UNDECLARED").upper()
                country_currency[cc][currency] += 1
                country_source_vintage[cc][str(station.get("source") or "UNDECLARED")] += 1
                if billing == "powerMinute":
                    problem = validate_power_bands(rule.get("powerBands"))
                    if problem:
                        issues[cc + "/" + problem] += 1
                    # V9 Tesla adapter flattens power bands using the charger's
                    # rated power, NOT the actual delivered power over time.
                    issues[cc + "/adapter_flattens_dynamic_power_tariff"] += 1
                elif billing == "kwh":
                    if rule.get("pricePerKwh") is None:
                        issues[cc + "/kwh_rate_missing"] += 1
                elif billing == "minute":
                    if rule.get("chargePerMinute") is None:
                        issues[cc + "/minute_rate_missing"] += 1
                    elif rule.get("pricePerMinute") is None:
                        issues[cc + "/adapter_may_double_count_minute_rate"] += 1
                else:
                    issues[cc + "/unknown_billing_mode"] += 1
                if currency not in ("EUR", "UNDECLARED"):
                    # Tesla V9 adapter hard-codes offer.currency='EUR'.
                    # It must preserve the source currency/FX contract.
                    issues[cc + "/adapter_hardcodes_eur_offer_currency"] += 1
                if currency == "UNDECLARED":
                    issues[cc + "/currency_not_explicit"] += 1
                signature = f"{cc}|{billing}|{currency}|{'bands' if rule.get('powerBands') else 'single'}|{rule.get('scope', 'unscoped')}"
                if len(examples[signature]) < 3:
                    examples[signature].append({
                        "country": cc,
                        "stationId": station.get("id"),
                        "configurationId": cfg.get("id"),
                        "configurationPowerKw": cfg.get("powerKw", station.get("powerKw")),
                        "source": station.get("source"),
                        "stationLastUpdated": station.get("lastUpdated"),
                        "billing": billing,
                        "currency": currency,
                        "pricingRule": rule,
                    })
                    sample_count += 1
    summary = {
        "schemaVersion": "1.0",
        "generatedAt": dt.datetime.now(dt.timezone.utc).isoformat(),
        "scopeCountries": list(SCOPE),
        "sourceRepository": "yass3705/tesla-charge-companion-stable",
        "sourceRef": REF,
        "sourcePath": "data/tesla_stations.json",
        "sourceSha256": digest,
        "sourceBytes": size,
        "sourceTotalStations": len(stations),
        "outOfScopeStations": dict(sorted(external.items())),
        "countries": {
            cc: {
                **dict(counts[cc]),
                "billingRuleOccurrences": dict(country_billing[cc]),
                "ruleCurrencies": dict(country_currency[cc]),
                "sourceLabels": dict(country_source_vintage[cc]),
                "sourceAgeBuckets": dict(age_histogram[cc]),
                "timeScopeAudit": dict(scope_audit[cc]),
            }
            for cc in SCOPE
        },
        "issues": dict(sorted(issues.items())),
        "fixtureExamples": sample_count,
        "completeConfigurationFixtureCount": sum(map(len,complete_configs.values())),
        "clockGapExamples": scope_gaps,
        "warnings": [
            "Global Tesla tariffs were ABSENT from the previous Data Lab source-roots census.",
            "Charging configurations and rule occurrences are NOT physical EVSE counts.",
            "Station/provider source timestamps are not assumed fresh from this fetch.",
            "Pricing by delivered power requires a power-over-time trace; a rated-power band is not a correct simulation.",
            "Rules without an explicit currency must not silently default to EUR.",
            "These are structural findings, not verified charge-session prices or changes to V9.",
        ],
    }
    json_write("tesla-global-inventory-latest.json", summary)
    json_write("tesla-global-real-rule-fixtures.json", [x for sig in sorted(examples) for x in examples[sig]])
    json_write('tesla-global-complete-config-fixtures.json',[
        x for sig in sorted(complete_configs) for x in complete_configs[sig]])
    print("TESLA_GLOBAL_INVENTORY=" + json.dumps({
        "stationCount": len(stations),
        "inScopeByCountry": {cc: counts[cc]["stations"] for cc in SCOPE},
        "billing": {cc: dict(country_billing[cc]) for cc in SCOPE},
        "issues": dict(issues),
        "fixtureExamples": sample_count,
        "sourceSha256": digest,
    }, ensure_ascii=False))

if __name__ == "__main__":
    main()
