"""Offline G6.6b-2: exact active national generation and archived lane impact.
No source writes, new identities, price promotion or hosted runtime."""
import collections, gzip, hashlib, json, os, pathlib, sys
from scripts.audit_irve_g5_power_scope import download, verify, digest, gzjson
from scripts.audit_electroverse_g5_real_matching import validate_national_projection
from scripts.build_v9_canonical_batch import build as build_archived
from v9_rebuild.canonical import normalize_france_irve_compact, validate
from v9_rebuild.canonical_registry import BY_SOURCE
from v9_rebuild.snapshot import prepare
ROOT=pathlib.Path(__file__).resolve().parents[1]
SOURCE="FR:irve_static"

def active_compact(rows, active):
    """Filter only exact raw EVSE keys; retain original station/group IDs."""
    result=[]
    for row in rows:
        groups=[]
        for group in row[8]:
            ids=[pdc for pdc in group[6] if pdc in active]
            if ids: groups.append([*group[:4],len(ids),group[5],ids])
        if groups:
            copy=list(row); copy[8]=groups; copy[6]=len({p for g in groups for p in g[6]})
            result.append(copy)
    actual={p for s in result for g in s[8] for p in g[6]}
    if actual!=active: raise ValueError("Active exact ID reconciliation")
    return result

def visible(n):
    """For archived lane replay only, exclude independently reviewed nonpublic sites."""
    ss=[s for s in n["stations"] if s.get("publicAccessDecision")!="exclude_non_public"]
    ids={s["id"] for s in ss}
    es=[e for e in n["evses"] if e["stationId"] in ids]
    ei={e["id"] for e in es}
    return dict(n,stations=ss,evses=es,connectors=[c for c in n["connectors"] if c["evseId"] in ei])

def write_json(path,obj):
    data=(json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(",",":"))+"\n").encode()
    path.write_bytes(data)
def write_gz(path,obj):
    raw=json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()
    path.write_bytes(gzip.compress(raw,mtime=0))

def compare_lanes(before,after,old,new,keys,lane):
    def index(report,n):
        s={r["id"]:r for r in n["stations"]};e={r["id"]:r for r in n["evses"]};c={r["id"]:r for r in n["connectors"]}
        out={}
        for kind in ("matches","unmatched"):
            for r in report[kind]:
                k=tuple(r.get(x) for x in keys)
                row=dict(r,matched=kind=="matches")
                if kind=="matches":
                    target=e[r["nationalEvseId"]]; st=s[target["stationId"]]
                    conn=c.get(r.get("nationalConnectorId"))
                    row["target"]=[st["sourceStationId"],st["cpoId"],target.get("officialEvseId"),
                        [conn.get("officialConnectorId"),conn.get("plugType"),conn.get("kind"),conn.get("powerKw")] if conn else None]
                out.setdefault(k,[]).append(row)
        return out
    a,b=index(before,old),index(after,new)
    records=[]
    for k in sorted(a.keys()|b.keys(),key=str):
        aa,bb=a.get(k,[]),b.get(k,[])
        am=[r["target"] for r in aa if r["matched"]];bm=[r["target"] for r in bb if r["matched"]]
        if len(am)>1 or len(bm)>1: state="AMBIGUOUS_PROOF_REVIEW"
        elif am and bm: state="UNCHANGED_TARGET" if am==bm else "CHANGED_TARGET_REVIEW"
        elif am: state="LOST_EXACT_TARGET"
        elif bm: state="NEW_EXACT_TARGET_REVIEW"
        else: state="UNMATCHED_BOTH"
        records.append(dict(lane=lane,key=k,state=state,before=aa,after=bb))
    return records

