#!/usr/bin/env python3
import json
from pathlib import Path

DETAIL=Path("reports/belgium/belgium-residual-unpriced-detail-v2-2026-09-28.json")
OUT_OVERLAY=Path("data/operator_direct/shell_belgium_official_2026-09-28.json")
OUT_FINAL=Path("reports/belgium/belgium-final-gap-reconciliation-2026-09-28.json")
SHELL_SOURCE="https://www.shell.be/fr_be/electric-charging/tarifs-de-shell-recharge.html"
IONITY_SOURCE="https://www.ionity.eu/fr/stories/pourquoi-les-prix-de-recharge-evoluent-ils-en-europe"
PARDIS_SOURCE="https://www.pardis.be/"
VIRTA_SOURCE="https://www.virta.global/knowledge-base/charging-prices"
TE_SOURCE="https://services.totalenergies.be/fr/faq/mobilite-electrique/quels-sont-les-tarifs-des-stations-de-recharge-de-totalenergies-et-de-ses"

d=json.loads(DETAIL.read_text())
targets=d["targets"]

# Official Shell Belgium rule (current 2026-09-28):
# Shell Recharge network fast chargers >50 kW: 0.79 EUR/kWh with payment card.
# Apply only to EVSEs explicitly identified as operator "Shell Recharge" and >50kW.
resolved=[]
remaining_shell=[]
for x in targets["Shell Recharge"]["items"]:
    maxw=max((x.get("powerW") or [0]))
    ids=x.get("externalIdentifiers") or []
    if maxw>50000 and ids:
        resolved.append({
          "externalIdentifiers":ids,
          "locationId":x.get("locationId"),
          "stationId":x.get("stationId"),
          "evseId":x.get("evseId"),
          "powerW":maxw,
          "tariff":{
            "ratePolicy":"adHoc",
            "paymentMethod":"bankCard",
            "currency":"EUR",
            "priceType":"pricePerKWh",
            "price":0.79,
            "taxIncluded":True
          },
          "source":{
            "url":SHELL_SOURCE,
            "publisher":"Shell Belgium",
            "rule":"Shell Recharge network fast chargers (>50 kW): €0.79/kWh with payment card",
            "retrieved":"2026-09-28"
          }
        })
    else:
        remaining_shell.append(x)

overlay={
  "country":"BE",
  "operator":"Shell Recharge",
  "asOf":"2026-09-28",
  "scope":"official direct/ad-hoc payment-card tariff for Shell Recharge network fast chargers (>50 kW)",
  "entries":resolved,
  "count":len(resolved),
  "rules":[
    "Only EVSEs already canonically attributed to Shell Recharge are eligible.",
    "Only EVSEs with canonical maximum power >50 kW are eligible.",
    "Community by Shell Recharge 7-22 kW is explicitly variable and is not filled.",
    "No roaming tariff is used."
  ]
}
OUT_OVERLAY.parent.mkdir(parents=True,exist_ok=True)
OUT_OVERLAY.write_text(json.dumps(overlay,ensure_ascii=False,indent=2)+"\n")

final={
  "country":"BE",
  "asOf":"2026-09-28",
  "scope":"Belgium Eco-Movement selected-CPO feed tariff-gap reconciliation",
  "inputMissingPriceEvses":12858,
  "decisions":{
    "resolvedExactOfficial":len(resolved),
    "excludedNonProduction":1,
    "unresolvedSourceLimited":12858-len(resolved)-1
  },
  "cpos":{
    "Shell Recharge":{
      "rawMissing":24,
      "resolvedExactOfficial":len(resolved),
      "remainingUnresolved":len(remaining_shell),
      "resolution":"8 DC 150 kW EVSEs receive Shell Belgium's official direct bank-card tariff; 7.36 kW AC EVSEs remain unresolved because Shell explicitly publishes Community pricing as variable.",
      "source":SHELL_SOURCE
    },
    "Gabriels":{
      "rawMissing":1,
      "excludedNonProduction":1,
      "remainingUnresolved":0,
      "resolution":"Exclude from production pricing coverage: canonical brand is explicitly 'Gabriels EV Hubject test location', EVSE is inoperative and connector power is 0 W. Raw NAP record remains preserved."
    },
    "IONITY":{
      "rawMissing":2,
      "resolvedExactOfficial":0,
      "remainingUnresolved":2,
      "resolution":"Drongen Gent is a newly opened public IONITY site. IONITY publishes Belgium Direct/ad-hoc as 'up to €0.78/kWh' and states the applicable price is shown before session; this does not prove the exact station tariff, so no value is invented.",
      "source":IONITY_SOURCE
    },
    "Sowalwatt":{
      "rawMissing":60,
      "resolvedExactOfficial":0,
      "remainingUnresolved":60,
      "resolution":"Official Pardis/Sowalwatt material confirms electricity resale/charging activity but no public station-level ad-hoc tariff was found.",
      "source":PARDIS_SOURCE
    },
    "VIR":{
      "rawMissing":12,
      "resolvedExactOfficial":0,
      "remainingUnresolved":12,
      "resolution":"All residual EVSEs use BE*VIR identifiers. Virta pricing is owner/CPO-defined and station-specific; no exact public tariff was found for Hannut or Gîte Riezes, so no generic Virta price is applied.",
      "source":VIRTA_SOURCE
    },
    "recticel":{
      "rawMissing":30,
      "resolvedExactOfficial":0,
      "remainingUnresolved":30,
      "resolution":"Corporate-site EVSEs use BE*TCB identifiers, but no exact public ad-hoc tariff or defensible public/private exclusion flag is available. Keep source-limited rather than inheriting TotalEnergies families."
    },
    "TotalEnergies":{
      "rawMissing":12729,
      "resolvedExactOfficial":0,
      "remainingUnresolved":12729,
      "resolution":"Official Belgium material does not provide a station-exact universal tariff; Charge+ is retained as a separate customer pricing layer and is not substituted for canonical CPO ad-hoc pricing. Charge Europe app-key/private-auth route is intentionally bounded.",
      "source":TE_SOURCE
    }
  },
  "productionSummary":{
    "rawCpoCounts":{"complete":64,"partial":7,"total":71},
    "productionCompleteAfterExclusion":["Gabriels"],
    "productionPartialRemaining":["TotalEnergies","Shell Recharge","IONITY","Sowalwatt","recticel","VIR"],
    "notes":[
      "Raw NAP data and raw first-pass counts are not rewritten.",
      "Exact overlays are additive and provenance-preserving.",
      "Source-limited means all safe public/read-only routes explored in this pass did not yield an exact defensible CPO ad-hoc tariff.",
      "The Eco-Movement Belgium dataset covers selected CPOs, not the entire Belgian market."
    ]
  }
}
OUT_FINAL.write_text(json.dumps(final,ensure_ascii=False,indent=2)+"\n")
print(json.dumps({"shellResolved":len(resolved),"shellRemaining":len(remaining_shell),"finalDecisions":final["decisions"]},indent=2))
