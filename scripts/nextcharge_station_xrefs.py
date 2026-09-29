#!/usr/bin/env python3
from __future__ import annotations
import json, zipfile
from pathlib import Path
from androguard.misc import AnalyzeAPK

APK=Path("/tmp/nextcharge.apk")
OUT=Path("data/reports/nextcharge_station_xrefs.json")
TOKENS=[
 "https://nextcharge.app.apis.goelectricstations.com/apis/station",
 "https://nextcharge.app.apis.goelectricstations.com/apis/stationConnectors",
 "evseId","idStation","uidConnector","payloadQrCode","urlToEncode",
 "tokenAppSessionForStations","tokenStations"
]

def method_dump(m):
    try:
        code=m.get_code()
        if not code: return []
        return [f"{i.get_name()} {i.get_output()}" for i in code.get_bc().get_instructions()]
    except Exception:
        return []

def main():
    a,ds,dx=AnalyzeAPK(str(APK))
    wanted=set(TOKENS)
    found=[]
    # Androguard string xrefs -> methods
    for s in dx.get_strings():
        val=s.get_value()
        if not any(t in val for t in TOKENS):
            continue
        xrefs=[]
        for cls,meth,off in s.get_xref_from():
            ins=method_dump(meth)
            xrefs.append({
                "class":meth.get_class_name(),
                "method":meth.get_name(),
                "descriptor":meth.get_descriptor(),
                "offset":off,
                "instructions":ins[:1200],
            })
        found.append({"string":val,"xrefs":xrefs})
    report={"scope":"NextCharge station/xref analysis verified APK 6.2.02","findings":found}
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(report,ensure_ascii=False,indent=2)[:180000])

if __name__=="__main__": main()
