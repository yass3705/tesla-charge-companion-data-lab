#!/usr/bin/env python3
import json, math, time, urllib.parse, urllib.request, gzip
from pathlib import Path
from datetime import datetime, timezone

OWNER = Path("data/switzerland/ecarup-owner-direct-tariffs.json")
COORD = Path("data/switzerland/ecarup-owner-coordinate-safe-overlay.json")
OVERLAY = Path("data/switzerland/ecarup-residual-name-search-overlay-2026-09-29.json")
REPORT = Path("docs/switzerland-ecarup-residual-name-search-batch-2026-09-29.json")
CANON = Path("docs/switzerland-cpo-progress-2026-09.json")
BASE = "https://ecarup.com/api/stations"
HEADERS = {"User-Agent":"Tesla-Charge-Companion/9","Accept":"application/json"}
BATCH = 1000
NATIONAL_URL = "https://data.geo.admin.ch/ch.bfe.ladestellen-elektromobilitaet/data/oicp/ch.bfe.ladestellen-elektromobilitaet.json"

def norm(s):
    return "".join(c for c in str(s or "").upper() if c.isalnum())

def get_coord(rec):
    if not isinstance(rec, dict):
        return None
    g = (rec.get("GeoCoordinates") or {}).get("Google")
    if isinstance(g, str):
        try:
            a,b = g.replace(","," ").split()[:2]
            return float(a), float(b)
        except Exception:
            pass
    for a,b in (("Latitude","Longitude"),("latitude","longitude")):
        if isinstance(rec.get(a),(int,float)) and isinstance(rec.get(b),(int,float)):
            return float(rec[a]), float(rec[b])
    return None

def distance_m(a,b):
    lat1,lon1=a; lat2,lon2=b
    x=math.radians(lon2-lon1)*math.cos(math.radians((lat1+lat2)/2))
    y=math.radians(lat2-lat1)
    return 6371000*math.sqrt(x*x+y*y)

def candidate_names(rec):
    vals=[]
    def walk(x):
        if isinstance(x,dict):
            for k,v in x.items():
                if isinstance(v,str) and ("name" in k.lower() or k.lower() in ("title","label")):
                    s=v.strip()
                    if 2 <= len(s) <= 140:
                        vals.append(s)
                walk(v)
        elif isinstance(x,list):
            for v in x:
                walk(v)
    walk(rec)
    out=[]; seen=set()
    for s in vals:
        n=norm(s)
        if n and n not in seen and not n.startswith("ECARUP"):
            seen.add(n); out.append(s)
    return out[:8]

def national_plug_codes(rec):
    vals=set()
    if not isinstance(rec,dict):
        return vals
    plugs=rec.get("Plugs") or []
    if isinstance(plugs,str):
        plugs=[plugs]
    for raw in plugs:
        s=str(raw or "").upper()
        if "CHADEMO" in s:
            vals.add(6)
        elif "CCS" in s or "COMBO" in s:
            vals.add(5)
        elif "TYPE 2" in s or "TYPE2" in s:
            vals.add(1)
    return vals

def national_power_types(rec):
    vals=set()
    if not isinstance(rec,dict):
        return vals
    facilities=rec.get("ChargingFacilities") or []
    if isinstance(facilities,dict):
        facilities=[facilities]
    for f in facilities:
        if not isinstance(f,dict):
            continue
        pt=str(f.get("powertype") or "").upper()
        if pt.startswith("AC"):
            vals.add("AC")
        elif pt.startswith("DC"):
            vals.add("DC")
    return vals

def connector_explicit_power_type(conn):
    txt=" ".join(str(conn.get(k) or "") for k in ("Name","name","Description","description")).upper()
    hits=set()
    import re
    if re.search(r"(^|[^A-Z])DC([^A-Z]|$)",txt):
        hits.add("DC")
    if re.search(r"(^|[^A-Z])AC([^A-Z]|$)",txt):
        hits.add("AC")
    return hits

def national_powers_w(rec):
    vals=set()
    if not isinstance(rec,dict):
        return vals
    facilities=rec.get("ChargingFacilities") or []
    if isinstance(facilities,dict):
        facilities=[facilities]
    for f in facilities:
        if not isinstance(f,dict):
            continue
        v=f.get("power")
        try:
            if v is not None:
                vals.add(round(float(v)*1000))
        except Exception:
            pass
    return vals

def fetch_search(term, co):
    q = urllib.parse.urlencode({
        "searchTerm": term,
        "location": f"{co[0]},{co[1]}",
        "includePartners": "true",
        "onlyAvailable": "false",
        "onlyRecentlyUsed": "false"
    })
    req=urllib.request.Request(BASE+"?"+q, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))

