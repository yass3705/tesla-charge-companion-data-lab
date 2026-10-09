#!/usr/bin/env python3
"""Regression: only explicit en_service PDC IDs establish operational station eligibility."""
import csv
import importlib.util
import tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("irve_dynamic_builder",ROOT/"scripts/france/build_france_irve_dynamic_status_v9.py")
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

def test_active_status_ids():
    static=[
        ["FR_TEST_P1",None,None,None,None,None,None,None,[[None,None,None,22,None,None,["FR*ABC*E*01","FR*ABC*E*02"]]]],
        ["FR_TEST_P2",None,None,None,None,None,None,None,[[None,None,None,50,None,None,["FR*ABC*E*03"]]]],
        ["FR_TEST_P3",None,None,None,None,None,None,None,[[None,None,None,60,None,None,["FR*ABC*E*04"]]]],
    ]
    records=[
        ("FR*ABC*E*01","hors_service","2026-10-09T00:00:00Z"),
        ("FR*ABC*E*02","hors_service","2026-10-08T00:00:00Z"),
        ("FR*ABC*E*02","en_service","2026-10-09T00:00:00Z"),
        ("FR*ABC*E*03","inconnu","2026-10-09T00:00:00Z"),
        ("FR*UNKNOWN*E*01","en_service","2026-10-09T00:00:00Z")
    ]
    with tempfile.TemporaryDirectory() as tmp:
        path=Path(tmp)/"dynamic.csv"
        with path.open("w",newline="",encoding="utf-8") as f:
            w=csv.DictWriter(f,fieldnames=["id_pdc_itinerance","etat_pdc","horodatage"])
            w.writeheader()
            for id,state,time in records:
                w.writerow({"id_pdc_itinerance":id,"etat_pdc":state,"horodatage":time})
        result=module.build(static,path,"2026-10-09T01:00:00Z")
    assert result["enServicePdcIds"]==["FR*ABC*E*02"],result
    assert result["matchedPdc"]==3,result
    assert result["displayExcludedPdc"]==2,result
    assert result["states"]=={"en_service":1,"hors_service":1,"inconnu":1},result
    assert "FR*ABC*E*04" not in result["enServicePdcIds"],result
    active=set(result["enServicePdcIds"])
    assert [x[0] for x in static if any(p in active for g in x[8] for p in g[6])]==["FR_TEST_P1"]
    print("IRVE_DYNAMIC_ACTIVE_EVIDENCE_TEST=PASS")

if __name__=="__main__":test_active_status_ids()
