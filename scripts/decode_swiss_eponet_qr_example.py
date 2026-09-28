#!/usr/bin/env python3
import urllib.request, subprocess, sys, json
from pathlib import Path
URL="https://wiki.eponet.ch/uploads/images/gallery/2025-07/YWggrafik.png"
p=Path("/tmp/eponet_qr.png")
req=urllib.request.Request(URL,headers={"User-Agent":"Mozilla/5.0"})
with urllib.request.urlopen(req,timeout=30) as r: p.write_bytes(r.read())
try:
 import cv2
except Exception:
 subprocess.check_call([sys.executable,"-m","pip","install","-q","opencv-python-headless"])
 import cv2
img=cv2.imread(str(p))
det=cv2.QRCodeDetector()
value, points, straight=det.detectAndDecode(img)
out={"source":URL,"bytes":p.stat().st_size,"decoded":value,"points":points.tolist() if points is not None else None}
Path("docs/switzerland-eponet-qr-example-decoded-2026-09-28.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
print(json.dumps(out,ensure_ascii=False,indent=2))