def main():
    pin=json.loads(pathlib.Path(sys.argv[1]).read_text());root=pathlib.Path(sys.argv[2]);root.mkdir()
    if pin["purpose"]!="offline_g66b2_active_national_alignment" or any(pin[k] is not False for k in ("supplierCalls","automaticPublication","runtimeActivation")): raise ValueError("Scope")
    sys.path.insert(0,str(ROOT/"production"/"scripts"))
    from import_g66_fr_projection import import_projection,crosswalk
    from import_v9_bundle import verify as production_verify
    from join_v9_exact import match_offers
    from build_v9_emsp_exact_join_report import read_electra,match_proofs
    g66=json.loads((ROOT/"production/config/migration/g66-fr-projection-pin.json").read_text())
    download(root/"g66a",g66,{"report":("g66-runtime-report.json",)})
    projection,g66report=import_projection(root/"g66a/input.zip",g66)
    prev=download(root/"previous",pin["previous"],{"crosswalk":("crosswalk.json.gz",),"receipt":("receipt.json",)})
    verify(prev["crosswalk"],pin["previousCrosswalkSha256"]);verify(prev["receipt"],pin["previousReceiptSha256"])
    prior=gzjson(prev["crosswalk"]); prior_receipt=json.loads(prev["receipt"].read_text())
    if prior_receipt["matched"]!=0 or len(prior)!=len(projection): raise ValueError("Previous lineage")
    previous={r["national_id"]:r for r in prior}
    if len(previous)!=len(prior) or any(any(previous[r["national_id"]][k]!=v for k,v in r.items()) for r in projection): raise ValueError("Previous projection changed")
    n=download(root/"national",pin["national"],{
      "all.json.gz":("data","national","france-irve-static-v9","all.json.gz"),
      "manifest.json":("data","national","france-irve-static-v9","manifest.json"),
      "dynamic.json.gz":("data","national","france-irve-dynamic-status-v9.json.gz"),
      "source.json":("reports","france","irve","irve-residual-crosswalk-latest.json"),
      "refresh.json":("irve-refresh-summary.json",)})
    verify(n["all.json.gz"],pin["allSha256"]);verify(n["dynamic.json.gz"],pin["dynamicSha256"])
    refresh=json.loads(n["refresh.json"].read_text()); manifest=json.loads(n["manifest.json"].read_text())
    if (refresh["codeSha"]!=pin["national"]["codeSha"] or refresh["staticAllSha256"]!=pin["allSha256"] or refresh["dynamicFileSha256"]!=pin["dynamicSha256"] or manifest["allSha256"]!=pin["allSha256"]): raise ValueError("National lineage")
    raw=gzjson(n["all.json.gz"]); dyn=gzjson(n["dynamic.json.gz"])
    active,owners,states=validate_national_projection(raw,dyn,manifest,json.loads(n["source.json"].read_text())["sources"])
    filtered=active_compact(raw,active)
    profiles=sum(len(g[6]) for s in filtered for g in s[8])
    if (len(active)!=refresh["activeEvse"] or len(filtered)!=refresh["activeStations"] or profiles!=refresh["activeConnectorProfiles"] or profiles!=g66report["nationalConnectorInventory"]): raise ValueError("Active snapshot internal reconciliation")
    ledger=(ROOT/"reports/france/irve-public-access-validation-ledger.json").read_bytes()
    kwargs=dict(artifact_sha256=pin["allSha256"],access_ledger=json.loads(ledger),access_ledger_sha256=hashlib.sha256(ledger).hexdigest(),source_manifest_bytes=n["manifest.json"].read_bytes())
    # Canonicalize both versions with the same existing production preview normalizer.
    full=normalize_france_irve_compact(raw,**kwargs)
    new=normalize_france_irve_compact(filtered,**kwargs)
    new["source"].update(operationalScope="IRVE_en_service_only",dynamicArtifactSha256=pin["dynamicSha256"],dynamicGeneratedAt=dyn["generatedAt"],nationalRun=pin["national"]["run"],nationalArtifact=pin["national"]["artifact"])
    validate(new)
    if {r["officialEvseId"] for r in new["evses"]}!=active or len(new["connectors"])!=profiles: raise ValueError("Canonical active identity mismatch")
    # Original compact group keys and canonical identities must remain identical after filter.
    old_keys={c["id"] for c in full["connectors"]};new_keys={c["id"] for c in new["connectors"]}
    if not new_keys<=old_keys: raise ValueError("Canonical active ID altered")
    del full, raw
    archived_ids=sorted(s for s in BY_SOURCE if s.startswith("FR:"))
    archived=build_archived(root/"archived",archived_ids)
    old_bundle=root/"archived/bundles"/archived["bundleId"]
    old_path=old_bundle/"FR__irve_static.json"
    old=json.loads(old_path.read_bytes())
    if digest(old_path)!=prior_receipt["nationalCanonicalSha256"]: raise ValueError("October generation changed")
    canonical=root/"FR__irve_static.json";write_json(canonical,new)
    bundle=prepare({SOURCE:canonical},root/"bundles")
    production_verify(bundle,selected_source=SOURCE)
    october=crosswalk(old,projection); november=crosswalk(new,projection)
    if len(october)!=len(november) or len(november)!=len(projection) or any(r["publicationEligible"] for r in october+november): raise ValueError("Crosswalk scope")
    # For every approved G5 pair verify matching exact national source IDs on the refreshed generation.
    for r in november:
        if r["evse_id"] not in active: raise ValueError("Approved G5 EVSE absent from its own active generation")
    transitions=collections.Counter((previous[r["national_id"]]["reason"],o["reason"],r["reason"]) for o,r in zip(october,november))
    for o,r in zip(october,november):
        if o["national_id"]!=r["national_id"]: raise ValueError("Order")
    # Existing archived Direct and Electra identity evidence only, not recalculated prices.
    ov,nv=visible(old),visible(new)
    direct=[]
    for source in archived_ids:
        if source==SOURCE: continue
        data=json.loads((old_bundle/(source.replace(":","__")+".json")).read_bytes())
        offers=[r for r in data["offers"] if r["channel"]=="Direct"]
        if not offers: continue
        src=dict(data,offers=offers)
        direct.extend(compare_lanes(match_offers(ov,[src]),match_offers(nv,[src]),ov,nv,("sourceId","offerId"),"Direct"))
    electra,esha=read_electra(ROOT/"data/platforms/electra/verified-app-evse-tariff-map.json")
    eimpact=compare_lanes(match_proofs(ov,electra),match_proofs(nv,electra),ov,nv,("channel","offerId","officialEvseId"),"Electra")
    dest=root/"results";dest.mkdir()
    write_gz(dest/"g66b2-october-corrected.json.gz",october)
    write_gz(dest/"g66b2-november-crosswalk.json.gz",november)
    write_gz(dest/"g66b2-archived-lane-impact.json.gz",direct+eimpact)
    write_gz(dest/"g66b2-national-active-canonical.json.gz",new)
    (dest/"g66b2-bundle-manifest.json").write_bytes((bundle/"manifest.json").read_bytes())
    report=dict(codeSha=os.environ.get("GITHUB_SHA"),sourcePin=pin,bundleId=bundle.name,nationalCanonicalSha256=digest(canonical),
        activeEvse=len(active),activeStations=len(filtered),activeProfiles=profiles,states=dict(collections.Counter(states.values())),
        nonPublicStations=sum(s.get("publicAccessDecision")=="exclude_non_public" for s in new["stations"]),
        oldCounts=dict(collections.Counter(r["reason"] for r in october)),newCounts=dict(collections.Counter(r["reason"] for r in november)),
        transitions=[dict(before=k[0],correctedOctober=k[1],november=k[2],count=v) for k,v in sorted(transitions.items())],
        lanes={lane:dict(collections.Counter(r["state"] for r in rows)) for lane,rows in (("Direct",direct),("Electra",eimpact))},
        directSources=[s for s in archived_ids if s!=SOURCE],electraProofSha256=esha,
        pricesPromoted=0,identityChanges=0,supplierCalls=0,published=False,runtimeActivated=False,
        limitations=["Archived canonical exact-offer join and Electra archived proof coverage, not all live or historical runtime tariffs; no price computation or transfer","October label correction isolated from November generation and active-status change","No new G5 matching, no runtime activation or public deployment","National canonical export is an isolated candidate; artifact retention is not durable storage"])
    report["exportSha256"]={p.name:digest(p) for p in dest.iterdir()}
    write_json(dest/"g66b2-report.json",report)
    print("G66B2 "+json.dumps(report,sort_keys=True))
if __name__=="__main__": main()
