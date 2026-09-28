#!/usr/bin/env python3
"""Read-only Swisscharge ad-hoc API probe.

Usage:
  python3 scripts/swisscharge_home_probe.py "/path/to/Swisscharge.xapk"

The script extracts the Swisscharge BuildConfig directly from classes*.dex,
never prints OAuth secrets/tokens, and performs read-only probes only.
"""
import json, os, re, struct, sys, tempfile, urllib.error, urllib.parse, urllib.request, zipfile
from datetime import date
from pathlib import Path

EVSE_IDENTIFIER = os.environ.get("EVSE_IDENTIFIER", "66730")

def uleb(data, pos):
    val=0; shift=0
    while True:
        b=data[pos]; pos+=1; val |= (b & 0x7f) << shift
        if not (b & 0x80): return val,pos
        shift += 7

def dex_strings(d):
    n,off=struct.unpack_from("<II",d,0x38); out=[]
    for i in range(n):
        so=struct.unpack_from("<I",d,off+4*i)[0]; _,p=uleb(d,so); e=d.find(b"\x00",p)
        out.append(d[p:e].decode("utf-8","replace"))
    return out

def buildconfig_from_dex(path):
    d=Path(path).read_bytes(); ss=dex_strings(d)
    type_n,type_off=struct.unpack_from("<II",d,0x40)
    types=[struct.unpack_from("<I",d,type_off+4*i)[0] for i in range(type_n)]
    field_n,field_off=struct.unpack_from("<II",d,0x50)
    fields=[struct.unpack_from("<HHI",d,field_off+8*i) for i in range(field_n)]
    cls_n,cls_off=struct.unpack_from("<II",d,0x60)
    for i in range(cls_n):
        vals=struct.unpack_from("<IIIIIIII",d,cls_off+32*i)
        class_idx,_,_,_,_,_,class_data_off,static_values_off=vals
        if ss[types[class_idx]] != "Lcs/swisscharge/BuildConfig;": continue
        p=class_data_off
        sf,p=uleb(d,p); _,p=uleb(d,p); _,p=uleb(d,p); _,p=uleb(d,p)
        fidx=0; static_fields=[]
        for _ in range(sf):
            diff,p=uleb(d,p); _,p=uleb(d,p); fidx+=diff; static_fields.append(fidx)
        values=[]
        if static_values_off:
            p=static_values_off; count,p=uleb(d,p)
            for _ in range(count):
                head=d[p]; p+=1; typ=head&0x1f; arg=head>>5
                # DEX encoded_value: BOOLEAN and NULL encode their value in
                # value_arg/type only and have zero payload bytes. Advancing
                # one byte here corrupts every following static value.
                if typ==0x1f:
                    values.append(bool(arg))
                    continue
                if typ==0x1e:
                    values.append(None)
                    continue
                nbytes=arg+1
                raw=int.from_bytes(d[p:p+nbytes],"little"); p+=nbytes
                if typ==0x17: values.append(ss[raw])
                elif typ in (0x04,0x06): values.append(raw)
                else: values.append(raw)
        return {ss[fields[fi][2]]: values[j] for j,fi in enumerate(static_fields) if j<len(values)}
    return None

def request(method,url,body=None,form=False,headers=None):
    headers=dict(headers or {})
    data=None
    if body is not None:
        if form:
            data=urllib.parse.urlencode(body).encode()
            headers["Content-Type"]="application/x-www-form-urlencoded"
        else:
            data=json.dumps(body,separators=(",",":")).encode()
            headers["Content-Type"]="application/json"
    req=urllib.request.Request(url,data=data,headers=headers,method=method)
    try:
        with urllib.request.urlopen(req,timeout=30) as r: raw=r.read(); status=r.status
    except urllib.error.HTTPError as e: status=e.code; raw=e.read()
    except Exception as e: return 0,{"transport_error":type(e).__name__+": "+str(e)}
    try: payload=json.loads(raw.decode())
    except Exception: payload={"raw":raw.decode("utf-8","replace")[:1000]}
    return status,payload

def sanitize(x):
    if isinstance(x,dict):
        return {k:("[REDACTED]" if k.lower() in {"access_token","refresh_token","token","client_secret"} else sanitize(v)) for k,v in x.items()}
    if isinstance(x,list): return [sanitize(v) for v in x]
    return x

