#!/usr/bin/env python3
import gzip
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def load(path):
    return json.loads((ROOT/path).read_text(encoding="utf-8"))

def load_gz(path):
    with gzip.open(ROOT/path,"rt",encoding="utf-8") as f:
        return json.load(f)

def seq_len(obj):
    if isinstance(obj,list):
        return len(obj)
    if isinstance(obj,dict):
        for key in ("stations","locations","data","items"):
            v=obj.get(key)
            if isinstance(v,list):
                return len(v)
    return 0

def main():
    checks={}

    # Switzerland AVIA accepted scope must never regress below the finalized
    # national 583-EVSE resolution.
    fin=load(Path("docs/switzerland-avia-finalization-2026-09-29.json"))
    avia=load(Path("data/switzerland/avia-guest-direct-tariffs.json"))
    rec=load(Path("docs/switzerland-avia-guest-reconciliation-2026-09-29.json"))
    assert fin["status"]=="complete"
    assert fin["coverage"]["resolvedNationalEvseCount"]==583
    assert fin["coverage"]["unresolvedNationalEvseCount"]==0
    assert avia["counts"]["uniquePricedEvses"]>=583, avia["counts"]
    assert rec["counts"]["nationalEvseCount"]==583
    assert rec["counts"]["missingNationalEvseCount"]<=1, rec["counts"]
    checks["AVIA_CH"]={
      "acceptedResolved":583,
      "currentGuestPricedEvses":avia["counts"]["uniquePricedEvses"],
      "currentMissingNational":rec["counts"]["missingNationalEvseCount"]
    }

    # Atlante exact direct-price snapshots.
    atl_fr=load_gz(Path("data/national/atlante_direct_stations_france_latest.json.gz"))
    atl_it=load_gz(Path("data/national/atlante_direct_stations_italy_latest.json.gz"))
    nfr=seq_len(atl_fr); nit=seq_len(atl_it)
    assert nfr>=160, nfr
    assert nit>=470, nit
    checks["ATLANTE"]={"FR_stations":nfr,"IT_stations":nit}

    # IONITY France exact direct-price snapshot.
    ion=load_gz(Path("data/national/ionity_direct_stations_france.json.gz"))
    assert ion["operator"]=="IONITY", ion.get("operator")
    ic=ion["counts"]
    assert ic["franceLocationCount"]>=180, ic
    assert ic["franceConnectorCount"]>=1800, ic
    assert ic["franceUnpricedConnectorCount"]==0, ic
    checks["IONITY_FR"]={
      "locations":ic["franceLocationCount"],
      "connectors":ic["franceConnectorCount"],
      "unpriced":0
    }

    # Electroverse France daily inventory must be complete at tile level.
    ev=load(Path("reports/electroverse/daily-delta.json"))
    assert ev["failedTileCount"]==0, ev["failedTileCount"]
    assert ev["inventoryCount"]>=160000, ev["inventoryCount"]
    checks["ELECTROVERSE_FR"]={"inventory":ev["inventoryCount"],"failedTiles":0}

    # Lidl UK accepted store-level inventory.
    lidl=load_gz(Path("data/national/uk_lidl_public_ev_stores.json.gz"))
    lstores=lidl.get("stores") or []
    assert len(lstores)>=300, len(lstores)
    assert all(x.get("evCharging") is True for x in lstores)
    checks["LIDL_UK"]={"evChargingStores":len(lstores)}

    # Morocco Kilowatt exact tariff scope.
    kw=load(Path("reports/morocco/kilowatt/latest-v9-tariff-overlay-manifest.json"))
    ks=kw["summary"]
    assert ks["productionStations"]==43, ks
    assert ks["unresolved"]==0, ks
    assert ks["free"]+ks["paid"]==ks["productionStations"], ks
    checks["KILOWATT_MA"]={"stations":43,"unresolved":0}

    # Morocco TotalEnergies native guest scope.
    te=load(Path("reports/morocco/totalenergies/latest-native-overlay.json"))
    ts=te["summary"]
    assert te["station_count"]==18, te["station_count"]
    assert ts["connectors_extracted"]==38, ts
    assert ts["priced_connectors"]==38, ts
    assert ts["live_status_200"]==38, ts
    checks["TOTALENERGIES_MA"]={"stations":18,"connectors":38,"priced":38,"live":38}

    print(json.dumps({"status":"ok","checks":checks},ensure_ascii=False))

if __name__=="__main__":
    main()
