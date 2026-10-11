#!/usr/bin/env python3
"""Read-only investigation of Agri Go Charge exact direct QR payment tariff discovery.

Fetch the public operator pages for explicit QR payment URLs (not production
session-start links), inventory 2,578 physical connector identities, and
sample AC and DC EVSEs. Do not brute force guessed payment URLs, use credentials,
or create a charging session. Inspect published HTML only.
"""
from __future__ import annotations
import collections
import csv
import datetime as dt
import html
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
INV=ROOT/"reports/netherlands/nl-cpo-unpriced-evse-inventory-2026-10-11.csv"
OUT=ROOT/"reports/netherlands/nl-agrigo-qr-endpoint-discovery-2026-10-11.json"
SITE=[
 "https://agrigo.nl/charge/tarieven/",
 "https://agrigo.nl/charge/locaties/",
 "https://agrigo.nl/charge/particulier/",
 "https://agrigo.nl/charge/"
]
class Links(HTMLParser):
    def __init__(self): super().__init__();self.found=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        for k in ("src","href","data-src","data-href","action"):
            u=a.get(k)
            if u and tag in ("script","a","iframe","form"):
                self.found.append((tag,k,u))

def page_probe(u):
    summary={"url":u,"status":None,"resolvedUrl":None,"bytes":0,
             "taggedPaymentLinkCount":0,"paymentLinks":[],"scriptSources":[],
             "iframeSources":[],"explicitEVSEIdInHtml":False,"note":""}
    req=urllib.request.Request(u,headers={"User-Agent":"Mozilla/5.0 (compatible; TCC-AgriPublicSourceAudit/1.0)",
          "Accept":"text/html,application/xhtml+xml","Accept-Language":"nl,en;q=0.8"})
    try:
        with urllib.request.urlopen(req,timeout=18) as resp:
            body=resp.read(2_000_000);summary["status"]=resp.status
            summary["resolvedUrl"]=resp.geturl();summary["bytes"]=len(body)
        text=body.decode("utf-8","replace")
        parser=Links();parser.feed(text)
        for tag,k,value in parser.found:
            url=urllib.parse.urljoin(summary["resolvedUrl"],html.unescape(value))
            if tag=="script" and url.startswith("http"):
                summary["scriptSources"].append(url)
            elif tag=="iframe" and url.startswith("http"):
                summary["iframeSources"].append(url)
            if (tag=="a" or tag=="form" or tag=="iframe") and re.search(r"payment|betaal|direct.?pay|checkout|ad.?hoc|webapp|qr.?code|\bcharge\b",url,re.I):
                summary["paymentLinks"].append({"tag":tag,"url":url[:400]})
        summary["scriptSources"]=list(dict.fromkeys(summary["scriptSources"]))[:30]
        summary["iframeSources"]=list(dict.fromkeys(summary["iframeSources"]))[:25]
        summary["paymentLinks"]=list({v["url"]:v for v in summary["paymentLinks"]}.values())[:40]
        summary["taggedPaymentLinkCount"]=len(summary["paymentLinks"])
        summary["explicitEVSEIdInHtml"]=bool(re.search(r"NL\*AGO\*E\d+",text))
        if not summary["paymentLinks"]:
            summary["note"]="No direct QR/pay link to exact physical charger in public operator page HTML"
    except Exception as e:
        summary["note"]=type(e).__name__+": "+str(e)[:300]
    return summary

def main():
    with INV.open("r",encoding="utf8",newline="") as f:
        rows=[x for x in csv.DictReader(f) if x["partyId"]=="AGO"]
    assert len(rows)==2578,len(rows)
    stations=collections.defaultdict(list)
    power=collections.Counter()
    for x in rows:
        stations[x["stationId"]].append(x)
        power[(x["connectorKind"],x["powerKw"])]+=1
    assert len(stations)==927
    sample=[]; seen=set()
    for kind in ("AC","DC"):
        for sid,group in stations.items():
            matching=[x for x in group if x["connectorKind"]==kind and x["evseStatus"] in ("AVAILABLE","CHARGING")]
            if not matching or sid in seen:continue
            x=matching[0];seen.add(sid)
            sample.append({k:x[k] for k in ("stationId","name","city","postalCode","evseId","connectorId","connectorKind","powerKw","latitude","longitude")})
            if sum(x["connectorKind"]==kind for x in sample)>=5:break
    report={
        "generatedAt":dt.datetime.now(dt.timezone.utc).isoformat(),
        "sourceSnapshotAt":"2026-10-10T09:55:33.004217Z",
        "operator":"Agri Go Charge (AGO)",
        "scope":{"stations":len(stations),"exactUnpricedConnectors":len(rows)},
        "sampleExactStations":sample,
        "publicSourceProbes":[page_probe(u) for u in SITE],
        "publicOfficialPricingUrl":"https://agrigo.nl/charge/tarieven/",
        "operatorAppGooglePlay":"https://play.google.com/store/apps/details?id=com.agrisnellaad.app",
        "lastMileSolutionsWhiteLabelDeveloper":"Last Mile Solutions (Google Play)",
        "lastMileSolutionsDirectCpoWebApp":"https://www.lastmilesolutions.com/legal/gtcfo/",
        "vendorEvidencePolicy":"App developer is NOT proof Agri Go QR uses the Last Mile Solutions CPO direct-payment vendor; do not substitute white-label LMS app roaming prices for the operator's QR guest checkout",
        "notAnExactPriceSource":"Web price table lists indicative classes but says rates vary by site; published illustration QR is not a real physical charger QR.",
        "exactQrTemplate":None,
        "qrTariffEndpointStatus":"unconfirmed_unless_public_page_exposes_live_exact_station_url",
        "pricingPublishedCount":0,
        "noSessionStarted":True,
        "noPaymentAttempted":True,
        "noGuessedEndpointOrEnumerativeProbes":True
    }
    OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    print(json.dumps({k:v for k,v in report.items() if k not in ("publicSourceProbes","sampleExactStations")} |
        {"probeSummary":[{"url":x["url"],"http":x["status"],"paymentLinks":x["paymentLinks"],"iframeSources":x["iframeSources"],"note":x["note"]} for x in report["publicSourceProbes"]],
         "sampleExactStations":len(sample)},ensure_ascii=False,indent=2))

if __name__=="__main__":main()
