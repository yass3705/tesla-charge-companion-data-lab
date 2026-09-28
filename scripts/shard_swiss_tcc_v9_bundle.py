#!/usr/bin/env python3
import json,re,hashlib
from pathlib import Path
from collections import defaultdict

SRC=Path("data/tcc_v9/switzerland.json")
OUTDIR=Path("data/tcc_v9/switzerland/operators")
MANIFEST=Path("data/tcc_v9/switzerland/manifest.json")
OUTDIR.mkdir(parents=True,exist_ok=True)

if not SRC.exists() or SRC.stat().st_size==0:
    raise SystemExit("missing monolithic Switzerland source bundle")
payload=json.loads(SRC.read_text(encoding="utf-8"))
rows=payload.pop("evses")
groups=defaultdict(list)
for ev in rows:
    op=ev.get("operatorId") or "UNKNOWN"
    groups[op].append(ev)

def safe(s):
    s=re.sub(r"[^A-Za-z0-9._-]+","_",s).strip("_")
    return s or "UNKNOWN"

files=[]
for op,items in sorted(groups.items()):
    fn=safe(op)+".json"
    fp=OUTDIR/fn
    shard={
      "schemaVersion":1,
      "country":"CH",
      "operatorId":op,
      "generatedAt":payload.get("generatedAt"),
      "policy":payload.get("policy"),
      "counts":{
        "evseCount":len(items),
        "directTariffResolvedEvseCount":sum(x.get("directTariffStatus")=="resolved" for x in items),
        "noPublicDirectTariffEvseCount":sum(x.get("directTariffStatus")=="no_public_direct_tariff" for x in items),
        "directTariffUnresolvedEvseCount":sum(x.get("directTariffStatus")=="unresolved" for x in items),
      },
      "evses":items
    }
    raw=(json.dumps(shard,ensure_ascii=False,separators=(",",":"))+"\n").encode()
    fp.write_bytes(raw)
    files.append({
      "operatorId":op,"file":str(fp),"bytes":len(raw),
      "sha256":hashlib.sha256(raw).hexdigest(),
      **shard["counts"]
    })

manifest={
 "schemaVersion":1,
 "dataset":"tcc-v9-switzerland-sharded",
 "generatedAt":payload.get("generatedAt"),
 "country":"CH",
 "nationalSource":payload.get("nationalSource"),
 "policy":payload.get("policy"),
 "counts":payload.get("counts"),
 "operatorShardCount":len(files),
 "sourceStats":payload.get("sourceStats"),
 "cpoResearchStatus":payload.get("cpoResearchStatus"),
 "operatorFiles":files
}
MANIFEST.parent.mkdir(parents=True,exist_ok=True)
MANIFEST.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

# Replace oversized monolith with a stable pointer, preserving backward discoverability.
pointer={
 "schemaVersion":1,
 "dataset":"tcc-v9-switzerland",
 "storage":"sharded",
 "manifest":"data/tcc_v9/switzerland/manifest.json",
 "generatedAt":payload.get("generatedAt"),
 "counts":payload.get("counts"),
 "operatorShardCount":len(files)
}
SRC.write_text(json.dumps(pointer,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

mx=max(files,key=lambda x:x["bytes"])
print(json.dumps({
 "manifest":str(MANIFEST),
 "operatorShardCount":len(files),
 "counts":manifest["counts"],
 "largestShard":mx,
 "pointerBytes":SRC.stat().st_size
},ensure_ascii=False,indent=2))
