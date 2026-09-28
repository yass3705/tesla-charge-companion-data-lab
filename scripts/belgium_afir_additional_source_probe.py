#!/usr/bin/env python3
from __future__ import annotations
import json, urllib.request, urllib.error, xml.etree.ElementTree as ET, re
from pathlib import Path
from collections import Counter

OUT=Path("reports/belgium")
OUT.mkdir(parents=True,exist_ok=True)

SOURCES={
  "road":{
    "url":"https://roaming.road.io/files/9ef09c78-2666-418a-aa45-4f2261e2e305/locations.json?force=true",
    "kind":"json"
  },
  "indigo":{
    "url":"https://transportdata.be/dataset/27f1357d-71ee-48cb-84a1-96f3f4f034b8/resource/d4bc8ddd-c80f-4330-98e5-d86e5b2147c3/download/indigo-data-evcharging-static-datexii.xml",
    "kind":"xml"
  },
  "monta_docs":{
    "url":"https://docs.public-api.monta.com/reference/get-afir-charge-points",
    "kind":"html"
  }
}

def fetch(url):
    req=urllib.request.Request(url,headers={"User-Agent":"TCC-Belgium-AFIR-probe/1.0","Accept":"*/*"})
    try:
        with urllib.request.urlopen(req,timeout=90) as r:
            return r.status,r.headers.get("content-type",""),r.read()
    except urllib.error.HTTPError as e:
        return e.code,e.headers.get("content-type",""),e.read()

def scan_json(obj):
    ids=set(); evse_ids=set(); operators=Counter(); tariffs=0; currencies=Counter(); locations=0
    def walk(x):
        nonlocal tariffs,locations
        if isinstance(x,dict):
            low={str(k).lower():v for k,v in x.items()}
            # rough location signal
            if any(k in low for k in ("coordinates","latitude","lat")) and any(k in low for k in ("evses","charge_points","chargepoints","connectors")):
                locations+=1
            for k in ("id","location_id","locationid"):
                v=low.get(k)
                if isinstance(v,str): ids.add(v)
            for k in ("evse_id","evseid","uid"):
                v=low.get(k)
                if isinstance(v,str) and ("*" in v or re.match(r"^[A-Z]{2}",v,re.I)): evse_ids.add(v)
            for k in ("operator","operator_name","operatorname","cpo","party_id","partyid","network"):
                v=low.get(k)
                if isinstance(v,str) and len(v)<120: operators[v]+=1
                elif isinstance(v,dict):
                    n=v.get("name") or v.get("id")
                    if isinstance(n,str): operators[n]+=1
            if any(k in low for k in ("tariffs","tariff","price","pricing","adhoc_price","ad_hoc_price")):
                tariffs+=1
            cur=low.get("currency")
            if isinstance(cur,str): currencies[cur]+=1
            for v in x.values(): walk(v)
        elif isinstance(x,list):
            for v in x: walk(v)
    walk(obj)
    return {
      "approxLocations":locations,
      "distinctIds":len(ids),
      "distinctEvseIds":len(evse_ids),
      "operatorTokens":operators.most_common(30),
      "tariffBearingObjects":tariffs,
      "currencies":dict(currencies)
    }

results={}
for name,s in SOURCES.items():
    st,ct,body=fetch(s["url"])
    rec={"status":st,"contentType":ct,"bytes":len(body)}
    try:
        if s["kind"]=="json" and st==200:
            obj=json.loads(body)
            rec["parsed"]=scan_json(obj)
            # persist public source snapshot in compressed-neutral JSON only if reasonable
            p=Path(f"data/belgium/additional/{name}-2026-09-28.json")
            p.parent.mkdir(parents=True,exist_ok=True)
            p.write_text(json.dumps(obj,ensure_ascii=False,separators=(",",":"))+"\n")
            rec["snapshotPath"]=str(p)
        elif s["kind"]=="xml" and st==200:
            root=ET.fromstring(body)
            tags=Counter()
            text_tokens=[]
            for el in root.iter():
                tag=el.tag.split("}")[-1]
                tags[tag]+=1
                if el.text and el.text.strip():
                    text_tokens.append(el.text.strip())
            evse_like=[t for t in text_tokens if re.search(r"[A-Z]{2}\*[A-Z0-9]+\*E",t,re.I)]
            price_like=[t for t in text_tokens if re.fullmatch(r"\d+(?:[.,]\d+)?",t)]
            rec["parsed"]={
              "topTags":tags.most_common(40),
              "evseLikeCount":len(set(evse_like)),
              "evseLikeSample":sorted(set(evse_like))[:50],
              "numericTokenCount":len(price_like),
            }
            p=Path(f"data/belgium/additional/{name}-2026-09-28.xml")
            p.parent.mkdir(parents=True,exist_ok=True)
            p.write_bytes(body)
            rec["snapshotPath"]=str(p)
        else:
            txt=body.decode("utf-8","replace")
            rec["bodySignals"]={
              "authorizationMention":bool(re.search(r"authorization|bearer|api[-_ ]?key",txt,re.I)),
              "afirMention":bool(re.search(r"afir",txt,re.I)),
              "endpointCandidates":sorted(set(re.findall(r'https?://[^"\'<>\s]+',txt)))[:30]
            }
    except Exception as e:
        rec["parseError"]=type(e).__name__+": "+str(e)
    results[name]=rec

payload={"country":"BE","asOf":"2026-09-28","phase":"additional-source-probe","sources":results}
(OUT/"belgium-afir-additional-source-probe-2026-09-28.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n")
print(json.dumps(payload,ensure_ascii=False,indent=2))
