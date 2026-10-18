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

    # The 583-EVSE dossier is historical evidence, not a current volume gate.
    fin=load(Path("docs/switzerland-avia-finalization-2026-09-29.json"))
    avia=load(Path("data/switzerland/avia-guest-direct-tariffs.json"))
    rec=load(Path("docs/switzerland-avia-guest-reconciliation-2026-09-29.json"))
    assert fin["status"]=="complete"
    assert fin["coverage"]["resolvedNationalEvseCount"]==583
    assert fin["coverage"]["unresolvedNationalEvseCount"]==0
    checks["AVIA_CH"]={
      "acceptedResolved":583,
      "currentGuestPricedEvses":avia["counts"]["uniquePricedEvses"],
      "currentMissingNational":rec["counts"]["missingNationalEvseCount"]
    }

    # Atlante exact direct-price snapshots.
    atl_fr=load_gz(Path("data/national/atlante_direct_stations_france_latest.json.gz"))
    atl_it=load_gz(Path("data/national/atlante_direct_stations_italy_latest.json.gz"))
    nfr=seq_len(atl_fr); nit=seq_len(atl_it)
    assert nfr>0, nfr
    assert nit>0, nit
    checks["ATLANTE"]={"FR_stations":nfr,"IT_stations":nit}

    # IONITY France exact direct-price snapshot.
    ion=load_gz(Path("data/national/ionity_direct_stations_france.json.gz"))
    assert ion["operator"]=="IONITY", ion.get("operator")
    ic=ion["counts"]
    assert ic["franceLocationCount"]>0, ic
    checks["IONITY_FR"]={
      "locations":ic["franceLocationCount"],
      "connectors":ic["franceConnectorCount"],
      "unpriced":ic["franceUnpricedConnectorCount"]
    }

    ion_it=load_gz(Path("data/national/ionity_direct_stations_italy.json.gz"))
    assert ion_it["operator"]=="IONITY"
    itc=ion_it["counts"]
    assert itc["countryLocationCount"]>0, itc
    checks["IONITY_IT"]={
      "locations":itc["countryLocationCount"],
      "connectors":itc["countryConnectorCount"],
      "unpriced":itc["countryUnpricedConnectorCount"]
    }

    ion_de=load_gz(Path("data/national/ionity_direct_stations_germany.json.gz"))
    assert ion_de["operator"]=="IONITY"
    dec=ion_de["counts"]
    assert dec["countryLocationCount"]>0, dec
    checks["IONITY_DE"]={
      "locations":dec["countryLocationCount"],
      "connectors":dec["countryConnectorCount"],
      "unpriced":dec["countryUnpricedConnectorCount"]
    }

    # Electroverse France daily inventory must be complete at tile level.
    ev=load(Path("reports/electroverse/daily-delta.json"))
    assert ev["failedTileCount"]==0, ev["failedTileCount"]
    assert ev["inventoryCount"]>0, ev["inventoryCount"]
    checks["ELECTROVERSE_FR"]={"inventory":ev["inventoryCount"],"failedTiles":0}

    # Lidl UK accepted store-level inventory.
    lidl=load_gz(Path("data/national/uk_lidl_public_ev_stores.json.gz"))
    lstores=lidl.get("stores") or []
    assert lstores, "unexpected empty Lidl UK EV store source"
    assert all(x.get("evCharging") is True for x in lstores)
    checks["LIDL_UK"]={"evChargingStores":len(lstores)}

    # Morocco Kilowatt exact tariff scope.
    kw=load(Path("reports/morocco/kilowatt/latest-v9-tariff-overlay-manifest.json"))
    ks=kw["summary"]
    assert ks["productionStations"]>0, ks
    assert ks["free"]+ks["paid"]==ks["productionStations"], ks
    checks["KILOWATT_MA"]={"stations":ks["productionStations"],"unresolved":ks["unresolved"]}

    # Morocco TotalEnergies native guest scope.
    te=load(Path("reports/morocco/totalenergies/latest-native-overlay.json"))
    ts=te["summary"]
    assert te["station_count"]>0, te["station_count"]
    assert ts["priced_connectors"]<=ts["connectors_extracted"], ts
    checks["TOTALENERGIES_MA"]={"stations":te["station_count"],"connectors":ts["connectors_extracted"],"priced":ts["priced_connectors"],"live":ts["live_status_200"]}

    print(json.dumps({"status":"ok","checks":checks},ensure_ascii=False))

if __name__=="__main__":
    main()
