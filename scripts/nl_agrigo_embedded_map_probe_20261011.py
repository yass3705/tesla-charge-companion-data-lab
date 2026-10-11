#!/usr/bin/env python3
"""Public HTML and bundle reconnaissance, no charger control or payment requests.

Inspect first-party map HTML, embedded JS and externally linked *same host*
JS assets for exact AGO EVSEs, map API URLs, location identifiers, and
read-only tariff origins. Small public GETs only, no guessed charger URL.
"""
import datetime as dt
import html
import json
import re
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

P=Path("reports/netherlands/nl-agrigo-embedded-map-probe-2026-10-11.json")
URLS=["https://agrigo.nl/charge/locaties/","https://agrigo.nl/charge/tarieven/",
 "https://agrigo.nl/js/app.a2b628b3.js","https://agrigo.nl/js/chunk-vendors.48197fb4.js"]
PATTERNS=[
 ("EVSE_ID",r"NL\*AGO\*E\d{4,}"),("AGO_PARTY",r"NL[\*:]*AGO"),("BRESKENS",r"Breskens"),
 ("ZIERIKZEE",r"Zierikzee"),("SAMPLE_E10894",r"E10894"),("SAMPLE_E10914",r"E10914"),
 ("API_HTTP",r"https?://[^\s\\x22\x27<>\\]{8,140}"),
 ("API_LABEL",r"(?i)api|chargepoint|evse|tariff|betaal|webapp|qr|powergoodies|lastmile|mapbox"),
 ("LATITUDE",r"(?i)latitude"),("MAP_GEO",r"(?i)geojson|latlng|markercluster|mapapi")]
def fetch(url):
    r={"url":url,"status":None,"bytes":0,"observations":{},"httpError":None}
    try:
        req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 TCC-public-NL-operator-data-inventory","Accept":"text/html,application/javascript,*/*"})
        with urllib.request.urlopen(req,timeout=15) as resp:
            body=resp.read(2_500_000)
            r["status"]=resp.status;r["resolvedUrl"]=resp.geturl()
            ctype=resp.headers.get("content-type","")
            r["contentType"]=ctype
        text=body.decode("utf8","replace");r["bytes"]=len(body)
        for name,pattern in PATTERNS:
            matches=list(re.finditer(pattern,text))
            if name=="API_HTTP":
                candidates=[]
                for m in matches:
                    s=m.group(0);s=html.unescape(s)
                    if re.search(r"api|map|charging|payment|wp-json|lastmile|agrigo|powergoodies",s,re.I):
                        candidates.append(s[:160])
                r["observations"][name]={"count":len(matches),"uniqueCandidates":list(dict.fromkeys(candidates))[:35]}
            elif name=="API_LABEL":
                r["observations"][name]={"count":len(matches),"sampleContexts":[re.sub(r"\s+"," ",text[max(0,m.start()-90):m.end()+100])[:210] for m in matches[:18]]}
            else:
                r["observations"][name]={"count":len(matches),"sampleContexts":[re.sub(r"\s+"," ",text[max(0,m.start()-80):m.end()+140])[:260] for m in matches[:6]]}
        r["publicInlineScriptSizes"]=sorted([len(x) for x in re.findall(r"<script[^>]*>([\s\S]*?)</script>",text,re.I)],reverse=True)[:12]
    except Exception as e:
        r["httpError"]=type(e).__name__+": "+str(e)[:240]
    return r

def main():
    rows=[fetch(u) for u in URLS]
    report={
      "generatedAt":dt.datetime.now(dt.timezone.utc).isoformat(),
      "source":"public Agri Go Charge official website",
      "pageAndBundleFindings":rows,
      "readOnly":True,"noLogin":True,"noPayment":True,"noChargingSession":True,
      "qrExactLinkValidated":False,
      "connectorTariffAmountPublished":False,
      "eMSPPricesNeverUsed":True,
      "important":"Detection of an identifier, public mapping API or posted category price alone cannot establish an exact real QR ad-hoc tariff."
    }
    P.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf8")
    print(json.dumps([{"url":r["url"],"http":r["status"],"bytes":r["bytes"],"hits":{k:v.get("count") for k,v in r["observations"].items()},"inlineScriptSizes":r.get("publicInlineScriptSizes"),"error":r["httpError"]} for r in rows],ensure_ascii=False,indent=2))

if __name__=="__main__":main()