def station_name(s):
    return s.get("Name") or s.get("name") or ""

def station_coord(s):
    for a,b in (("Latitude","Longitude"),("latitude","longitude")):
        if isinstance(s.get(a),(int,float)) and isinstance(s.get(b),(int,float)):
            return float(s[a]), float(s[b])
    return None

def connectors(s):
    return s.get("Connectors") or s.get("connectors") or []

def connector_price(c):
    return c.get("Price") or c.get("price")

def connector_access(c):
    return c.get("AccessType", c.get("accessType"))

def download_national_context():
    req=urllib.request.Request(NATIONAL_URL, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=90) as r:
        raw=r.read()
    if len(raw) >= 2 and raw[0] == 31 and raw[1] == 139:
        raw=gzip.decompress(raw)
    root=json.loads(raw.decode("utf-8"))
    contexts={}
    useful_name_keys=("name","title","label")
    coord_keys=("GeoCoordinates","Latitude","Longitude","latitude","longitude")
    def walk(x, inherited_names=None, inherited_coord=None, owner_id=None):
        inherited_names=list(inherited_names or [])
        if isinstance(x,dict):
            if isinstance(x.get("OperatorID"),str):
                owner_id=x.get("OperatorID")
            local_names=list(inherited_names)
            for k,v in x.items():
                lk=k.lower()
                if k == "ChargingStationNames" and isinstance(v,list):
                    for item in v:
                        if isinstance(item,dict) and isinstance(item.get("value"),str):
                            s=item["value"].strip()
                            if 2 <= len(s) <= 160 and norm(s) not in {norm(z) for z in local_names}:
                                local_names.append(s)
                elif isinstance(v,str) and any(t in lk for t in useful_name_keys):
                    s=v.strip()
                    if 2 <= len(s) <= 160 and norm(s) not in {norm(z) for z in local_names}:
                        local_names.append(s)
            local_coord=inherited_coord
            g=(x.get("GeoCoordinates") or {}).get("Google") if isinstance(x.get("GeoCoordinates"),dict) else None
            if isinstance(g,str):
                try:
                    a,b=g.replace(","," ").split()[:2]
                    local_coord=(float(a),float(b))
                except Exception:
                    pass
            if isinstance(x.get("Latitude"),(int,float)) and isinstance(x.get("Longitude"),(int,float)):
                local_coord=(float(x["Latitude"]),float(x["Longitude"]))
            eid=x.get("EvseID")
            if owner_id=="CH*ECU" and isinstance(eid,str):
                contexts[eid]={"names":local_names[-12:],"coord":local_coord}
            for v in x.values():
                walk(v,local_names,local_coord,owner_id)
        elif isinstance(x,list):
            for v in x:
                walk(v,inherited_names,inherited_coord,owner_id)
    walk(root)
    return contexts

national_context=download_national_context()

owner=json.loads(OWNER.read_text(encoding="utf-8"))
coord=json.loads(COORD.read_text(encoding="utf-8")) if COORD.exists() else {}
overlay=json.loads(OVERLAY.read_text(encoding="utf-8")) if OVERLAY.exists() else {
    "schemaVersion":1,"country":"CH","operatorId":"CH*ECU","rows":[]
}

done={r.get("evseId") for r in owner.get("evses",[]) if r.get("evseId")}
done |= {r.get("evseId") for r in coord.get("evses",[]) if r.get("evseId")}
done |= {r.get("evseId") for r in overlay.get("rows",[]) if r.get("evseId")}

remaining=[r for r in owner.get("unresolved",[]) if r.get("evseId") and r.get("evseId") not in done]
promoted=[]; tested=[]; errors=[]