def main():
    if len(sys.argv)!=2:
        raise SystemExit("Usage: python3 swisscharge_home_probe.py /path/to/Swisscharge.xapk")
    xapk=Path(sys.argv[1]).expanduser()
    if not xapk.exists(): raise SystemExit(f"File not found: {xapk}")
    report={"evse_identifier":EVSE_IDENTIFIER,"token_attempts":[],"location_attempts":[],"tariffs":[]}
    with tempfile.TemporaryDirectory() as td:
        td=Path(td); xd=td/"xapk"; xd.mkdir()
        with zipfile.ZipFile(xapk) as z:z.extractall(xd)
        apks=list(xd.glob("*.apk"))
        base=next((p for p in apks if p.name in ("cs.swisscharge.apk","base.apk")),apks[0])
        ad=td/"apk"; ad.mkdir()
        with zipfile.ZipFile(base) as z:z.extractall(ad)
        cfg=None
        for dex in sorted(ad.glob("classes*.dex")):
            try:
                cfg=buildconfig_from_dex(dex)
                if cfg: break
            except Exception: pass
        if not cfg: raise SystemExit("Could not extract Swisscharge BuildConfig")
        host=cfg.get("HOST_PRIVATE"); public_host=cfg.get("HOST_PUBLIC")
        cid=cfg.get("OAUTH_ID"); secret=cfg.get("OAUTH_SECRET")
        report.update({"app_version":cfg.get("VERSION_NAME"),"host":host,"public_host":public_host,
                       "oauth_client_id_present":bool(cid),"oauth_secret_present":bool(secret)})
        if not all([host,cid,secret]): raise SystemExit("OAuth config incomplete")
        token_body={"client_id":cid,"client_secret":secret,"grant_type":"ad-hoc",
                    "unique_for_device":True,"operatorCountry":"CH"}
        access=None; base_url=None
        headers={"Accept":"application/json","User-Agent":"Swisscharge/4.234.1 (Android)","Accept-Language":"de-CH"}
        for thost in [h for h in (public_host,host) if h]:
            control_status,_=request("GET",f"https://{thost}/api/v1/app/oauth/token",headers=headers)
            report.setdefault("controls",[]).append({"host":thost,"get_token_status":control_status})
            for form in (False,True):
                status,payload=request("POST",f"https://{thost}/api/v1/app/oauth/token",token_body,form=form,headers=headers)
                report["token_attempts"].append({"host":thost,"encoding":"form" if form else "json","status":status,
                                                 "response":sanitize(payload)})
                if isinstance(payload,dict) and payload.get("access_token"):
                    access=payload["access_token"]; base_url=f"https://{thost}/api/v1"; break
            if access: break
        if not access:
            Path(os.environ.get("PROBE_REPORT","swisscharge-home-probe-report.json")).write_text(json.dumps(report,indent=2,ensure_ascii=False))
            print("No token obtained. Sanitized report written.")
            return 2
        auth={"Authorization":"Bearer "+access,"Accept":"application/json","User-Agent":headers["User-Agent"]}
        paths=[
          f"/app/locations/withEVSEIdentifier/{EVSE_IDENTIFIER}?operatorCountry=CH",
          f"/app/locations/withEVSEIdentifier/{EVSE_IDENTIFIER}?operatorCountry=CH&lookupMode=default",
          f"/app/evses/search?search={EVSE_IDENTIFIER}",
        ]
        location=None
        for path in paths:
            s,p=request("GET",base_url+path,headers=auth)
            report["location_attempts"].append({"path":path,"status":s,"body":sanitize(p) if s==200 else sanitize(p)})
            if s==200: location=p; break
        matches=[]
        def walk(x):
            if isinstance(x,dict):
                ident=str(x.get("identifier",""))
                if ident==EVSE_IDENTIFIER or ident.endswith(EVSE_IDENTIFIER): matches.append(x)
                for v in x.values(): walk(v)
            elif isinstance(x,list):
                for v in x: walk(v)
        if location is not None: walk(location)
        ids=list(dict.fromkeys(str(m["id"]) for m in matches if m.get("id") is not None))
        report["evse_ids"]=ids
        for eid in ids[:5]:
            calls=[
              ("tariff-group",f"/app/tariffs/{urllib.parse.quote(eid)}/tariff-group"),
              ("optimised",f"/app/tariffs/optimised/{urllib.parse.quote(eid)}/price-periods"),
              ("tou",f"/app/tariffs/tou/{urllib.parse.quote(eid)}/price-periods"),
              ("standard-tod",f"/app/tariffs/standard-tod/{urllib.parse.quote(eid)}/price-periods?date={date.today().isoformat()}"),
            ]
            for kind,path in calls:
                s,p=request("GET",base_url+path,headers=auth)
                report["tariffs"].append({"evse_id":eid,"kind":kind,"status":s,"body":sanitize(p)})
        Path(os.environ.get("PROBE_REPORT","swisscharge-home-probe-report.json")).write_text(json.dumps(report,indent=2,ensure_ascii=False))
        print("Probe complete. Sanitized report written.")
        print("token=OK; evse_matches=",len(ids)," tariff_calls=",len(report["tariffs"]))
        return 0

if __name__=="__main__":
    raise SystemExit(main())
