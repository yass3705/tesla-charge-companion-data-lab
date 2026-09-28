#!/usr/bin/env python3
from __future__ import annotations
import json,re,subprocess
from pathlib import Path
URL="https://apkcombo.com/totalenergies-charge/com.totalenergies.chargeplus/download/apk"
OUT=Path("reports/belgium/totalenergies")
OUT.mkdir(parents=True,exist_ok=True)
p=subprocess.run(["curl","-LsS","-A","Mozilla/5.0",URL],capture_output=True,text=True)
html=p.stdout
needles=["download","play.googleapis","data-dt","variant","version","package_name","server","token"]
snips=[]
low=html.lower()
for n in needles:
    start=0
    while True:
        i=low.find(n,start)
        if i<0: break
        s=html[max(0,i-800):min(len(html),i+1800)]
        if s not in snips: snips.append(s)
        start=i+len(n)
        if len(snips)>=120: break
    if len(snips)>=120: break
urls=sorted(set(re.findall(r"https?://[^\"'<>\\s]+",html)))
interesting=[u for u in urls if any(x in u.lower() for x in ("googleapis","download","apkcombo","apk"))]
out={"url":URL,"bytes":len(html),"snippets":snips[:120],"interestingUrls":interesting[:500]}
(OUT/"apkcombo-download-contract-2026-09-28.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({"bytes":len(html),"snippetCount":len(snips),"interestingUrls":interesting[:100]},ensure_ascii=False,indent=2))
