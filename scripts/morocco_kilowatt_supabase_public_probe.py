#!/usr/bin/env python3
"""Sanitized, read-only Kilowatt Morocco Supabase discovery.

Public app client keys are recovered only in memory. No raw key, credential,
account data or unfiltered backend body is persisted. Only safe authentication
outcomes, charging-infrastructure table names/schema keys and whitelisted
public charging fields may be written.
"""
from __future__ import annotations
import base64, datetime as dt, json, re, subprocess, tempfile, urllib.error, urllib.parse, urllib.request, zipfile
from pathlib import Path

PACKAGE="ma.kilowatt.app"; PROJECT_REF="jmrgknphxsviooizyilj"; HOST=f"{PROJECT_REF}.supabase.co"
OUT=Path("artifacts/morocco-kilowatt-supabase"); OUT.mkdir(parents=True,exist_ok=True)
UA="Mozilla/5.0 (compatible; TeslaChargeCompanionPublicResearch/1.1)"
JWT_RE=re.compile(rb"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")
PUB_RE=re.compile(rb"sb_(?:publishable|anon)_[A-Za-z0-9_-]{20,}",re.I)
URL_RE=re.compile(rb"https://[a-z0-9]{20}\.supabase\.co",re.I)
INFRA=("station","charger","charge_point","chargepoint","evse","connector","location","tariff","price","pricing")
SENSITIVE=("user","profile","account","payment","invoice","wallet","customer","auth","session","receipt")
SAFE={"id","name","title","status","availability","available","is_available","power","power_kw","max_power","max_power_kw","latitude","longitude","lat","lng","address","city","country","currency","tariff","tariff_id","price","price_kwh","price_per_kwh","price_per_minute","idle_price","idle_fee","fixed_starting_fee","free","operator","operator_id","network","network_id","cpo","connector_type","type","station_id","location_id","evse_id","connector_id","updated_at","last_updated"}

def b64json(x:bytes):
 try:
  x+=b"="*(-len(x)%4); return json.loads(base64.urlsafe_b64decode(x).decode("utf-8","replace"))
 except Exception:return {}

def download(dest):
 for fmt in ("XAPK","APK"):
  try:
   q=urllib.request.Request(f"https://d.apkpure.com/b/{fmt}/{PACKAGE}?version=latest",headers={"User-Agent":UA,"Accept":"*/*"})
   with urllib.request.urlopen(q,timeout=120) as r:data=r.read()
   if len(data)>100000: dest.write_bytes(data); return fmt,len(data)
  except Exception:pass
 return None,0

def unzip_safe(src,dst):
 dst.mkdir(parents=True,exist_ok=True)
 try:
  with zipfile.ZipFile(src) as z:
   for i in z.infolist():
    if ".." not in Path(i.filename).parts and i.file_size<180*1024*1024:z.extract(i,dst)
 except Exception:pass

def blobs(root):
 for p in root.rglob("*"):
  if not p.is_file():continue
  try:s=p.stat().st_size
  except OSError:continue
  if s>160*1024*1024:continue
  if p.name in ("index.android.bundle","main.jsbundle","libapp.so","resources.arsc","classes.dex") or p.suffix.lower() in (".json",".js",".txt",".xml"):
   try:yield p.read_bytes()
   except Exception:
    try:yield subprocess.run(["strings","-a",str(p)],capture_output=True,timeout=120).stdout
    except Exception:pass

def discover(bs):
 urls=set(); legacy=[]; publish=[]
 for b in bs:
  for u in URL_RE.findall(b):urls.add(u.decode("ascii","ignore").lower())
  for t in PUB_RE.findall(b):publish.append(t.decode("ascii","ignore"))
  for t in JWT_RE.findall(b):
   parts=t.split(b"."); payload=b64json(parts[1]) if len(parts)==3 else {}
   if str(payload.get("role","")).lower()=="anon":legacy.append((t.decode("ascii","ignore"),payload))
 # dedupe values without ever persisting them
 publish=list(dict.fromkeys(publish)); ded=[]; seen=set()
 for token,p in legacy:
  if token not in seen:seen.add(token);ded.append((token,p))
 return sorted(urls),publish,ded

def safe_error(obj):
 if not isinstance(obj,dict):return None
 out={}
 for k in ("code","message","hint","details","error","error_description"):
  if isinstance(obj.get(k),(str,int,float,bool)):
   v=str(obj[k]); out[k]=v[:300]
 return out or None

def get(url,headers):
 q=urllib.request.Request(url,headers=headers,method="GET")
 try:
  with urllib.request.urlopen(q,timeout=30) as r:status=r.status;ctype=r.headers.get("content-type","");body=r.read(1500000)
 except urllib.error.HTTPError as e:
  status=e.code;ctype=e.headers.get("content-type","") if e.headers else ""
  try:body=e.read(300000)
  except Exception:body=b""
 except Exception as e:return None,"",None,type(e).__name__
 try:obj=json.loads(body.decode("utf-8","replace"))
 except Exception:obj=None
 return status,ctype,obj,None

