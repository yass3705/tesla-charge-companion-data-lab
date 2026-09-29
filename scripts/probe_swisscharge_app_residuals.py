#!/usr/bin/env python3
import json,struct,tempfile,urllib.request,urllib.parse,urllib.error,zipfile
from datetime import date,datetime,timezone
from pathlib import Path

SRC=Path("docs/switzerland-swisscharge-prefix-closeout-2026-09-28.json")
OUT=Path("docs/switzerland-swisscharge-app-residual-probe-2026-09-29.json")
XAPK=Path("/tmp/swisscharge.xapk")

def uleb(data,pos):
    val=0;shift=0
    while True:
        b=data[pos];pos+=1;val|=(b&0x7f)<<shift
        if not b&0x80:return val,pos
        shift+=7

def dex_strings(d):
    n,off=struct.unpack_from("<II",d,0x38);out=[]
    for i in range(n):
        so=struct.unpack_from("<I",d,off+4*i)[0];_,p=uleb(d,so);e=d.find(b"\x00",p)
        out.append(d[p:e].decode("utf-8","replace"))
    return out

def buildconfig(path):
    d=Path(path).read_bytes();ss=dex_strings(d)
    tn,to=struct.unpack_from("<II",d,0x40);types=[struct.unpack_from("<I",d,to+4*i)[0] for i in range(tn)]
    fn,fo=struct.unpack_from("<II",d,0x50);fields=[struct.unpack_from("<HHI",d,fo+8*i) for i in range(fn)]
    cn,co=struct.unpack_from("<II",d,0x60)
    for i in range(cn):
        vals=struct.unpack_from("<IIIIIIII",d,co+32*i);class_idx,_,_,_,_,_,cdo,svo=vals
        if ss[types[class_idx]]!="Lcs/swisscharge/BuildConfig;":continue
        p=cdo;sf,p=uleb(d,p);_,p=uleb(d,p);_,p=uleb(d,p);_,p=uleb(d,p)
        fidx=0;sfs=[]
        for _ in range(sf):
            diff,p=uleb(d,p);_,p=uleb(d,p);fidx+=diff;sfs.append(fidx)
        values=[]
        if svo:
            p=svo;count,p=uleb(d,p)
            for _ in range(count):
                head=d[p];p+=1;typ=head&0x1f;arg=head>>5
                if typ==0x1f:values.append(bool(arg));continue
                if typ==0x1e:values.append(None);continue
                nb=arg+1;raw=int.from_bytes(d[p:p+nb],"little");p+=nb
                values.append(ss[raw] if typ==0x17 else raw)
        return {ss[fields[fi][2]]:values[j] for j,fi in enumerate(sfs) if j<len(values)}
    return None

def request(method,url,body=None,form=False,headers=None):
    headers=dict(headers or {});data=None
    if body is not None:
        if form:
            data=urllib.parse.urlencode(body).encode();headers["Content-Type"]="application/x-www-form-urlencoded"
        else:
            data=json.dumps(body,separators=(",",":")).encode();headers["Content-Type"]="application/json"
    req=urllib.request.Request(url,data=data,headers=headers,method=method)
    try:
        with urllib.request.urlopen(req,timeout=30) as r:raw=r.read();st=r.status
    except urllib.error.HTTPError as e:st=e.code;raw=e.read()
    except Exception as e:return 0,{"transport_error":type(e).__name__+": "+str(e)}
    try:return st,json.loads(raw.decode())
    except:return st,{"raw":raw.decode("utf-8","replace")[:1000]}

def safe(x):
    if isinstance(x,dict):return {k:("[REDACTED]" if k.lower() in {"access_token","refresh_token","token","client_secret"} else safe(v)) for k,v in x.items()}
    if isinstance(x,list):return [safe(v) for v in x]
    return x

if not XAPK.exists():raise SystemExit("missing /tmp/swisscharge.xapk")
with tempfile.TemporaryDirectory() as td:
    td=Path(td);xd=td/"x";xd.mkdir()
    with zipfile.ZipFile(XAPK) as z:z.extractall(xd)
    apks=list(xd.glob("*.apk"));base=next((p for p in apks if p.name in ("cs.swisscharge.apk","base.apk")),apks[0])
    ad=td/"apk";ad.mkdir()
    with zipfile.ZipFile(base) as z:z.extractall(ad)
    cfg=None
    for dex in sorted(ad.glob("classes*.dex")):
        try:
            cfg=buildconfig(dex)
            if cfg:break
        except:pass
