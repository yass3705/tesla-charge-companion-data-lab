#!/usr/bin/env python3
"""Audited, pinned recovery of a failed source window; never promotion evidence.

Uses 128 source shards and an independent successful parent artifact. Only one
known failure is trusted; any other failed run needs its own evidence and pin.
"""
import argparse
import hashlib
import json
import subprocess
import zipfile
from pathlib import PurePosixPath

PARENT_ZIP_SHA = "92ffb6c827fdfe805518746aa0eba13730a8f26ef6254ef9b69e149de655e5c1"
FAILURE_ZIP_SHA = "60bbd578cc6a8193e5dbc6c3105bacc16407c06bd42f431bad2ae803f6099f01"
PARENT_FILESET_SHA = "1969e550c139db2dfdad6f0709b0bc4084002d424a6d9e66c90ccc56cb6d4fa9"
FAILURE_FILESET_SHA = "1aea5283a310f637410db62b9743891122ba33d2126269648dadb9cbfb6231fe"
PARENT_RUN, FAILURE_RUN = 44962339493, 44968499274
PARENT_HEAD = "5fffc5bbf931533d2b177d414484e9a9f6a78167"
FAILURE_HEAD = "1c8c6d1b377d266ab2f82b053326aeb5c3604b97"
STATE = "checkpoints/FR_electroverse_full/"
MAPPING = STATE+"data/electroverse/irve_location_mapping.json"
INVENTORY = STATE+"data/electroverse/inventory/france-current.json"
CHECKED = STATE+"data/electroverse/tariff_cache/checked-at.json"
CURSOR = STATE+"v9-electroverse-checkpoint.json"
FAILURES = STATE+"reports/electroverse/hybrid-refresh-failures.json"


def jread(z,path):
    return json.loads(z.read(path))


