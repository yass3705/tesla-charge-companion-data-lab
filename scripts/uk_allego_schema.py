#!/usr/bin/env python3
"""Summarize already-validated Allego CPO PCPR tariff structures without credentials."""
import collections,gzip,json
from pathlib import Path
source=Path("data/national/uk_allego_uk_pcpr_v9.json.gz")
with gzip.open(source,"rt",encoding="utf-8") as h: doc=json.load(h)
s=doc["sources"][0]
rows=s.get("locations",[]);tariffs=s.get("tariffs",[])
result={"sourceId":s.get("id"),"stations":len(rows),"tariffs":len(tariffs),
"components":dict(collections.Counter(c.get("type") for t in tariffs for el in t.get("elements",[]) for c in el.get("price_components",[]))),
"componentsStepSizes":dict(collections.Counter(f"{c.get('type')}|{c.get('step_size')}" for t in tariffs for el in t.get("elements",[]) for c in el.get("price_components",[]))),
"elementsPerTariff":dict(collections.Counter(str(len(t.get("elements",[]))) for t in tariffs)),
"restrictions":dict(collections.Counter(k for t in tariffs for el in t.get("elements",[]) for k in (el.get("restrictions") or {}))),
"tariffExtraKeys":dict(collections.Counter(k for t in tariffs for k in t if k not in ("id","country_code","party_id","currency","elements","tccPriceBasis","tccSourcePriceBasis"))),
"connectorStandards":dict(collections.Counter(c.get("standard","missing") for l in rows for e in l.get("evses",[]) for c in e.get("connectors",[]))),
"connectorPowerTypes":dict(collections.Counter(c.get("power_type","missing") for l in rows for e in l.get("evses",[]) for c in e.get("connectors",[]))),
"connectorCount":sum(len(e.get("connectors",[])) for l in rows for e in l.get("evses",[])),
"exampleOfComplexRules":[{"id":t.get("id"),"elements":t.get("elements")} for t in tariffs if len(t.get("elements",[]))>1 or any(el.get("restrictions") for el in t.get("elements",[]))][:3]}
Path("reports/uk/allego_uk-pcpr-schema.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({k:v for k,v in result.items() if k!="exampleOfComplexRules"},ensure_ascii=False,indent=2))
