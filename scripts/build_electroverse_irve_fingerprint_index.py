#!/usr/bin/env python3
import csv, io, json, urllib.request
from pathlib import Path

SOURCE="https://www.data.gouv.fr/api/1/datasets/r/eb76d20a-8501-400e-b336-d85724de5435"
MAP=Path("data/electroverse/irve_location_mapping.json")
OUT=Path("reports/electroverse/irve-fingerprint-index.json")

mapping=json.loads(MAP.read_text())
wanted={str(x.get("irveStationId","")) for x in mapping.get("mappings",[]) if x.get("irveStationId")}
stations={}
request=urllib.request.Request(SOURCE,headers={"User-Agent":"TCC-Electroverse-fingerprint/1.0"})
with urllib.request.urlopen(request,timeout=180) as raw:
    text=io.TextIOWrapper(raw,encoding="utf-8-sig",newline="")
    header=text.readline()
    delimiter=max([",",";","\\t","|"],key=header.count)
    reader=csv.DictReader(chain([header],text),delimiter=delimiter)
    for row in reader:
        station=(row.get("id_station_itinerance") or row.get("id_station_local") or "").strip()
        if station not in wanted:
            continue
        pdc=(row.get("id_pdc_itinerance") or row.get("id_pdc_local") or "").strip()
        try:
            kw=float(str(row.get("puissance_nominale","")).replace(",","."))
        except (TypeError,ValueError):
            continue
        if not pdc or kw<=0:
            continue
        dc=any(str(row.get(k,"")).strip().lower() in {"1","true","oui","yes"} for k in ("prise_type_combo_ccs","prise_type_chademo"))
        item={"pdcId":pdc,"stationId":station,"powerKw":round(kw),"mode":"DC" if dc else "AC"}
        stations.setdefault(station,{"pdcs":[],"text":""})["pdcs"].append(item)
        stations[station]["text"]+=" "+" ".join(str(row.get(k,"")) for k in ("nom_station","adresse_station","nom_enseigne","nom_operateur","nom_amenageur","observations","implantation_station")).upper()

OUT.parent.mkdir(parents=True,exist_ok=True)
OUT.write_text(json.dumps({"schemaVersion":1,"source":SOURCE,"stationCount":len(stations),"stations":stations},ensure_ascii=False),encoding="utf-8")
print(json.dumps({"stations":len(stations),"pdcs":sum(len(x["pdcs"]) for x in stations.values()),"delimiter":delimiter}))