def safe_sample(obj):
 if not isinstance(obj,list) or not obj or not isinstance(obj[0],dict):return None
 out={}
 for k,v in obj[0].items():
  if str(k).lower() in SAFE and isinstance(v,(str,int,float,bool,type(None))):out[k]=v
 return out or None

def main():
 report={"schema_version":2,"generated_at":dt.datetime.now(dt.timezone.utc).isoformat(),"package":PACKAGE,"policy":{"read_only":True,"no_login":True,"no_mutations":True,"public_client_keys_used_in_memory_only":True,"raw_key_persisted":False,"raw_package_persisted":False,"raw_response_bodies_persisted":False,"account_or_user_tables_queried":False}}
 with tempfile.TemporaryDirectory(prefix="kilowatt-supabase-") as td:
  root=Path(td);pkg=root/"app.pkg";fmt,size=download(pkg);report.update({"download_ok":bool(fmt),"download_format":fmt,"download_bytes":size})
  if not fmt:(OUT/"summary.json").write_text(json.dumps(report,indent=2)+"\n");return
  tree=root/"tree";unzip_safe(pkg,tree)
  for i,a in enumerate(list(tree.rglob("*.apk"))[:30]):unzip_safe(a,tree/f"apk_{i}")
  urls,publish,legacy=discover(list(blobs(tree)))
  now=int(dt.datetime.now(dt.timezone.utc).timestamp())
  legacy_meta=[]
  for _,p in legacy:
   exp=p.get("exp");legacy_meta.append({"role":p.get("role"),"ref_matches_project":p.get("ref")==PROJECT_REF,"claim_names":sorted(p.keys()),"has_exp":isinstance(exp,(int,float)),"expired":bool(isinstance(exp,(int,float)) and exp<now)})
  report["client_context"]={"supabase_project_seen":any(HOST in u for u in urls),"project_hosts":[urllib.parse.urlsplit(u).hostname for u in urls[:10]],"publishable_key_found":bool(publish),"legacy_anon_key_found":bool(legacy),"legacy_anon_candidates":legacy_meta[:5]}
  modes=[]
  if publish:modes.append(("publishable_apikey_only",publish[0],False))
  for token,p in legacy:
   if p.get("ref")==PROJECT_REF:
    modes.extend([("legacy_anon_apikey_only",token,False),("legacy_anon_apikey_and_bearer",token,True)]);break
  base=f"https://{HOST}"; successful=None
  for label,key,bearer in modes:
   h={"User-Agent":UA,"Accept":"application/json","apikey":key}
   if bearer:h["Authorization"]=f"Bearer {key}"
   st,ct,obj,er=get(base+"/rest/v1/",h)
   item={"mode":label,"status":st,"content_type":ct,"error_type":er,"safe_error":safe_error(obj)};report.setdefault("auth_mode_probes",[]).append(item)
   if st==200 and isinstance(obj,dict):successful=(h,obj,label);break
  if successful:
   headers,spec,label=successful;paths=spec.get("paths",{}) if isinstance(spec,dict) else {};tables=[]
   if isinstance(paths,dict):
    for p in paths:
     t=str(p).strip("/");lo=t.lower()
     if t and any(w in lo for w in INFRA) and not any(w in lo for w in SENSITIVE):tables.append(t)
   tables=sorted(set(tables))[:30];report["rest_discovery"]={"successful_mode":label,"charging_infrastructure_tables":tables,"charging_infrastructure_table_count":len(tables)}
   probes=[]
   for table in tables[:12]:
    st,ct,obj,er=get(base+"/rest/v1/"+urllib.parse.quote(table,safe="")+"?limit=1",headers);x={"table":table,"status":st,"content_type":ct,"error_type":er}
    if isinstance(obj,list):
     x["row_count_returned"]=len(obj)
     if obj and isinstance(obj[0],dict):x["field_names"]=sorted(map(str,obj[0].keys()))[:100];sample=safe_sample(obj);x.update({"sanitized_public_sample":sample} if sample else {})
    else:x["safe_error"]=safe_error(obj)
    probes.append(x)
   report["table_probes"]=probes
  else:report["rest_discovery"]={"charging_infrastructure_tables":[],"charging_infrastructure_table_count":0,"blocker":"No recovered public client-key mode authenticated successfully to the REST root."}
 (OUT/"summary.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
 print(json.dumps({"download_ok":report.get("download_ok"),"publishable_key_found":report.get("client_context",{}).get("publishable_key_found"),"legacy_anon_key_found":report.get("client_context",{}).get("legacy_anon_key_found"),"table_count":report.get("rest_discovery",{}).get("charging_infrastructure_table_count")}))
if __name__=="__main__":main()
