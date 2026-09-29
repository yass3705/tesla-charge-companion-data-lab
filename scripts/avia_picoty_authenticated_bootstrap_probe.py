#!/usr/bin/env python3
import json, os, subprocess
from pathlib import Path
from urllib.parse import urlencode

API=os.environ.get("AVIA_API_BASE","https://pdefweushaapiam01.azure-api.net").rstrip("/")
KEY=os.environ.get("AVIA_APIM_SUBSCRIPTION_KEY","").strip()
TENANT="9439c762-3ce1-45fc-a9ea-a92ed5e06489"
PATHS=[
 "/app-backend/v1/registration-groups",
 "/app-backend/v1/tenants",
 f"/app-backend/v1/tenants/{TENANT}/app-distribution",
 f"/app-backend/v1/tenants/{TENANT}/cpos",
 f"/app-backend/v1/tenants/{TENANT}/files",
 f"/app-backend/v1/tenants/{TENANT}/map-locations",
 "/v1/registration-groups",
 "/v1/tenants",
]
def req(path):
    url=API+path
    if path.endswith("/map-locations"):
        url += "?" + urlencode({
          "latLongBottomLeft":"48.70,1.50",
          "latLongTopRight":"48.88,1.78",
          "evseTypes":"AC,DC,HPC",
          "connectorTypes":"TYPE2,CCS",
        })
    cmd=["curl","-sS","--max-time","25","-w","\n__STATUS__:%{http_code}",
         "-H","accept: application/json",
         "-H","x-app-platform: ios",
         "-H","x-app-version: 2.0.0",
         "-H","user-agent: RechargeEtVous/4418 CFNetwork",
         "-H",f"ocp-apim-subscription-key: {KEY}",url]
    p=subprocess.run(cmd,capture_output=True,text=True)
    body,status=p.stdout.rsplit("\n__STATUS__:",1) if "\n__STATUS__:" in p.stdout else (p.stdout,"000")
    rec={"path":path,"status":int(status)}
    try:
        data=json.loads(body)
        rec["jsonType"]=type(data).__name__
        if isinstance(data,dict):
            rec["keys"]=sorted(list(data.keys()))[:40]
            slim={}
            for k,v in data.items():
                kl=k.lower()
                if any(t in kl for t in ("tenant","registration","distribution","name","id","cpo")) and not any(s in kl for s in ("token","key","secret","auth")):
                    if isinstance(v,(str,int,float,bool,type(None))):
                        slim[k]=v
                    elif isinstance(v,list):
                        slim[k]=v[:10]
            if slim:
                rec["summary"]=slim
        elif isinstance(data,list):
            rec["length"]=len(data)
            rec["sample"]=data[:5]
    except Exception:
        rec["bodyPrefix"]=body[:300]
    return rec


def cpo_and_map_diagnostics():
    cpos=req(f"/app-backend/v1/tenants/{TENANT}/cpos")
    # Re-fetch full CPO payload locally so we can identify Picoty/AVIA identifiers.
    url=API+f"/app-backend/v1/tenants/{TENANT}/cpos"
    cmd=["curl","-sS","--max-time","25","-H","accept: application/json",
         "-H","x-app-platform: ios","-H","x-app-version: 2.3.0",
         "-H","user-agent: RechargeEtVous/4614 CFNetwork",
         "-H",f"ocp-apim-subscription-key: {KEY}",url]
    p=subprocess.run(cmd,capture_output=True,text=True)
    matches=[]
    try:
        arr=json.loads(p.stdout)
        for x in arr if isinstance(arr,list) else []:
            s=json.dumps(x,ensure_ascii=False).lower()
            if any(t in s for t in ("picoty","avia volt","aviavolt")) or (str(x.get("countryCode") or "").upper()=="FR" and str(x.get("partyId") or "").upper()=="PY2"):
                matches.append({k:v for k,v in x.items() if k.lower() not in ("token","key","secret","authorization")})
    except Exception:
        pass
    variants=[]
    include_values=[]
    for x in matches:
        cc=str(x.get("countryCode") or "").upper()
        pid=str(x.get("partyId") or "").upper()
        if cc and pid:
            include_values += [cc+pid, cc+"*"+pid, pid]
    include_values += ["FRPY2","FR*PY2","PY2"]
    seen=[]
    for v in include_values:
        if v and v not in seen: seen.append(v)
    base=f"/app-backend/v1/tenants/{TENANT}/map-locations"
    for inc in seen[:12]:
        for status in ("AVAILABLE","UNKNOWN","OUT_OF_ORDER"):
            q={
              "latLongBottomLeft":"48.70,1.50",
              "latLongTopRight":"48.88,1.78",
              "evseTypes":"AC,DC,HPC",
              "connectorTypes":"TYPE2,CCS",
              "includeCpos":inc,
              "locationStatus":status,
            }
            url=API+base+"?"+urlencode(q)
            cmd=["curl","-sS","--max-time","25","-w","\\n__STATUS__:%{http_code}",
                 "-H","accept: application/json","-H","x-app-platform: ios",
                 "-H","x-app-version: 2.3.0","-H","user-agent: RechargeEtVous/4614 CFNetwork",
                 "-H",f"ocp-apim-subscription-key: {KEY}",url]
            pr=subprocess.run(cmd,capture_output=True,text=True)
            body,st=pr.stdout.rsplit("\\n__STATUS__:",1) if "\\n__STATUS__:" in pr.stdout else (pr.stdout,"000")
            rec={"includeCpos":inc,"locationStatus":status,"status":int(st)}
            try:
                jd=json.loads(body)
                rec["keys"]=sorted(jd.keys()) if isinstance(jd,dict) else []
                rec["locations"]=len(jd.get("locations") or []) if isinstance(jd,dict) else None
                if isinstance(jd,dict) and jd.get("locations"):
                    rec["sample"]=[{
                      "id":x.get("id"),"partyId":x.get("partyId"),"coordinates":x.get("coordinates")
                    } for x in (jd.get("locations") or [])[:3]]
            except Exception:
                rec["bodyPrefix"]=body[:160]
            variants.append(rec)
    return {"cpoMatches":matches,"mapVariants":variants}

def main():
    if not KEY:
        raise SystemExit("missing AVIA_APIM_SUBSCRIPTION_KEY")
    out={"schemaVersion":1,"api":API,"tenant":TENANT,"results":[req(p) for p in PATHS],"diagnostics":cpo_and_map_diagnostics()}
    Path("data/reports/avia_picoty_authenticated_bootstrap_probe.json").write_text(
        json.dumps(out,indent=2,ensure_ascii=False)+"\n", encoding="utf-8"
    )
    print(json.dumps(out,indent=2,ensure_ascii=False))
if __name__=="__main__":
    main()
