#!/usr/bin/env python3
from __future__ import annotations
import json,socket,ssl,time
from pathlib import Path
import requests

OUT=Path("data/reports/nextcharge_ges_network_probe.json")
HOST="nextcharge.app.apis.goelectricstations.com"
BASE=f"https://{HOST}/apis"
EVSE_RAW="ITGESE125845134"
EVSE_STAR="IT*GES*E125845134"

def dns_probe():
    rows=[]
    try:
        for fam,typ,proto,canon,addr in socket.getaddrinfo(HOST,443,type=socket.SOCK_STREAM):
            rows.append({"family":fam,"addr":addr[0]})
    except Exception as e:
        return {"error":f"{type(e).__name__}: {e}"}
    return {"answers":rows}

def tls_probe(ip=None):
    try:
        ctx=ssl.create_default_context()
        with socket.create_connection((ip or HOST,443),timeout=8) as sock:
            with ctx.wrap_socket(sock,server_hostname=HOST) as ss:
                return {"ok":True,"version":ss.version(),"cipher":ss.cipher()[0],"peer":ss.getpeercert().get("subject")}
    except Exception as e:
        return {"ok":False,"error":f"{type(e).__name__}: {e}"}

def post_station(evse):
    # APK 6.2.02 LS3/b.e: station-family requests are multipart/form-data.
    # The method augments the caller map with osType=android and appVersion.
    sess=requests.Session()
    headers={"User-Agent":"NextCharge/6.2.02 Android"}
    attempts=[]
    versions=["6.2.02","6.2.2","60202"]
    for i,app_version in enumerate(versions,1):
        t0=time.time()
        fields={"evseId":evse,"osType":"android","appVersion":app_version}
        files={k:(None,str(v)) for k,v in fields.items()}
        try:
            r=sess.post(BASE+"/station",files=files,headers=headers,timeout=(8,20))
            row={"attempt":i,"appVersion":app_version,"encoding":"multipart/form-data","submittedFields":fields,
                 "elapsed":round(time.time()-t0,3),"httpStatus":r.status_code,"contentType":r.headers.get("content-type")}
            try: row["json"]=r.json()
            except Exception: row["textPrefix"]=r.text[:500]
            attempts.append(row)
            if r.status_code==200 and isinstance(row.get("json"),dict) and row["json"].get("status")=="OK":
                return {"evseId":evse,"attempts":attempts}
        except Exception as e:
            attempts.append({"attempt":i,"appVersion":app_version,"encoding":"multipart/form-data",
                             "elapsed":round(time.time()-t0,3),"error":f"{type(e).__name__}: {e}"})
        time.sleep(1)
    return {"evseId":evse,"attempts":attempts}

def station_id_from(o):
    if not isinstance(o,dict): return None
    if o.get("status")!="OK": return None
    data=o.get("data")
    if isinstance(data,dict):
        return data.get("idStation") or data.get("stationId") or data.get("id")
    if isinstance(data,list):
        for x in data:
            if isinstance(x,dict):
                sid=x.get("idStation") or x.get("stationId") or x.get("id")
                if sid is not None: return sid
    return None

def post_connectors(station_id):
    try:
        fields={"idStation":str(station_id),"limit":"100","offset":"0","osType":"android","appVersion":"6.2.02"}
        r=requests.post(BASE+"/stationConnectors",files={k:(None,str(v)) for k,v in fields.items()},
                        headers={"User-Agent":"NextCharge/6.2.02 Android"},timeout=(8,20))
        row={"httpStatus":r.status_code,"contentType":r.headers.get("content-type")}
        try: row["json"]=r.json()
        except Exception: row["textPrefix"]=r.text[:1000]
        return row
    except Exception as e:
        return {"error":f"{type(e).__name__}: {e}"}

def main():
    dns=dns_probe()
    ips=[x["addr"] for x in dns.get("answers",[]) if ":" not in x["addr"]]
    tls_default=tls_probe()
    tls_ipv4=[{"ip":ip,"result":tls_probe(ip)} for ip in ips[:3]]
    probes=[post_station(EVSE_RAW),post_station(EVSE_STAR)]
    chain=[]
    for p in probes:
        for a in p["attempts"]:
            sid=station_id_from(a.get("json"))
            if sid is not None:
                chain.append({"submittedEvseId":p["evseId"],"stationId":sid,"connectors":post_connectors(sid)})
                break
    report={"scope":"GES NextCharge network+station probe","dns":dns,"tlsDefault":tls_default,"tlsIpv4":tls_ipv4,"stationProbes":probes,"connectorChains":chain}
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(report,ensure_ascii=False,indent=2)[:120000])

if __name__=="__main__": main()
