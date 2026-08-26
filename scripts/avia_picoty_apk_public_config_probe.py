#!/usr/bin/env python3
import hashlib,json,re,sys,zipfile
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlsplit,urlunsplit

KEYWORDS=[b'deftpower',b'api.deftpower',b'account.deftpower',b'openid',b'oauth',b'picoty',b'aviavolt',b'chargingpoint',b'chargepoint',b'tariff',b'location']
URL_RE=re.compile(rb'https?://[A-Za-z0-9._~:/?#\[\]@!$&\'()*+,;=%-]{3,400}')
DOMAIN_RE=re.compile(r'https?://([^/\s"\'<>]+)',re.I)

def safe_url(raw):
    try:
        s=raw.decode('utf-8','ignore').rstrip('.,);\x00')
        p=urlsplit(s)
        # Keep only scheme/domain/path; redact query/fragment to avoid leaking embedded identifiers/tokens.
        return urlunsplit((p.scheme,p.netloc,p.path,'',''))[:500]
    except Exception: return ''

def printable_context(blob,needle,radius=120):
    low=blob.lower(); out=[]; start=0
    while len(out)<8:
        i=low.find(needle.lower(),start)
        if i<0: break
        c=blob[max(0,i-radius):min(len(blob),i+len(needle)+radius)]
        txt=''.join(chr(x) if 32<=x<127 else ' ' for x in c)
        txt=re.sub(r'\s+',' ',txt).strip()
        # Redact high-entropy/alphanumeric strings commonly used as keys/tokens.
        txt=re.sub(r'(?<![A-Za-z0-9])[A-Za-z0-9_\-]{32,}(?![A-Za-z0-9])','<REDACTED_LONG_TOKEN>',txt)
        out.append(txt[:600]); start=i+len(needle)
    return out

def main(apk_path,out_path):
    p=Path(apk_path); raw=p.read_bytes(); sha=hashlib.sha256(raw).hexdigest()
    report={'schemaVersion':'1.0.0','dataset':'avia-picoty-public-apk-config-probe','generatedAt':datetime.now(timezone.utc).isoformat(),'apk':{'bytes':len(raw),'sha256':sha},'policy':'public_apk_static_config_only_no_credentials_no_authenticated_calls','zip':False,'domains':[],'urls':[],'keywordFindings':[],'entriesScanned':0}
    if not zipfile.is_zipfile(p):
        report['error']='download_is_not_zip_apk_or_xapk'
    else:
        report['zip']=True; urls=set(); domains=Counter(); findings=[]
        with zipfile.ZipFile(p) as z:
            # XAPK can contain one or more nested APKs; scan all zip entries as bytes, including nested APK raw bytes.
            for info in z.infolist():
                if info.file_size>80_000_000: continue
                try: blob=z.read(info)
                except Exception: continue
                report['entriesScanned']+=1
                for m in URL_RE.finditer(blob):
                    u=safe_url(m.group(0))
                    if not u: continue
                    urls.add(u)
                    dm=DOMAIN_RE.match(u)
                    if dm: domains[dm.group(1).lower()]+=1
                low=blob.lower()
                for kw in KEYWORDS:
                    if kw in low:
                        findings.append({'entry':info.filename,'keyword':kw.decode(),'contexts':printable_context(blob,kw)})
        # Filter noisy generic URLs/domains, retain charging/app/API-oriented values + first-party.
        interesting=[]
        for u in sorted(urls):
            lu=u.lower()
            if any(k in lu for k in ['deftpower','picoty','avia','oauth','openid','charge','api','account']): interesting.append(u)
        report['urls']=interesting[:300]
        report['domains']=[{'domain':d,'hits':n} for d,n in domains.most_common() if any(k in d for k in ['deftpower','picoty','avia'])][:100]
        report['keywordFindings']=findings[:250]
    Path(out_path).parent.mkdir(parents=True,exist_ok=True); Path(out_path).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'apk':report['apk'],'zip':report['zip'],'entriesScanned':report['entriesScanned'],'domains':report['domains'],'urls':report['urls'][:40],'findingCount':len(report['keywordFindings']),'error':report.get('error')},ensure_ascii=False,indent=2))
if __name__=='__main__': main(sys.argv[1],sys.argv[2])
