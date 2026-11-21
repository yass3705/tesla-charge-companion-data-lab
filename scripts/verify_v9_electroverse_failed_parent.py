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

PARENT_ZIP_SHA = "3622a321b6885434d7c4541199d2ffc58703c82f790a0511a6b3cf998e6e7aac"
FAILURE_ZIP_SHA = "2e1c1b9c4a8feeb3049f99db8e4df9ef9a1a24cc890359d0ea2aa1bb1a42ecf7"
PARENT_FILESET_SHA = "b04dfb1565024c06a40b5fc75069ea07cad2f03e24f7fa8032634657a662d1e3"
FAILURE_FILESET_SHA = "789fbf0f55d3d38ba8d9a84695215f81edd0e374db08549f0e011c8d3df58dd8"
PARENT_RUN, FAILURE_RUN = 44950136959, 44956526554
PARENT_HEAD = "78d3c997c156a54c7954808969c2fe369918a330"
FAILURE_HEAD = "1edd310ebbad1d554f7bbe3c8599678dacbd440f"
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
    if (len(names)!=138 or len(names)!=len(set(names))
            or any(n.startswith("/") or "\\" in n or ".." in PurePosixPath(n).parts for n in names)
            or any(((i.external_attr>>16)&0o170000)==0o120000 for i in z.infolist())):
        raise ValueError("Unsafe or changed checkpoint archive")
    manifest=jread(z,"checkpoint-manifest.json")
    if (manifest.get("state")!="partial_checkpoint"
            or manifest.get("completeSnapshotValidated") is not False
            or manifest.get("source")!="FR:electroverse_full"
            or manifest.get("branch")!="rebuild/v9-20261020"
            or manifest.get("headSha")!=head or manifest.get("runId")!=run
            or manifest.get("sha256")!=fileset_sha or len(manifest.get("files",[]))!=136):
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


def verify_transition(parent,failed):
    old=jread(parent,CURSOR);new=jread(failed,CURSOR)
    if (old["completed"]!=[0] or new["completed"]!=[0,6000]
            or len(old["pending"]["pks"])!=1700
            or len(new["pending"]["pks"])!=5501
            or new["pending"]["pks"][0]!="4234003"):
        raise ValueError("Unexpected recovery cursor")
    if parent.read(MAPPING)!=failed.read(MAPPING) or parent.read(INVENTORY)!=failed.read(INVENTORY):
        raise ValueError("Mapping or national inventory was modified")
    keys=[str(m["electroverseLocationPk"]) for m in jread(parent,MAPPING)["mappings"]]
    if len(keys)!=22818 or len(set(keys))!=len(keys):
        raise ValueError("Untrusted mapping key population")
    order=ordered_pks(keys)
    older=processed(old,order);newer=processed(new,order)
    advance=newer-older
    if not older<=newer or len(advance)!=2199 or "4234003" in advance:
        raise ValueError("Lost or repeated verified location")
    a=jread(parent,CHECKED)["checkedAt"];b=jread(failed,CHECKED)["checkedAt"]
    if set(a)!=set(b) or set(a)!=set(keys):
        raise ValueError("Missing checked timestamps")
    modified={pk for pk in a if a[pk]!=b[pk]}
    if modified!=advance or any(b[pk]<=a[pk] for pk in advance):
        raise ValueError("Checks outside monotonic new cursor")
    oldManifest=jread(parent,"manifest.json")
    newManifest=jread(failed,"manifest.json")
    if (oldManifest["status"]!="partial_failure"
            or oldManifest["sources"][0]["reason"]!="collector_window_budget"
            or newManifest["status"]!="partial_failure"
            or newManifest["sources"][0]["reason"]!="collector_exit_nonzero"
            or newManifest["sources"][0]["source"]!="FR:electroverse_full"):
        raise ValueError("Failed source not compatible with recoverable checkpoint")
    errors=jread(failed,FAILURES)["failures"]
    if len(errors)!=1 or errors[0].get("pk")!="4234003" or errors[0].get("error")!="fetch_failed":
        raise ValueError("Missing or changed retryable failed identity")
    if "4234003" not in new["pending"]["pks"]:
        raise ValueError("Failed source ID was discarded")
    checked_rows=changed_hash=0
    for idx in range(128):
        path=STATE+f"data/electroverse/tariff_cache/shard-{idx:03d}.json"
        before=jread(parent,path)["stations"]
        after=jread(failed,path)["stations"]
        if set(before)!=set(after):
            raise ValueError("Shards lost/add stations")
        for pk,row in before.items():
            if pk not in advance and row!=after[pk]:
                raise ValueError("Unselected station modified "+pk)
            if pk in advance:
                checked_rows+=1
                changed_hash+=row["tariffHash"]!=after[pk]["tariffHash"]
    if checked_rows!=2199 or changed_hash!=971:
        raise ValueError("Incorrect validated tariff delta")
    return {"state":"recovered_failure_not_complete","parentRun":PARENT_RUN,
            "failureRun":FAILURE_RUN,"newlyChecked":checked_rows,
            "totalChecked":len(newer),"remaining":len(keys)-len(newer),
            "completed":new["completed"],"pendingOffset":new["pending"]["offset"],
            "pending":len(new["pending"]["pks"]),"failedPk":"4234003",
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
