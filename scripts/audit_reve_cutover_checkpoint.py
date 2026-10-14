#!/usr/bin/env python3
"""Read-only Spanish REVE checkpoint / provenance validation before legacy cutover."""
import argparse,json,pathlib,gzip
p=argparse.ArgumentParser()
p.add_argument("--root",type=pathlib.Path,default=pathlib.Path("."))
p.add_argument("--report",type=pathlib.Path,required=True)
a=p.parse_args()
root=a.root/"data/spain_reve"
statefile=root/"tariff_status_stream_state.json"
lastfile=root/"tariff_status_stream_last_run.json"
state=json.loads(statefile.read_text()) if statefile.exists() else {}
last=json.loads(lastfile.read_text()) if lastfile.exists() else {}
tariff=root/"reve_connector_tariffs_raw.json.gz"
status=root/"reve_operational_status_raw.json.gz"
def inspect(path):
    entry={"exists":path.is_file(),"bytes":path.stat().st_size if path.is_file() else None,"gzipReadable":False}
    if path.is_file():
        try:
            with gzip.open(path,"rb") as fp:
                fp.read(1)
            entry["gzipReadable"]=True
        except (OSError,EOFError): pass
    return entry
cursors={k:state.get(k) for k in ("nextTariffPage","nextStatusPage","tariffRowsStored","statusRowsStored","complete")}
attempted=last.get("requestsAttempted")
succeeded=last.get("requestsSucceeded")
workflow=(a.root/".github/workflows/spain-reve-v9-stream-refresh.yml").read_text()
no_legacy_fallback="tesla-charge-companion-stable/spain-reve-preintegration" not in workflow
report={"schemaVersion":1,"purpose":"shadow-reve-cutover-validation","cursors":cursors,
        "lastRun":{"requestsAttempted":attempted,"requestsSucceeded":succeeded},
        "datasets":{"tariff":inspect(tariff),"status":inspect(status)},
        "tests":{"statePresent":statefile.exists(),"noStableFallback":no_legacy_fallback,"tariffCursorBaselineMet":isinstance(cursors["nextTariffPage"],int) and cursors["nextTariffPage"]>=245,
                 "statusCursorBaselineMet":isinstance(cursors["nextStatusPage"],int) and cursors["nextStatusPage"]>=164,
                 "requestBudget":attempted is None or (isinstance(attempted,int) and attempted<=5),
                 "lastBatchSucceeded":attempted is None or attempted==succeeded,
                 "tariffGzipPresentAndReadable":inspect(tariff)["gzipReadable"],
                 "statusGzipPresentAndReadable":inspect(status)["gzipReadable"]},
        "cutoverAuthorized":False,"stableFallbackDependencyStillPresent":not no_legacy_fallback}
a.report.parent.mkdir(parents=True,exist_ok=True)
a.report.write_text(json.dumps(report,indent=2)+"\n")
print(json.dumps(report,indent=2))
if not all(report["tests"].values()): raise SystemExit("REVE state validation failed")