def verify_archive(path, zip_sha, fileset_sha, run, head):
    h=hashlib.sha256()
    with open(path,"rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""):
            h.update(chunk)
    if h.hexdigest()!=zip_sha:
        raise ValueError("Pinned ZIP SHA-256 mismatch")
    z=zipfile.ZipFile(path)
    names=z.namelist()
    expected_files=136 if run==PARENT_RUN else 137 if run==FAILURE_RUN else -1
    if (len(names)!=expected_files+2 or len(names)!=len(set(names))
            or any(n.startswith("/") or "\\" in n or ".." in PurePosixPath(n).parts for n in names)
            or any(((i.external_attr>>16)&0o170000)==0o120000 for i in z.infolist())):
        raise ValueError("Unsafe or changed checkpoint archive")
    manifest=jread(z,"checkpoint-manifest.json")
    if (manifest.get("state")!="partial_checkpoint"
            or manifest.get("completeSnapshotValidated") is not False
            or manifest.get("source")!="FR:electroverse_full"
            or manifest.get("branch")!="rebuild/v9-20261020"
            or manifest.get("headSha")!=head or manifest.get("runId")!=run
            or manifest.get("sha256")!=fileset_sha or len(manifest.get("files",[]))!=expected_files):
        raise ValueError("Untrusted checkpoint file-set manifest")
    listed=set()
    for file in manifest["files"]:
        rel=STATE+file["path"]
        if rel in listed:
            raise ValueError("Duplicate listed path")
        listed.add(rel)
        raw=z.read(rel)
        if len(raw)!=file["bytes"] or hashlib.sha256(raw).hexdigest()!=file["sha256"]:
            raise ValueError("Corrupted checkpoint file "+rel)
    if set(names)!=(listed|{"manifest.json","checkpoint-manifest.json"}):
        raise ValueError("Unexpected checkpoint archive files")
    return z


def ordered_pks(keys):
    js='const fs=require("node:fs");const a=JSON.parse(fs.readFileSync(0,"utf8"));process.stdout.write(JSON.stringify(a.sort((x,y)=>x.localeCompare(y))))'
    return json.loads(subprocess.check_output(["node","-e",js],input=json.dumps(keys).encode()))


def processed(cursor,order):
    completed=cursor["completed"]
    if cursor.get("mode")!="full" or completed!=list(range(0,len(completed)*6000,6000)):
        raise ValueError("Noncontiguous checkpoint")
    offset=len(completed)*6000
    pending=cursor.get("pending")
    if not isinstance(pending,dict) or pending.get("offset")!=offset:
        raise ValueError("Bad pending offset")
    rest=pending.get("pks")
    if not isinstance(rest,list) or not rest or len(set(rest))!=len(rest):
        raise ValueError("Missing or duplicate pending station")
    current=set(order[offset:offset+6000])
    if not set(rest)<=current:
        raise ValueError("Pending station outside selected source chunk")
    return set(order[:offset])|(current-set(rest))


def verify_transition(parent, failed):
    old=jread(parent,CURSOR);new=jread(failed,CURSOR)
    if (old["completed"]!=[0,6000] or new["completed"]!=[0,6000]
            or old["pending"]["offset"]!=12000 or new["pending"]["offset"]!=12000
            or len(old["pending"]["pks"])!=4804 or len(new["pending"]["pks"])!=2306):
        raise ValueError("Unexpected latest checkpoint cursor")
    if parent.read(MAPPING)!=failed.read(MAPPING) or parent.read(INVENTORY)!=failed.read(INVENTORY):
        raise ValueError("Mapping or inventory changed")
    keys=[str(m["electroverseLocationPk"]) for m in jread(parent,MAPPING)["mappings"]]
    if len(keys)!=22818 or len(set(keys))!=len(keys):raise ValueError("Invalid Electroverse location population")
    order=ordered_pks(keys);older=processed(old,order);newer=processed(new,order)
    delta=newer-older
    if (not older<=newer or len(delta)!=2498
            or set(old["pending"]["pks"])-set(new["pending"]["pks"])!=delta
            or not set(new["pending"]["pks"])<=set(old["pending"]["pks"])
            or not {"426269","426271","426272"}<=delta):
        raise ValueError("Repeated or lost previously verified identities")
    a=jread(parent,CHECKED)["checkedAt"];b=jread(failed,CHECKED)["checkedAt"]
    if set(a)!=set(b) or set(a)!=set(keys):raise ValueError("Checked timestamp population changed")
    changed_ids={pk for pk in a if a[pk]!=b[pk]}
    if changed_ids!=delta or any(b[pk]<=a[pk] for pk in delta):
        raise ValueError("Nonmonotonic or out-of-window checked timestamps")
    old_manifest=jread(parent,"manifest.json");new_manifest=jread(failed,"manifest.json")
    if (old_manifest.get("status")!="partial_failure"
            or new_manifest.get("status")!="partial_failure"
            or old_manifest["sources"][0]["reason"]!="collector_exit_nonzero"
            or new_manifest["sources"][0]["reason"]!="collector_exit_nonzero"
            or new_manifest["sources"][0]["source"]!="FR:electroverse_full"):
        raise ValueError("Incompatible partial source status")
    expected={"4475895","4475896"}
    failures=jread(failed,FAILURES)["failures"]
    if (len(failures)!=2 or {str(e.get("pk")) for e in failures}!=expected
            or any(e.get("error")!="fetch_failed" or len(e.get("diagnostics",{}).get("attempts",[]))!=5
                   or any(row.get("httpStatus")!=429 for row in e["diagnostics"]["attempts"])
                   for e in failures)
            or not expected<=set(new["pending"]["pks"]) or expected&delta):
        raise ValueError("Untrusted rate-limited failure PKs or diagnostics")
    diagnostics_path=STATE+"reports/electroverse/failure-diagnostics.json"
    events=jread(failed,diagnostics_path).get("events",[])
    if len(events)!=1 or {str(e.get("pk")) for e in events[0].get("failures",[])}!=expected:
        raise ValueError("Diagnostic journal not conserved")
    checked_rows=changed_hash=0
    for idx in range(128):
        path=STATE+f"data/electroverse/tariff_cache/shard-{idx:03d}.json"
        before=jread(parent,path)["stations"];after=jread(failed,path)["stations"]
        if set(before)!=set(after):raise ValueError("Shard station membership changed")
        for pk,row in before.items():
            if pk not in delta and row!=after[pk]:raise ValueError("Unselected tariff modified "+pk)
            if pk in delta:
                checked_rows+=1;changed_hash+=row["tariffHash"]!=after[pk]["tariffHash"]
    if checked_rows!=2498 or changed_hash!=1077:raise ValueError("Unexpected tariff diff in checkpoint")
    return {"state":"recovered_failure_not_complete","parentRun":PARENT_RUN,
            "failureRun":FAILURE_RUN,"newlyChecked":checked_rows,
            "totalChecked":len(newer),"remaining":len(keys)-len(newer),
            "completed":new["completed"],"pendingOffset":new["pending"]["offset"],
            "pending":len(new["pending"]["pks"]),"failedPks":sorted(expected),
            "tariffHashChanged":changed_hash}


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--parent",required=True)
    p.add_argument("--failed",required=True)
    args=p.parse_args()
    parent=verify_archive(args.parent,PARENT_ZIP_SHA,PARENT_FILESET_SHA,PARENT_RUN,PARENT_HEAD)
    failed=verify_archive(args.failed,FAILURE_ZIP_SHA,FAILURE_FILESET_SHA,FAILURE_RUN,FAILURE_HEAD)
    try:
        print(json.dumps(verify_transition(parent,failed),sort_keys=True))
    finally:
        parent.close()
        failed.close()


if __name__=="__main__":
    main()
