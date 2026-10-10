#!/usr/bin/env python3
"""Regression: 52 Connected Kerb UTC day/night repair and 4 fee safeguards."""
import collections,gzip,importlib.util,json
from pathlib import Path
from datetime import datetime,timezone

ROOT=Path(__file__).resolve().parents[1]
def load(path):
    with gzip.open(ROOT/path,"rt",encoding="utf8") as f:return json.load(f)
def main():
    spec=importlib.util.spec_from_file_location("ck_source",ROOT/"scripts/uk_connected_kerb_app_collect.py")
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    detailed=load("data/national/uk_connected_kerb_app_details.json.gz")
    baseline=load("data/national/uk_connected_kerb_locations.json.gz")
    with open(ROOT/"reports/uk/connected-kerb-app-collection-latest.json",encoding="utf8") as f:original=json.load(f)
    assert detailed["collectedAt"]==original["collectedAt"]
    lookup={x["operatorLocationId"]:x for x in detailed["records"]}
    public={x["id"]:x for x in baseline["locations"] if x.get("publish")}
    by_reason=collections.Counter()
    outputs=[]
    for bad in original["unresolved"]:
        if bad["reason"] not in ("multiple_energy_prices_without_windows","fee_unit_verification_pending"):continue
        detail=lookup[bad["locationId"]]["location"]
        matched=[x for x in detail["sockets"] if mod.qr(x.get("qrCode"))==mod.qr(bad.get("physicalReference"))]
        assert len(matched)==1
        price,reason=mod.choose_standard(matched[0])
        if bad["reason"]=="multiple_energy_prices_without_windows":
            assert reason is None and price, (bad,reason)
            assert price["timeOfDayWindowsRecoveredFromSameSocketSpecification"] is True
            energy=price["energySlices"]
            assert len(energy)==2
            assert {v["startTime"][:5] for v in energy}=={"15:00","19:00"}
            assert {(v["startTime"][:5],v["endTime"][:5]) for v in energy}=={("15:00","19:00"),("19:00","15:00")}
            assert {round(v["price"],5) for v in energy}=={.45,.35004}
            # Sample every minute (1440 points): one, and only one, applicable.
            def inside(m,s,e):
                return s<=m<e if s<e else m>=s or m<e
            starts=[(int(v["startTime"][:2])*60+int(v["startTime"][3:5]),int(v["endTime"][:2])*60+int(v["endTime"][3:5])) for v in energy]
            assert all(sum(inside(t,a,b) for a,b in starts)==1 for t in range(1440))
            by_reason["recovered_energy_windows"]+=1
        else:
            assert reason=="fee_unit_verification_pending" and price is None
            by_reason["fee_unit_still_blocked"]+=1
        outputs.append({"locationId":bad["locationId"],"evseId":bad["evseId"],"connectorId":bad["connectorId"],
            "originalReason":bad["reason"],"decision":"exact_time_windows_recovered" if price else "tarif_incalculable",
            "tariffId":price["appTariffId"] if price else None,
            "energyRulesUtc":price["energySlices"] if price else None})
    assert len(outputs)==56 and by_reason["recovered_energy_windows"]==52 and by_reason["fee_unit_still_blocked"]==4,dict(by_reason)
    report={"generatedAt":datetime.now(timezone.utc).isoformat(),"sourceAppAt":original["collectedAt"],
            "sourceBaselineAt":original["operatorBaselineCollectedAt"],"total":56,
            "classification":dict(by_reason),"productionActivated":False,
            "safety":"source-app proof only, no extrapolation, future collector must persist full app reconciliations",
            "records":outputs}
    path=ROOT/"reports/uk/connected-kerb-tod-resolution-qa-2026-10-10.json"
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    print("CONNECTED_KERB_TOD_QA="+json.dumps({"classification":dict(by_reason),"pass":True}))
if __name__=="__main__":main()
