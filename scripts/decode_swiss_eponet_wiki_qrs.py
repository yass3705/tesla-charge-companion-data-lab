#!/usr/bin/env python3
import urllib.request,subprocess,json,re
from pathlib import Path
from datetime import datetime,timezone
URLS=[
"https://wiki.eponet.ch/uploads/images/gallery/2025-07/YWggrafik.png",
"https://wiki.eponet.ch/uploads/images/gallery/2025-07/5H5grafik.png",
"https://wiki.eponet.ch/uploads/images/gallery/2025-07/img-4818.jpeg",
"https://wiki.eponet.ch/uploads/images/gallery/2025-07/img-4820.jpeg",
"https://wiki.eponet.ch/uploads/images/gallery/2025-07/img-4819.jpeg",
"https://wiki.eponet.ch/uploads/images/gallery/2026-08/enable-public-charger-details.png",
"https://wiki.eponet.ch/uploads/images/gallery/2026-08/public-tab.png",
]
rows=[]
for i,u in enumerate(URLS):
 p=Path(f"/tmp/eponet_img_{i}"+Path(u).suffix)
 try:
  req=urllib.request.Request(u,headers={"User-Agent":"Mozilla/5.0"})
  with urllib.request.urlopen(req,timeout=30) as r:p.write_bytes(r.read())
  cp=subprocess.run(["zbarimg","--quiet","--raw",str(p)],capture_output=True,text=True,timeout=30)
  vals=[x.strip() for x in cp.stdout.splitlines() if x.strip()]
  rows.append({"url":u,"bytes":p.stat().st_size,"decoded":vals,"decoderReturnCode":cp.returncode})
 except Exception as e:
  rows.append({"url":u,"error":type(e).__name__+": "+str(e)})
out={"generatedAt":datetime.now(timezone.utc).isoformat(),"rows":rows}
Path("docs/switzerland-eponet-wiki-qr-batch-2026-09-28.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
print(json.dumps(out,ensure_ascii=False,indent=2))
