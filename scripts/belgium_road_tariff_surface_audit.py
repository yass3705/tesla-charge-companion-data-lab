#!/usr/bin/env python3
import json,re
from pathlib import Path
from collections import Counter,defaultdict

SRC=Path("data/belgium/additional/road-2026-09-28.json")
OUT=Path("reports/belgium/belgium-road-tariff-surface-audit-2026-09-29.json")
d=json.loads(SRC.read_text())

key_counts=Counter()
url_counts=Counter()
tariff_key_counts=Counter()
samples=defaultdict(list)

def walk(x,path=""):
    if isinstance(x,dict):
        for k,v in x.items():
            lk=str(k).lower()
            key_counts[lk]+=1
            if any(t in lk for t in ("price","tariff","fee","cost","rate","adhoc","ad_hoc")):
                tariff_key_counts[lk]+=1
                if len(samples[lk])<10:
                    samples[lk].append({"path":path+"/"+str(k),"valueType":type(v).__name__,"valuePreview":str(v)[:300]})
            if any(t in lk for t in ("url","link","qr","web","endpoint")):
                if isinstance(v,str) and v.startswith("http"):
                    host=re.sub(r"^https?://","",v).split("/")[0]
                    url_counts[host]+=1
            walk(v,path+"/"+str(k))
    elif isinstance(x,list):
        for i,v in enumerate(x):
            walk(v,path+f"/{i}")

walk(d)
payload={
 "country":"BE","asOf":"2026-09-29","source":"Road public locations feed",
 "tariffRelatedKeys":tariff_key_counts.most_common(),
 "tariffKeySamples":dict(samples),
 "urlHosts":url_counts.most_common(),
 "topKeys":key_counts.most_common(120),
 "conclusion":"The public Road inventory feed exposes no usable station tariff values if tariffRelatedKeys contains only non-price metadata or is empty."
}
OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n")
print(json.dumps({
 "tariffRelatedKeys":payload["tariffRelatedKeys"][:30],
 "urlHosts":payload["urlHosts"][:30]
},ensure_ascii=False,indent=2))
