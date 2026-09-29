#!/usr/bin/env python3
import gzip, json, re, requests
from pathlib import Path

BASE="https://nextcharge.app.apis.goelectricstations.com/apis"
PUN=Path("data/national/pun_italy_national.json.gz")
OUT=Path("data/reports/nextcharge_ges_uid_probe.json")
HEAD={"User-Agent":"NextCharge/6.2.02 Android","Content-Type":"application/x-www-form-urlencoded"}

def post(path,data):
    try:
        r=requests.post(BASE+path,data=data,headers=HEAD,timeout=(8,20))
        row={"httpStatus":r.status_code,"contentType":r.headers.get("content-type")}
        try: row["json"]=r.json()
        except Exception: row["textPrefix"]=r.text[:1000]
        return row
    except Exception as e:
        return {"error":f"{type(e).__name__}: {e}"}

def list_data(resp):
    o=resp.get("json") if isinstance(resp,dict) else None
    if not isinstance(o,dict) or o.get("status")!="OK": return []
    d=o.get("data")
    if isinstance(d,list): return d
    if isinstance(d,dict):
        for k in ("results","stations","data","connectors"):
            if isinstance(d.get(k),list): return d[k]
    return []

pun=json.loads(gzip.decompress(PUN.read_bytes()))
ges=[e for e in pun.get("evses",[]) if isinstance(e,dict) and e.get("partyId")=="GES" and e.get("evseId") and isinstance(e.get("coordinates"),list)]
sample=[]
seen=set()
for e in ges:
    sid=str(e.get("stationId") or "")
    if sid in seen: continue
    seen.add(sid); sample.append(e)
    if len(sample)>=8: break

rows=[]
for e in sample:
    ev=str(e["evseId"]); lat=float(e["coordinates"][0]); lon=float(e["coordinates"][1])
    vals=[ev]
    if ev.startswith("ITGES"):
        tail=ev[5:]
        vals.append("IT*GES*"+tail)
    m=re.search(r"(\d+)$",ev)
    if m: vals.append(m.group(1))
    vals=list(dict.fromkeys(vals))
    attempts=[]
    for uid in vals:
        form={
          "lonSW":str(lon-0.02),"latSW":str(lat-0.02),
          "lonNE":str(lon+0.02),"latNE":str(lat+0.02),
          "statusStation":"","UID":uid,"includeNextcharge":"1","includeHighway":"1",
          "favorites":"0","filterStations":"",
          "osType":"android","appVersion":"6.2.02","tokenAppSessionForStations":"",
        }
        resp=post("/stationsGrid",form)
        stations=list_data(resp)
        chains=[]
        for st in stations[:20]:
            if not isinstance(st,dict): continue
            sid=st.get("idStation") or st.get("stationId") or st.get("id")
            if sid is None: continue
            cr=post("/stationConnectors",{"idStation":str(sid),"limit":"100","offset":"0","osType":"android","appVersion":"6.2.02","tokenAppSessionForStations":""})
            conns=list_data(cr)
            chains.append({
              "idStation":sid,
              "provider":st.get("provider"),
              "connectorIdentities":[{
                "uidConnector":c.get("uidConnector"),
                "physicalReference":c.get("physicalReference")
              } for c in conns if isinstance(c,dict)]
            })
        attempts.append({"UID":uid,"status":(resp.get("json") or {}).get("status") if isinstance(resp,dict) and isinstance(resp.get("json"),dict) else None,"stationCount":len(stations),"chains":chains})
    rows.append({"evseId":ev,"stationId":e.get("stationId"),"attempts":attempts})

report={"scope":"GES exact stationsGrid UID lookup probe","gesPunEvseCount":len(ges),"sampleCount":len(sample),"results":rows,"security":{"credentialsUsed":False,"paymentAttempted":False,"chargingStarted":False}}
OUT.parent.mkdir(parents=True,exist_ok=True)
OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
print(json.dumps(report,ensure_ascii=False,indent=2)[:180000])
