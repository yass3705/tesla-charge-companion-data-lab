#!/usr/bin/env python3
import urllib.request, subprocess, json
from pathlib import Path
URL="https://wiki.eponet.ch/uploads/images/gallery/2025-07/YWggrafik.png"
p=Path("/tmp/eponet_qr.png")
req=urllib.request.Request(URL,headers={"User-Agent":"Mozilla/5.0"})
with urllib.request.urlopen(req,timeout=30) as r: p.write_bytes(r.read())
cp=subprocess.run(["zbarimg","--quiet","--raw",str(p)],capture_output=True,text=True,timeout=30)
value=cp.stdout.strip()
out={"source":URL,"bytes":p.stat().st_size,"decoded":value,"decoderReturnCode":cp.returncode,"stderr":cp.stderr[:2000]}
Path("docs/switzerland-eponet-qr-example-decoded-2026-09-28.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
print(json.dumps(out,ensure_ascii=False,indent=2))