for row in remaining[:BATCH]:
    eid=row["evseId"]
    rec=row.get("nationalRecord") or {}
    ctx=national_context.get(eid) or {}
    co=get_coord(rec) or ctx.get("coord")
    names=candidate_names(rec)
    for s in ctx.get("names") or []:
        if norm(s) and norm(s) not in {norm(x) for x in names} and not norm(s).startswith("ECARUP"):
            names.append(s)
    names=names[:12]
    accepted=None
    if co and names:
        for term in names:
            try:
                arr=fetch_search(term, co)
            except Exception as e:
                errors.append({"evseId":eid,"term":term,"error":str(e)[:200]})
                continue
            if not isinstance(arr,list):
                continue
            term_near=[]
            term_priced=[]
            term_tuples=set()
            for st in arr:
                sc=station_coord(st)
                if not sc or distance_m(co,sc) > 3.0:
                    continue
                term_near.append(st)
                for conn in connectors(st):
                    p=connector_price(conn)
                    if connector_access(conn) in (0,None) and isinstance(p,dict):
                        term_priced.append((st,conn,p))
                        term_tuples.add(json.dumps(p,sort_keys=True,separators=(",",":")))
            if term_priced and len(term_tuples)==1:
                st,conn,p=term_priced[0]
                sc=station_coord(st)
                accepted={
                    "evseId":eid,
                    "stationName":station_name(st),
                    "stationId":st.get("ID") or st.get("id"),
                    "match":"name_search_nearby_identical_public_price_tuple",
                    "distanceMeters":round(distance_m(co,sc),2) if sc else None,
                    "searchTerm":term,
                    "candidateStationCount":len(term_near),
                    "candidatePublicConnectorCount":len(term_priced),
                    "price":p,
                    "connector":{
                        "Id":conn.get("Id") or conn.get("ID") or conn.get("id"),
                        "Name":conn.get("Name") or conn.get("name"),
                        "MaxPower":conn.get("MaxPower") or conn.get("maxPower")
                    }
                }
                break
            matches=[]
            for st in arr:
                sc=station_coord(st)
                if not sc or distance_m(co,sc) > 3.0:
                    continue
                if norm(station_name(st)) != norm(term):
                    continue
                matches.append(st)
            if len(matches) != 1:
                continue
            st=matches[0]
            priced=[]
            for c in connectors(st):
                p=connector_price(c)
                if connector_access(c) in (0,None) and isinstance(p,dict):
                    priced.append(c)
            if len(priced) != 1:
                continue
            c=priced[0]
            accepted={
                "evseId":eid,
                "stationName":station_name(st),
                "stationId":st.get("ID") or st.get("id"),
                "match":"exact_name_and_coordinate_single_connector",
                "distanceMeters":round(distance_m(co,station_coord(st)),2),
                "price":connector_price(c),
                "connector":{
                    "Id":c.get("Id") or c.get("ID") or c.get("id"),
                    "Name":c.get("Name") or c.get("name"),
                    "MaxPower":c.get("MaxPower") or c.get("maxPower")
                }
            }
            break
    if not accepted and co:
        try:
            arr=fetch_search("", co)
        except Exception as e:
            errors.append({"evseId":eid,"term":"","error":str(e)[:200]})
            arr=[]
        exact_id_matches=[]
        if isinstance(arr,list):
            for st in arr:
                for conn in connectors(st):
                    hub=(conn.get("Hubject") or {}).get("ID") if isinstance(conn.get("Hubject"),dict) else None
                    p=connector_price(conn)
                    if norm(hub)==norm(eid) and connector_access(conn) in (0,None) and isinstance(p,dict):
                        exact_id_matches.append((st,conn))
        if len(exact_id_matches)==1:
            st,conn=exact_id_matches[0]
            sc=station_coord(st)
            accepted={
                "evseId":eid,
                "stationName":station_name(st),
                "stationId":st.get("ID") or st.get("id"),
                "match":"exact_hubject_id_from_coordinate_search",
                "distanceMeters":round(distance_m(co,sc),2) if sc else None,
                "price":connector_price(conn),
                "connector":{
                    "Id":conn.get("Id") or conn.get("ID") or conn.get("id"),
                    "Name":conn.get("Name") or conn.get("name"),
                    "MaxPower":conn.get("MaxPower") or conn.get("maxPower"),
                    "HubjectID":(conn.get("Hubject") or {}).get("ID") if isinstance(conn.get("Hubject"),dict) else None
                }
            }

        if not accepted and isinstance(arr,list):
            exact_stations=[]
            for st in arr:
                sc=station_coord(st)
                if sc and distance_m(co,sc) <= 0.75:
                    exact_stations.append(st)
            priced_connectors=[]
            tuple_keys=set()
            for st in exact_stations:
                for conn in connectors(st):
                    p=connector_price(conn)
                    if connector_access(conn) in (0,None) and isinstance(p,dict):
                        priced_connectors.append((st,conn,p))
                        tuple_keys.add(json.dumps(p,sort_keys=True,separators=(",",":")))
            if priced_connectors and len(tuple_keys)==1:
                st,conn,p=priced_connectors[0]
                sc=station_coord(st)
                accepted={
                    "evseId":eid,
                    "stationName":station_name(st),
                    "stationId":st.get("ID") or st.get("id"),
                    "match":"exact_coordinate_identical_public_price_tuple",
                    "distanceMeters":round(distance_m(co,sc),2) if sc else None,
                    "candidateStationCount":len(exact_stations),
                    "candidatePublicConnectorCount":len(priced_connectors),
                    "price":p,
                    "connector":{
                        "Id":conn.get("Id") or conn.get("ID") or conn.get("id"),
                        "Name":conn.get("Name") or conn.get("name"),
                        "MaxPower":conn.get("MaxPower") or conn.get("maxPower"),
                        "HubjectID":(conn.get("Hubject") or {}).get("ID") if isinstance(conn.get("Hubject"),dict) else None
                    }
                }

        if not accepted and isinstance(arr,list):
            near_stations=[]
            for st in arr:
                sc=station_coord(st)
                if sc and distance_m(co,sc) <= 3.0:
                    near_stations.append(st)
            priced_connectors=[]
            tuple_keys=set()
            for st in near_stations:
                for conn in connectors(st):
                    p=connector_price(conn)
                    if connector_access(conn) in (0,None) and isinstance(p,dict):
                        priced_connectors.append((st,conn,p))
                        tuple_keys.add(json.dumps(p,sort_keys=True,separators=(",",":")))
            if priced_connectors and len(tuple_keys)==1:
                st,conn,p=priced_connectors[0]
                sc=station_coord(st)
                accepted={
                    "evseId":eid,
                    "stationName":station_name(st),
                    "stationId":st.get("ID") or st.get("id"),
                    "match":"three_meter_identical_public_price_tuple",
                    "distanceMeters":round(distance_m(co,sc),2) if sc else None,
                    "candidateStationCount":len(near_stations),
                    "candidatePublicConnectorCount":len(priced_connectors),
                    "price":p,
                    "connector":{
                        "Id":conn.get("Id") or conn.get("ID") or conn.get("id"),
                        "Name":conn.get("Name") or conn.get("name"),
                        "MaxPower":conn.get("MaxPower") or conn.get("maxPower"),
                        "HubjectID":(conn.get("Hubject") or {}).get("ID") if isinstance(conn.get("Hubject"),dict) else None
                    }
                }

    if not accepted and co and isinstance(arr,list):
        npowers=national_powers_w(rec)
        if npowers:
            power_matches=[]
            for st in arr:
                sc=station_coord(st)
                if not sc or distance_m(co,sc) > 3.0:
                    continue
                for conn in connectors(st):
                    p=connector_price(conn)
                    mp=conn.get("MaxPower") or conn.get("maxPower")
                    if connector_access(conn) not in (0,None) or not isinstance(p,dict) or not isinstance(mp,(int,float)):
                        continue
                    if round(float(mp)) in npowers:
                        power_matches.append((st,conn,p))
            if len(power_matches)==1:
                st,conn,p=power_matches[0]
                sc=station_coord(st)
                accepted={
                    "evseId":eid,
                    "stationName":station_name(st),
                    "stationId":st.get("ID") or st.get("id"),
                    "match":"unique_exact_power_connector_within_3m",
                    "distanceMeters":round(distance_m(co,sc),2) if sc else None,
                    "nationalPowerW":sorted(npowers),
                    "price":p,
                    "connector":{
                        "Id":conn.get("Id") or conn.get("ID") or conn.get("id"),
                        "Name":conn.get("Name") or conn.get("name"),
                        "MaxPower":conn.get("MaxPower") or conn.get("maxPower"),
                        "HubjectID":(conn.get("Hubject") or {}).get("ID") if isinstance(conn.get("Hubject"),dict) else None
                    }
                }

    if not accepted and co and isinstance(arr,list):
        plugcodes=national_plug_codes(rec)
        npowers=national_powers_w(rec)
        if plugcodes:
            plug_matches=[]
            for st in arr:
                sc=station_coord(st)
                if not sc or distance_m(co,sc) > 3.0:
                    continue
                for conn in connectors(st):
                    p=connector_price(conn)
                    code=conn.get("PlugType") if "PlugType" in conn else conn.get("plugType")
                    mp=conn.get("MaxPower") or conn.get("maxPower")
                    if connector_access(conn) not in (0,None) or not isinstance(p,dict):
                        continue
                    if code not in plugcodes:
                        continue
                    if npowers and isinstance(mp,(int,float)) and round(float(mp)) not in npowers:
                        continue
                    plug_matches.append((st,conn,p))
            if len(plug_matches)==1:
                st,conn,p=plug_matches[0]
                sc=station_coord(st)
                accepted={
                    "evseId":eid,
                    "stationName":station_name(st),
                    "stationId":st.get("ID") or st.get("id"),
                    "match":"unique_validated_plug_and_power_connector_within_3m",
                    "distanceMeters":round(distance_m(co,sc),2) if sc else None,
                    "nationalPlugCodes":sorted(plugcodes),
                    "nationalPowerW":sorted(npowers),
                    "price":p,
                    "connector":{
                        "Id":conn.get("Id") or conn.get("ID") or conn.get("id"),
                        "Name":conn.get("Name") or conn.get("name"),
                        "PlugType":code,
                        "MaxPower":mp,
                        "HubjectID":(conn.get("Hubject") or {}).get("ID") if isinstance(conn.get("Hubject"),dict) else None
                    }
                }

    if not accepted and co and isinstance(arr,list):
        ntypes=national_power_types(rec)
        if len(ntypes)==1:
            target_type=next(iter(ntypes))
            type_matches=[]
            for st in arr:
                sc=station_coord(st)
                if not sc or distance_m(co,sc) > 3.0:
                    continue
                for conn in connectors(st):
                    p=connector_price(conn)
                    if connector_access(conn) not in (0,None) or not isinstance(p,dict):
                        continue
                    if target_type in connector_explicit_power_type(conn):
                        type_matches.append((st,conn,p))
            if len(type_matches)==1:
                st,conn,p=type_matches[0]
                sc=station_coord(st)
                accepted={
                    "evseId":eid,
                    "stationName":station_name(st),
                    "stationId":st.get("ID") or st.get("id"),
                    "match":"unique_explicit_acdc_connector_within_3m",
                    "distanceMeters":round(distance_m(co,sc),2) if sc else None,
                    "nationalPowerType":target_type,
                    "price":p,
                    "connector":{
                        "Id":conn.get("Id") or conn.get("ID") or conn.get("id"),
                        "Name":conn.get("Name") or conn.get("name"),
                        "Description":conn.get("Description") or conn.get("description"),
                        "MaxPower":conn.get("MaxPower") or conn.get("maxPower"),
                        "HubjectID":(conn.get("Hubject") or {}).get("ID") if isinstance(conn.get("Hubject"),dict) else None
                    }
                }

    if accepted:
        promoted.append(accepted)
        overlay.setdefault("rows",[]).append(accepted)
        result="promoted"
    else:
        result="no_safe_exact_match"
    tested.append({"evseId":eid,"result":result,"namesTried":names,"coordinate":co})
    time.sleep(0.15)

