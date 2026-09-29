#!/usr/bin/env python3
from __future__ import annotations
import gzip, json, platform, requests
from pathlib import Path

BASE="https://nextcharge.app.apis.goelectricstations.com/apis"
PUN=Path("data/national/pun_italy_national.json.gz")
OUT=Path("data/reports/nextcharge_ges_exact_station_session_probe.json")
UA="NextCharge/6.2.02 Android"
APP_VERSION="6.2.02"
OS_TYPE="android"
OS_VERSION="14"
DEVICE_MODEL="GitHub Actions"

def post(path,data):
    h={"User-Agent":UA,"Content-Type":"application/x-www-form-urlencoded"}
    try:
        r=requests.post(BASE+path,data=data,headers=h,timeout=(8,25))
        row={"httpStatus":r.status_code,"contentType":r.headers.get("content-type")}
        try: row["json"]=r.json()
        except Exception: row["textPrefix"]=r.text[:1000]
        return row
    except Exception as e:
        return {"error":f"{type(e).__name__}: {e}"}

def j(row):
    return row.get("json") if isinstance(row,dict) and isinstance(row.get("json"),dict) else {}

def common():
    return {"osType":OS_TYPE,"appVersion":APP_VERSION}

# APK LS3/b->h AUTH_NEW_USER flow.
start=post("/userSession",{"request":"newUserStartSession",**common()})
so=j(start)
user_id=so.get("userId")
token_app=so.get("token")
ephemeral=so.get("ephemeralDeviceKey")

auth_new=None
device_key=None
if so.get("status")=="AUTH_NEW_USER" and user_id and token_app and ephemeral:
    auth_new=post("/userSession",{
      "request":"newUserAuthSession",
      "tokenAppSession":token_app,
      "ephemeralDeviceKey":ephemeral,
      "deviceModel":DEVICE_MODEL,
      "osType":OS_TYPE,
      "osVersion":OS_VERSION,
      "appVersion":APP_VERSION,
      "lang":"en",
    })
    ao=j(auth_new)
    if ao.get("status")=="OK":
        device_key=ao.get("deviceKey")

# APK LS3/b->d stations-token flow.
stations_session=None
stations_token=None
if user_id and device_key:
    stations_session=post("/userSession",{
      "userId":user_id,
      "request":"authSession",
      "deviceKey":device_key,
      "deviceModel":DEVICE_MODEL,
      "osType":OS_TYPE,
      "osVersion":OS_VERSION,
      "appVersion":APP_VERSION,
      "lang":"en",
      "tokenType":"stations",
    })
    st=j(stations_session)
    if st.get("status")=="OK":
        stations_token=st.get("token")

pun=json.loads(gzip.decompress(PUN.read_bytes()))
ges=[e for e in pun.get("evses",[]) if isinstance(e,dict) and e.get("partyId")=="GES" and e.get("evseId")]
# Include known uidConnector witness plus unresolved examples.
wanted=["ITGESE171731","ITGESE125845134","ITGESE131365937","ITGESE134229802","ITGESE171711","ITGESE1961","ITGESE198784281","ITGESE2204"]
present={str(e["evseId"]) for e in ges}
targets=[x for x in wanted if x in present or x=="ITGESE171731"]

attempts=[]
if stations_token:
    for ev in targets:
        star=("IT*GES*"+ev[5:]) if ev.startswith("ITGES") else ev
        numeric=ev[6:] if ev.startswith("ITGESE") else ev
        cases=[
          ("uid_raw","uidConnector",ev),
          ("uid_star","uidConnector",star),
          ("uid_numeric","uidConnector",numeric),
          ("qr_raw","payloadQrCode",ev),
          ("qr_star","payloadQrCode",star),
          ("qr_numeric","payloadQrCode",numeric),
        ]
        for label,key,value in cases:
            body={key:value,"osType":OS_TYPE,"appVersion":APP_VERSION,"tokenAppSessionForStations":stations_token}
            resp=post("/station",body)
            attempts.append({"evseId":ev,"case":label,"field":key,"value":value,"response":resp})

report={
  "scope":"Exact APK guest bootstrap -> stations token -> /station probe",
  "start":start,
  "authNewUserSession":auth_new,
  "stationsSession":stations_session,
  "stationsTokenObtained":bool(stations_token),
  "targets":targets,
  "attempts":attempts,
  "security":{"credentialsUsed":False,"paymentAttempted":False,"chargingStarted":False},
}
OUT.parent.mkdir(parents=True,exist_ok=True)
OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
print(json.dumps(report,ensure_ascii=False,indent=2)[:180000])
