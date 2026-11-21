#!/usr/bin/env python3
"""Preserved inline Eco-Movement PCPR collector from G1 workflow archive."""
import hashlib
import os,json,time,urllib.request,urllib.parse,urllib.error,gzip
from pathlib import Path
from datetime import datetime,timezone

token=os.environ.get("ECO_MOVEMENT_PCPR_TOKEN","").strip()
if not token:
    raise SystemExit("ECO_MOVEMENT_PCPR_TOKEN missing")

BASE="https://open-chargepoints.com/api/ocpi/cpo/2.2.1"
STATUS_URL="https://open-chargepoints.com/api/statuses"
UA="TeslaChargeCompanion/9 Eco-Movement-PCPR"
headers={"Authorization":"Token "+token,"Accept":"application/json","User-Agent":UA}

def get_json(url,timeout=60):
    req=urllib.request.Request(url,headers=headers)
    with urllib.request.urlopen(req,timeout=timeout) as r:
        body=r.read()
        return r.status,dict(r.headers.items()),json.loads(body.decode("utf-8"))

def response_rows(payload, endpoint, *, allow_list=False):
    if isinstance(payload, dict):
        if "status_code" in payload and payload["status_code"] != 1000:
            raise RuntimeError(f"{endpoint}: provider reported a failed request")
        rows = payload.get("data")
    else:
        rows = payload if allow_list else None
    if isinstance(rows, dict):
        rows = [rows]
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise RuntimeError(f"{endpoint}: missing or invalid data records")
    return rows


def page(endpoint, limit=1000):
    out = []
    seen_pages = set()
    expected = None
    while True:
        query = urllib.parse.urlencode({"limit": limit, "offset": len(out)})
        status, headers, payload = get_json(f"{BASE}/{endpoint}?{query}")
        if status != 200:
            raise RuntimeError(f"{endpoint}: HTTP {status}")
        rows = response_rows(payload, endpoint)
        total = next((v for k, v in headers.items() if k.lower() == "x-total-count"), None)
        if total is not None:
            if not str(total).isdigit() or (expected is not None and int(total) != expected):
                raise RuntimeError(f"{endpoint}: inconsistent pagination total")
            expected = int(total)
        if rows:
            fingerprint = hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).digest()
            if fingerprint in seen_pages:
                raise RuntimeError(f"{endpoint}: repeated page")
            seen_pages.add(fingerprint)
        out.extend(rows)
        if expected is not None:
            if len(out) == expected:
                return out
            if not rows or len(out) > expected:
                raise RuntimeError(f"{endpoint}: incomplete or inconsistent pagination")
        elif len(rows) < limit:
            return out
        time.sleep(.25)


locations = page("locations")
tariffs = page("tariffs")
status_http, _, status_json = get_json(STATUS_URL)
if status_http != 200:
    raise RuntimeError(f"statuses: HTTP {status_http}")
statuses = response_rows(status_json, "statuses", allow_list=True)

def names(loc):
    vals=[]
    for k in ("operator","owner","suboperator"):
        x=loc.get(k)
        if isinstance(x,dict):
            if x.get("name"): vals.append(x.get("name"))
            for e in x.get("ema_id") or []: vals.append(e)
    return [str(v) for v in vals if v]

target_terms={
  "Blink":["blink"],
  "bp pulse":["bp pulse","chargemaster","bpc","bpp","bpt"],
  "Source EV":["source ev","sourceev"],
  "ubitricity":["ubitricity"],
  "Shell Recharge":["shell recharge","shell"],
  "evyve":["evyve"],
  "ChargePoint CMS":["chargepoint"],
  "InstaVolt":["instavolt"],
  "ev-point":["ev-point","ev point"]
}

operator_hits={k:{"locations":0,"sampleNames":set(),"sampleIds":[]} for k in target_terms}
for loc in locations:
    hay=" | ".join(names(loc)).lower()
    for label,terms in target_terms.items():
        if any(t in hay for t in terms):
            h=operator_hits[label]
            h["locations"]+=1
            h["sampleNames"].update(names(loc))
            if len(h["sampleIds"])<10: h["sampleIds"].append(loc.get("id"))

for v in operator_hits.values():
    v["sampleNames"]=sorted(v["sampleNames"])[:20]

now=datetime.now(timezone.utc).isoformat()
payload={"retrievedAt":now,"source":"Eco-Movement PCPR","locations":locations,"tariffs":tariffs,"statuses":statuses}
with gzip.open("data/national/uk_eco_movement_pcpr.json.gz","wt",encoding="utf-8") as g:
    json.dump(payload,g,ensure_ascii=False,separators=(",",":"))

report={
  "retrievedAt":now,
  "locationCount":len(locations),
  "tariffCount":len(tariffs),
  "statusCount":len(statuses),
  "operatorHits":operator_hits
}
Path("reports/uk/eco-movement-pcpr-latest.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
print(json.dumps(report,ensure_ascii=False,indent=2))