if not cfg:raise SystemExit("BuildConfig not found")
host=cfg.get("HOST_PRIVATE");public_host=cfg.get("HOST_PUBLIC");cid=cfg.get("OAUTH_ID");secret=cfg.get("OAUTH_SECRET")
headers={"Accept":"application/json","User-Agent":"Swisscharge/4.234.1 (Android)","Accept-Language":"de-CH"}
token_body={"client_id":cid,"client_secret":secret,"grant_type":"ad-hoc","unique_for_device":True,"operatorCountry":"CH"}
access=None;base_url=None;token_attempts=[]
for thost in [h for h in (public_host,host) if h]:
    for form in (False,True):
        st,p=request("POST",f"https://{thost}/api/v1/app/oauth/token",token_body,form=form,headers=headers)
        token_attempts.append({"host":thost,"encoding":"form" if form else "json","status":st,"response":safe(p)})
        if isinstance(p,dict) and p.get("access_token"):
            access=p["access_token"];base_url=f"https://{thost}/api/v1";break
    if access:break
if not access:raise SystemExit("anonymous app token not obtained")
auth={"Authorization":"Bearer "+access,"Accept":"application/json","User-Agent":headers["User-Agent"]}
refs=[str(x["physicalReference"]) for x in json.loads(SRC.read_text()).get("unresolved",[])]
rows=[]
for ref in refs:
    attempts=[];location=None
    paths=[
      f"/app/locations/withEVSEIdentifier/{urllib.parse.quote(ref)}?operatorCountry=CH",
      f"/app/locations/withEVSEIdentifier/{urllib.parse.quote(ref)}?operatorCountry=CH&lookupMode=default",
      f"/app/evses/search?search={urllib.parse.quote(ref)}"
    ]
    for path in paths:
        st,p=request("GET",base_url+path,headers=auth);attempts.append({"path":path,"status":st,"body":safe(p)})
        if st==200:location=p;break
    matches=[]
    def walk(x):
        if isinstance(x,dict):
            ident=str(x.get("identifier",""))
            if ident==ref or ident.endswith(ref):matches.append(x)
            for v in x.values():walk(v)
        elif isinstance(x,list):
            for v in x:walk(v)
    if location is not None:walk(location)
    ids=list(dict.fromkeys(str(m["id"]) for m in matches if m.get("id") is not None))
    tariffs=[]
    for eid in ids[:5]:
        calls=[
          ("tariff-group",f"/app/tariffs/{urllib.parse.quote(eid)}/tariff-group"),
          ("optimised",f"/app/tariffs/optimised/{urllib.parse.quote(eid)}/price-periods"),
          ("tou",f"/app/tariffs/tou/{urllib.parse.quote(eid)}/price-periods"),
          ("standard-tod",f"/app/tariffs/standard-tod/{urllib.parse.quote(eid)}/price-periods?date={date.today().isoformat()}")
        ]
        for kind,path in calls:
            st,p=request("GET",base_url+path,headers=auth);tariffs.append({"evseId":eid,"kind":kind,"status":st,"body":safe(p)})
    rows.append({"reference":ref,"locationAttempts":attempts,"matches":safe(matches),"evseIds":ids,"tariffs":tariffs})
    print(ref,"matches",len(matches),"tariffCalls",len(tariffs),flush=True)
out={"schemaVersion":1,"country":"CH","operatorId":"CH*SUI","generatedAt":datetime.now(timezone.utc).isoformat(),"appVersion":cfg.get("VERSION_NAME"),"host":host,"publicHost":public_host,"tokenObtained":True,"tokenAttempts":token_attempts,"rows":rows,
"summary":{"total":len(rows),"matchedRefs":sum(1 for r in rows if r["matches"]),"refsWithTariff200":sum(1 for r in rows if any(t["status"]==200 for t in r["tariffs"]))}}
OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
print(json.dumps(out["summary"]))
