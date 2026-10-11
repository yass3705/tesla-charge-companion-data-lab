#!/usr/bin/env python3
"""Match Agri Go first-party public Wordpress map markers with exact DOT-NL AGO EVSEs.

Only strict geodesic 10m with single official marker candidate, using the
official operator site's own markers, no station tariff inference. All distances
and exact underlying EVSE IDs retained in audit CSV and summary. Public-map
visibility alone does not validate physical accessibility nor working QR.
"""
from __future__ import annotations
import csv
import datetime as dt
import html
import json
import math
import re
import urllib.request
from collections import Counter,defaultdict
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/"reports/netherlands/nl-cpo-unpriced-evse-inventory-2026-10-11.csv"
SUMMARY=ROOT/"reports/netherlands/nl-agrigo-official-map-match-2026-10-11.json"
CSV=ROOT/"reports/netherlands/nl-agrigo-official-map-match-2026-10-11.csv"
URL="https://agrigo.nl/charge/locaties/"
def hav_m(x1,y1,x2,y2):
    r=6371000
    a1=math.radians(x1);a2=math.radians(x2)
    dx=a2-a1;dy=math.radians(y2-y1)
    z=math.sin(dx/2)**2+math.cos(a1)*math.cos(a2)*math.sin(dy/2)**2
    return 2*r*math.asin(min(1,math.sqrt(z)))

def operator_markers(raw):
    dec=json.JSONDecoder()
    byid={}
    errors=0
    for m in re.finditer(r'\{"id":"[0-9]+","title":',raw):
        try:
            data,n=dec.raw_decode(raw[m.start():])
            if not isinstance(data,dict):continue
            a=float(data.get("coord_x"));b=float(data.get("coord_y"))
            if not (50<a<54 and 3<b<8): continue
            mid=str(data["id"])
            item={"mapMarkerId":mid,"name":str(data.get("title") or ""),
                  "address":str(data.get("address") or ""),
                  "lat":a,"lon":b,"markerGroupId":str(data.get("marker_group_id") or ""),
                  "iconId":str(data.get("icon") or "")}
            # Some markers embedded twice by WP (frontend initialization + JSON).
            if mid in byid and byid[mid]!=item:raise ValueError("Conflicting duplicate marker "+mid)
            byid[mid]=item
        except (ValueError,TypeError,json.JSONDecodeError):
            errors+=1
    return list(byid.values()),errors

def name_tokens(value):
    # Street/site tokens only: no city/postal code from the full address.
    base=str(value or "").split(",")[0].split("\t")[0].casefold()
    return {t for t in re.findall(r"[a-zà-ÿ][a-zà-ÿ'-]{4,}",base)
            if t not in {"hotel","charge","laadpaal","station","parking","laadpunt","nieuw"}}

def verified_street_alignment(source_name, marker):
    source=name_tokens(source_name)
    official=name_tokens(marker.get("name","")) | name_tokens(marker.get("address",""))
    return bool(source & official)

def main():
    req=urllib.request.Request(URL,headers={"User-Agent":"Mozilla/5.0 TCC-public-operator-map-exact-location-audit","Accept":"text/html"})
    with urllib.request.urlopen(req,timeout=35) as resp:
        raw=resp.read(3_000_000).decode("utf8","replace")
        status=resp.status
    marks,parse_errors=operator_markers(raw)
    with SOURCE.open("r",encoding="utf8",newline="") as f:rows=[r for r in csv.DictReader(f) if r["partyId"]=="AGO"]
    stations=defaultdict(list)
    for row in rows:stations[row["stationId"]].append(row)
    assert len(stations)==927 and len(rows)==2578
    result=[]
    statuscounts=Counter()
    exact_connector_counts=Counter()
    sample={}
    for sid,ss in stations.items():
        ex=ss[0];lat=float(ex["latitude"]);lon=float(ex["longitude"])
        close=sorted([(hav_m(lat,lon,m["lat"],m["lon"]),m) for m in marks if abs(m["lat"]-lat)<.002 and abs(m["lon"]-lon)<.004],key=lambda pair:pair[0])
        strict=[x for x in close if x[0]<=10.0]
        if len(strict)==1:
            chosen=strict[0]
            if verified_street_alignment(ex["name"],chosen[1]):
                rank="unique_strict_gps_and_street_10m"
            else:
                # Even 4 metres can match a neighbouring street or a second
                # charger. Retain for review, never treat as exact identity.
                rank="unique_gps_10m_street_unverified"
        elif len(strict)>1:
            rank="ambiguous_multiple_map_markers_10m";chosen=None
        elif close and close[0][0]<=30.0:
            rank="near_30m_unverified";chosen=close[0]
        else:
            rank="no_operator_map_marker_nearby";chosen=None
        statuscounts[rank]+=1
        exact_connector_counts[rank]+=len(ss)
        m=chosen[1] if chosen else {}
        row={"stationId":sid,"sourceStationName":ex["name"],"city":ex["city"],
            "postalCode":ex["postalCode"],"latitude":lat,"longitude":lon,
            "exactSourceConnectorCount":len(ss),
            "exactSourceEvseIds":";".join(sorted({c["evseId"] for c in ss})),
            "operatorMarkerStatus":rank,"mapMarkerId":m.get("mapMarkerId",""),
            "mapMarkerTitle":m.get("name",""),"mapMarkerAddress":m.get("address",""),
            "mapMarkerGroupId":m.get("markerGroupId",""),
            "mapIconId":m.get("iconId",""),
            "gpsMatchMeters":round(chosen[0],2) if chosen else "",
            "exactGuestQrUrlVerified":False,"exactCpoGuestKwhTariff":"UNVERIFIED",
            "priceSource":"none; public map is NOT the QR checkout"}
        result.append(row)
        if len(sample.get(rank,[]))<5:
            sample.setdefault(rank,[]).append({k:row[k] for k in ("stationId","sourceStationName","operatorMarkerStatus","mapMarkerTitle","gpsMatchMeters","exactSourceConnectorCount")})
    assert sum(statuscounts.values())==927
    assert sum(exact_connector_counts.values())==2578
    with CSV.open("w",encoding="utf8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(result[0]));w.writeheader()
        w.writerows(sorted(result,key=lambda r:(r["operatorMarkerStatus"],r["city"],r["stationId"])))
    report={
        "generatedAt":dt.datetime.now(dt.timezone.utc).isoformat(),
        "operator":"Agri Go Charge","officialMap":URL,"officialMapHttpStatus":status,
        "operatorMapMarkers":len(marks),"markerParsingErrors":parse_errors,
        "sourceStations":len(stations),"sourceConnectors":len(rows),
        "matchStationsByClass":dict(statuscounts),
        "matchConnectorsByClass":dict(exact_connector_counts),
        "sampleByClass":sample,
        "siteIdentityProvenance":"first-party map exact GPS location; no public QR price",
        "uniquenessPolicy":"only unique official marker <=10m with an independently matching source street token can be promoted to first-party site match. Neighbouring street/name mismatch remains unverified even at 4m. Multiple candidates fail closed; 10–30m unverified.",
        "notForV9DirectPrice":True,"matchedConnectorPricePromoted":0,
        "csv":"reports/netherlands/nl-agrigo-official-map-match-2026-10-11.csv"
    }
    SUMMARY.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    print(json.dumps({"mapMarkers":len(marks),"parsingErrors":parse_errors,
      "stations":dict(statuscounts),"connectors":dict(exact_connector_counts)},indent=2))

if __name__=="__main__":main()
