#!/usr/bin/env python3
import json, os, subprocess, sys
from urllib.parse import urlencode

API=os.environ.get("AVIA_API_BASE","https://pdefweushaapiam01.azure-api.net").rstrip("/")
TENANT=os.environ.get("AVIA_PICOTY_TENANT_ID","9439c762-3ce1-45fc-a9ea-a92ed5e06489")
KEY=os.environ.get("AVIA_APIM_SUBSCRIPTION_KEY","").strip()
# Known AVIA Picoty site: Maulette, FRPY2P785500029.
BBOX=("48.70,1.50","48.88,1.78")

def get(path, query=None):
    url=API+path
    if query: url += "?" + urlencode(query)
    cmd=["curl","-sS","--max-time","30","-w","\n__STATUS__:%{http_code}",
         "-H","accept: */*","-H","content-type: application/json; charset=utf-8",
         "-H","accept-language: fr","-H","x-app-platform: ios","-H","x-app-version: 2.3.0",
         "-H","user-agent: RechargeEtVous/1 CFNetwork",
         "-H",f"ocp-apim-subscription-key: {KEY}",url]
    p=subprocess.run(cmd,capture_output=True,text=True)
    body,status=p.stdout.rsplit("\n__STATUS__:",1) if "\n__STATUS__:" in p.stdout else (p.stdout,"000")
    return int(status), body

def main():
    if not KEY:
        print("missing_secret=true")
        return 2
    base=f"/app-backend/v1/tenants/{TENANT}/map-locations"
    variants=[
      ("FRPY2",{"includeCpos":"FRPY2"}),
      ("PY2",{"includeCpos":"PY2"}),
      ("none",{}),
    ]
    summary=[]
    winning=[]
    for label,extra in variants:
        q={"latLongBottomLeft":BBOX[0],"latLongTopRight":BBOX[1],
           "evseTypes":"AC,DC,HPC","connectorTypes":"TYPE2,CCS"}
        q.update(extra)
        status,body=get(base,q)
        rec={"variant":label,"status":status}
        try:
            data=json.loads(body)
            locs=data.get("locations") or []
            rec["locations"]=len(locs)
            rec["partyIds"]=sorted({str(x.get("partyId")) for x in locs if x.get("partyId")})
            rec["ids"]=[x.get("id") for x in locs[:8] if x.get("id")]
            if locs:
                winning.append((label,locs))
        except Exception:
            rec["bodyPrefix"]=body[:160]
        summary.append(rec)
    out={"tenantId":TENANT,"bbox":BBOX,"results":summary}
    print(json.dumps(out,indent=2,ensure_ascii=False))
    if not winning:
        return 3
    # Validate one returned location detail and detect FR*PY2 EVSEs without persisting credentials.
    label,locs=winning[0]
    lid=locs[0].get("id")
    st,body=get(f"/app-backend/v1/tenants/{TENANT}/locations/{lid}")
    detail={"variant":label,"locationUuid":lid,"status":st}
    try:
        d=json.loads(body)
        evses=d.get("evses") or []
        detail["locationName"]=d.get("locationName")
        detail["evseIds"]=[e.get("evseId") for e in evses if e.get("evseId")]
        detail["frpy2Matches"]=[x for x in detail["evseIds"] if str(x).replace("*","").upper().startswith("FRPY2")]
    except Exception:
        detail["bodyPrefix"]=body[:160]
    print("DETAIL="+json.dumps(detail,ensure_ascii=False))
    return 0 if st==200 else 4

if __name__=="__main__":
    raise SystemExit(main())