now=datetime.now(timezone.utc).isoformat()
overlay["generatedAt"]=now
overlay["method"]="Exact eCarUp public API reconciliation: name-search uniform tariff, exact ChargingStationNames+coordinate, exact Hubject.ID, identical price tuple at <=0.75m/3m, unique exact connector power, validated Type2/CCS/CHAdeMO + power, or unique explicit AC/DC connector within 3m"
overlay["policy"]="No nearest-neighbour tariff inheritance; no cross-station extrapolation."
OVERLAY.write_text(json.dumps(overlay,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

report={
    "schemaVersion":1,
    "country":"CH",
    "operatorId":"CH*ECU",
    "generatedAt":now,
    "remainingBeforeBatch":len(remaining),
    "batchSize":BATCH,
    "testedCount":len(tested),
    "promotedCount":len(promoted),
    "remainingAfterBatch":len(remaining)-len(promoted),
    "promoted":promoted,
    "tested":tested,
    "errors":errors,
    "policy":"Fail closed: exact normalized name+coordinate, exact Hubject.ID, identical full public price tuple within <=0.75m/3m, or exactly one public connector within <=3m matching the national declared charging power."
}
REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

if CANON.exists():
    canon=json.loads(CANON.read_text(encoding="utf-8"))
    promoted_total=len({r.get("evseId") for r in overlay.get("rows",[]) if r.get("evseId")})
    priced_total=6470+promoted_total
    remaining_total=max(0,6764-priced_total)
    for op in canon.get("operators",[]):
        if op.get("operatorId")=="CH*ECU":
            op["status"]="complete" if remaining_total==0 else "partial"
            op["evidence"]=str(REPORT)
            op["note"]=f"{priced_total}/6764 deterministic current prices. Exact ChargingStationNames + coordinate public API reconciliation promoted {promoted_total} residual EVSEs in total; {remaining_total} remain fail-closed."
            op["setAside"]=False
            op["blockerPersistent"]=False
            op["blockerEvidence"]=None
            op["resumeCondition"]=None if remaining_total==0 else "Continue secondary exact-identity methods on the remaining residual EVSEs; no nearest-neighbour or cross-station tariff extrapolation."
    canon["updatedAt"]=now
    CANON.write_text(json.dumps(canon,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

print(json.dumps({k:v for k,v in report.items() if k not in ("tested","errors")},ensure_ascii=False,indent=2))
