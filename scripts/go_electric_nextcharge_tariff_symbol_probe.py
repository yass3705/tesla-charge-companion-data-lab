#!/usr/bin/env python3
"""Targeted read-only discovery of NextCharge connector/tariff frontend symbols."""
from __future__ import annotations
import json,re,urllib.parse,urllib.request
from html.parser import HTMLParser
from pathlib import Path
ROOT="https://nextcharge.app/map?nextcharge=only"
ALLOWED={"nextcharge.app","www.nextcharge.app","nextchargeapp-542e.kxcdn.com"}
USER_AGENT="TeslaChargeCompanion-DataLab/1.0 (+read-only public research)"
NEEDLES=("getTariffs","tariffEMP","showConnectors","showConnectors=function","function showConnectors","currentConnectorsList","selectConnector","gesGlobalRequest","connectorsInfoForStationGeneric","priceRateStandard","connectorsSummary","idConnector","idEVSE","uidConnector","tariff","connector")
FOCUS=("showConnectors=function","function showConnectors","currentConnectorsList","selectConnector","connectorsInfoForStationGeneric","gesGlobalRequest","priceRateStandard","tariffEMP")
class Parser(HTMLParser):
    def __init__(self): super().__init__(); self.scripts=[]
    def handle_starttag(self,tag,attrs):
        if tag.lower()=="script":
            src=dict(attrs).get("src")
            if src:self.scripts.append(src)
def safe(base,value):
    u=urllib.parse.urljoin(base,value); p=urllib.parse.urlparse(u)
    return u if p.scheme=="https" and p.hostname in ALLOWED else None
def get(url):
    u=safe(url,url)
    if not u: raise RuntimeError("disallowed host")
    req=urllib.request.Request(u,headers={"User-Agent":USER_AGENT})
    with urllib.request.urlopen(req,timeout=30) as r:return r.read(12_000_000).decode("utf-8",errors="replace")
def js_urls(text,base):
    out=[]
    for m in re.finditer(r"[\"']([^\"']+\.js(?:\?[^\"']*)?)[\"']",text,re.I):
        u=safe(base,m.group(1))
        if u and u not in out:out.append(u)
    return out
def compact(text,needle,radius=2200,limit=8):
    out=[]; pos=0
    while len(out)<limit:
        pos=text.find(needle,pos)
        if pos<0:break
        s=re.sub(r"\s+"," ",text[max(0,pos-radius):min(len(text),pos+len(needle)+radius)])
        if s not in out:out.append(s)
        pos+=len(needle)
    return out
def candidates(text):
    pats={"pathApiMembers":r"pathAPI\.([A-Za-z0-9_$]{1,80})","hostApiSymbols":r"\b(hostAPI[A-Za-z0-9_$]{1,100})\b","globalRequestActions":r"gesGlobalRequest(?:\.apply\([^\n]{0,300}?\[|\()\s*[\"']([A-Za-z0-9_$-]{1,100})[\"']"}
    out={}
    for name,pat in pats.items():
        vals=[]
        for m in re.finditer(pat,text):
            v=m.group(1)
            if v not in vals:vals.append(v)
            if len(vals)>=200:break
        if vals:out[name]=vals
    return out
def main():
    html=get(ROOT); p=Parser(); p.feed(html); scripts=[]
    for raw in p.scripts+js_urls(html,ROOT):
        u=safe(ROOT,raw)
        if u and u not in scripts:scripts.append(u)
    sources=[]
    for url,text in [(ROOT,html)]+[(u,get(u)) for u in scripts]:
        hits={n:text.count(n) for n in NEEDLES if text.count(n)}
        if not hits:continue
        sources.append({"url":url,"bytes":len(text.encode()),"hitCounts":hits,"candidates":candidates(text),"focusContexts":{n:compact(text,n) for n in FOCUS if n in text}})
    report={"schemaVersion":3,"policy":{"readOnly":True,"authenticated":False,"remoteMutation":False,"discoveredApiCallsExecuted":False,"chargingActionsAllowed":False,"paymentActionsAllowed":False,"reservationActionsAllowed":False},"root":ROOT,"sources":sources}
    out=Path("artifacts/go_electric_nextcharge_tariff_symbol_probe.json");out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps([{"url":s["url"],"hitCounts":s["hitCounts"],"candidates":s["candidates"],"focusContexts":{k:v[:5] for k,v in s["focusContexts"].items()}} for s in sources],ensure_ascii=False,indent=2))
if __name__=="__main__":main()
