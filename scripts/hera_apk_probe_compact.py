#!/usr/bin/env python3
import argparse, hashlib, ipaddress, json, re, zipfile
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
import requests
from androguard.core.apk import APK

PACKAGE='com.siemens.hera.mobility'
VERSION='6.2.15'
CODE='62015'
SHA='05c1d24c96ef16e62cf3e2330e526109ab7df87ccbd687d15312024218791018'
URL_RE=re.compile(rb'https?://[A-Za-z0-9._~:/?#\[\]@!$&\'()*+,;=%{}-]{4,500}',re.I)
ASCII_RE=re.compile(rb'[\x20-\x7e]{4,240}')
RELEVANT=('api','tariff','tariffe','price','pricing','offerta','offer','flat','consumo','charging','charger','station','evse','connector','ocpi','mobility','ricarica','hera','penalty','parking','idle','kwh','minute','location')
SENSITIVE=('secret','api_key','apikey','bearer','access_token','refresh_token','password','passwd','private_key','payment_token','credit_card','session_token')
UNSAFE=('start','stop','delete','remove','activate','deactivate','payment','checkout','purchase','session','command','remote','token','oauth','login','logout','password','register','signup','reset')

def norm(raw):
    try: p=urlsplit(raw.decode('ascii','ignore').rstrip('.,;:)]}\\\"\''))
    except ValueError: return None
    if p.scheme.lower() not in ('http','https') or not p.hostname or p.username or p.password: return None
    path=p.path or '/'
    low=path.casefold()
    if len(path)>300 or any(x in low for x in SENSITIVE): return None
    return urlunsplit((p.scheme.lower(),p.netloc.lower(),path,'',''))

def public(host):
    if host in ('localhost','localhost.localdomain') or host.endswith(('.local','.internal')): return False
    try:
        ip=ipaddress.ip_address(host)
        return not (ip.is_private or ip.is_loopback or ip.is_reserved or ip.is_link_local or ip.is_multicast)
    except ValueError: return True

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--apk',type=Path,required=True); ap.add_argument('--output',type=Path,required=True); ns=ap.parse_args()
    data=ns.apk.read_bytes(); actual=hashlib.sha256(data).hexdigest(); assert actual==SHA,actual
    apk=APK(str(ns.apk)); assert apk.get_package()==PACKAGE; assert str(apk.get_androidversion_name())==VERSION; assert str(apk.get_androidversion_code())==CODE
    certs=[]
    for c in apk.get_certificates():
        der=c.dump(); certs.append({'sha256':hashlib.sha256(der).hexdigest(),'sha1':hashlib.sha1(der).hexdigest()})
    urls=set(); paths={}; scanned=[]; redacted=0
    with zipfile.ZipFile(ns.apk) as z:
        for i in z.infolist():
            low=i.filename.casefold()
            if i.file_size>80_000_000 or not (low.endswith(('.dex','.xml','.json','.txt','.properties','.html','.js')) or low in ('resources.arsc','androidmanifest.xml')): continue
            blob=z.read(i); scanned.append({'path':i.filename,'size':i.file_size,'sha256':hashlib.sha256(blob).hexdigest()})
            for m in URL_RE.finditer(blob):
                u=norm(m.group());
                if u: urls.add(u)
            for m in ASCII_RE.finditer(blob):
                s=m.group().decode('ascii','ignore').strip(); low=s.casefold()
                if any(x in low for x in SENSITIVE) and any(x in s for x in ('=',':',' ')): redacted+=1; continue
                if s.startswith('/') and len(s)<241 and any(x in low for x in RELEVANT): paths[s.split('?',1)[0]]=paths.get(s.split('?',1)[0],0)+1
    urls=sorted(urls); hosts=sorted({urlsplit(u).hostname for u in urls if urlsplit(u).hostname})
    probes=[]; seen=set()
    for u in urls:
        p=urlsplit(u); root=f'https://{p.netloc}/'
        for candidate in (root,u):
            low=urlsplit(candidate).path.casefold()
            if candidate in seen or p.scheme!='https' or not public(p.hostname) or any(x in low for x in UNSAFE): continue
            seen.add(candidate)
            if len(probes)>=40: break
            row={'url':candidate}
            try:
                r=requests.get(candidate,headers={'User-Agent':f'Hera-Ricarica-public-audit/{VERSION}'},timeout=(8,15),allow_redirects=True,stream=True)
                row.update(status=r.status_code,contentType=r.headers.get('content-type'),contentLength=r.headers.get('content-length'),finalUrl=norm(r.url.encode()),redirectCount=len(r.history)); r.close()
            except requests.RequestException as e: row['error']=f'{type(e).__name__}: {e}'
            probes.append(row)
    report={'schemaVersion':'1.0.0','dataset':'hera-ricarica-apk-public-discovery','country':'IT','application':{'package':PACKAGE,'versionName':VERSION,'versionCode':CODE,'apkSha256':actual,'apkSize':len(data),'certificates':sorted(certs,key=lambda x:x['sha256']),'signing':{'v1':apk.is_signed_v1(),'v2':apk.is_signed_v2(),'v3':apk.is_signed_v3()}},'discovery':{'urls':urls,'hosts':hosts,'endpointPaths':[{'path':p,'occurrences':n} for p,n in sorted(paths.items(),key=lambda x:(-x[1],x[0]))],'redactedStringCount':redacted,'scan':{'fileCount':len(scanned),'files':scanned}},'readOnlyProbes':probes,'safety':{'queryStringsPersisted':False,'credentialLikeValuesPersisted':False,'httpMethod':'GET','stateChangingPathsExcluded':True,'privateHostsExcluded':True,'userAccountUsed':False}}
    ns.output.parent.mkdir(parents=True,exist_ok=True); ns.output.write_text(json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'sha256':actual,'hosts':hosts,'urls':len(urls),'paths':len(paths),'probes':len(probes)},ensure_ascii=False))
if __name__=='__main__': main()
