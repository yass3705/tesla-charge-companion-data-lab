"""G6.6b-3 offline request/response gate for verified France Electroverse.
No HTTP service, provider request, price publication or browser activation."""
import collections, json, pathlib, subprocess
from scripts.audit_irve_g5_power_scope import verify
from scripts.audit_irve_g5_power_identity_scenarios import signature
from scripts.replay_g6_fr_simple import dec,j
from scripts.evaluate_g6_fr_dynamic import session,prepare,historical_rules
from scripts.consolidate_g6_fr_scenarios import EST,REVIEW
from scripts.unify_g6_fr_dynamic import diagnose,engine_agrees,PASS
from scripts.refine_g6_fr_dynamic import FAMILIES
from scripts.audit_g6_fr_segment_rounding import segment_oracle,explain,ROUNDING

ROOT=pathlib.Path(__file__).resolve().parents[1]
FIELDS=("national_id","source_id","station_id","evse_id","national_plug","national_kw","national_mode","tariff_signature","g6_calculability")
SCOPE=("nationalStationKey","nationalEvseKey","nationalConnectorKey","source_id","tariff_signature")
SESSION=("startAt","timeZone","energy","seconds","chargeSeconds","parkSeconds","includeCongestionFees")

def fixture(s):
    if not isinstance(s,dict) or set(s)!=set(SESSION): raise ValueError("SESSION_FIELDS_INVALID")
    if s["timeZone"]!="Europe/Paris" or type(s["includeCongestionFees"]) is not bool: raise ValueError("SESSION_ZONE_OR_CONGESTION_INVALID")
    if s["includeCongestionFees"] is False: raise ValueError("CONGESTION_EXCLUSION_NOT_PROVEN")
    if type(s["energy"]) not in (str,int,float): raise ValueError("SESSION_ENERGY_INVALID")
    if not isinstance(s["startAt"],str): raise ValueError("SESSION_START_INVALID")
    at,elapsed,charge,park,energy=session(s)
    return dict(id="request",startAt=at.isoformat(),seconds=elapsed,chargeSeconds=charge,parkSeconds=park,
                energy=str(energy),duration=str(dec(elapsed)/60),charging=str(dec(charge)/60),parking=str(dec(park)/60))

def result(decision,reason="",parts=None,canonical=None,segmented=None):
    return dict(decision=decision,reason=reason,currency="EUR",components=parts,
                canonical=canonical,segmented=segmented,estimateEur=parts["total"] if parts else None,
                diagnosticOnly=True,publicationEligible=False)

class QuoteGate:
    def __init__(self,offers,crosswalk,canonical,engine_sha,lineage):
        self.engine=ROOT/"migration/v9/g6-candidate/pricing-engine.cjs"
        verify(self.engine,engine_sha)
        self.lineage=dict(lineage)
        self.pairs={r["national_id"]:r for r in crosswalk}
        if len(self.pairs)!=len(crosswalk) or len({r["source_id"] for r in crosswalk})!=len(crosswalk): raise ValueError("Crosswalk uniqueness")
        by_offer={r["national_id"]:r for r in offers}
        if len(by_offer)!=len(offers) or set(by_offer)!=set(self.pairs): raise ValueError("Offer lineage")
        self.registry={}
        self.bound={}
        stations={s["id"]:s for s in canonical["stations"]}
        evses={e["id"]:e for e in canonical["evses"]}
        connectors={c["id"]:c for c in canonical["connectors"]}
        if any(len(x)!=len(canonical[k]) for x,k in ((stations,"stations"),(evses,"evses"),(connectors,"connectors"))): raise ValueError("Canonical uniqueness")
        for r in crosswalk:
            raw=by_offer[r["national_id"]]
            if any(raw[k]!=r[k] for k in FIELDS) or raw["raw_verified"]!="True":raise ValueError("Offer projection changed")
            sig=r["tariff_signature"]; payload=json.loads(raw["raw_price_payload"])
            if signature(payload)!=sig or raw["g6_calculability"] not in (EST,REVIEW):raise ValueError("Raw signature invalid")
            item=dict(raw=payload,family=raw["family"],baseline=raw["g6_calculability"]==EST)
            if sig in self.registry and self.registry[sig]!=item:raise ValueError("Signature collision")
            self.registry[sig]=item
            if r["publicationEligible"] is not False:raise ValueError("Publication scope")
            if r["reason"]!="EXACT_RUNTIME_CROSSWALK":
                if r["nationalConnectorKey"] is not None:raise ValueError("Rejected connector attached")
                continue
            sk,ek,ck=(r[k] for k in SCOPE[:3])
            s,e,c=stations[sk],evses[ek],connectors[ck]
            if s["sourceStationId"]!=r["station_id"] or e["officialEvseId"]!=r["evse_id"] or e["stationId"]!=sk or c["evseId"]!=ek or dec(c["powerKw"])!=dec(r["national_kw"]) or dec(r["national_kw"])<=0 or s.get("publicAccessDecision")=="exclude_non_public" or c["kind"]!=r["national_mode"]:
                raise ValueError("Canonical binding invalid")
            if ck in self.bound:raise ValueError("Duplicate target")
            self.bound[ck]=r
        self.prepared={sig:prepare(x["raw"],x["family"],x["baseline"],sig) for sig,x in self.registry.items()}

    def evaluate_signatures(self,requests):
        """Independent oracle and historical candidate on the supplied session.
        Shared computation only for identical verified signature + exact session."""
        verify(self.engine,self.lineage["candidateSha256"])
        output={};jobs=[];pending=[]
        for key,(sig,f) in requests.items():
            item=self.registry[sig];prepared=self.prepared[sig];family=item["family"]
            try:
                state,parts,detail=diagnose(prepared,f,family,item["baseline"])
                if parts is None:output[key]=result(state,state);continue
                rules=historical_rules(prepared,f,family)
            except (ValueError,TypeError,KeyError,ArithmeticError) as ex:
                output[key]=result("MODEL_REVIEW",str(ex));continue
            jobs.append(dict(signature=sig,fixture=f,rules=rules));pending.append((key,parts,family))
        if jobs:
            runner=ROOT/"scripts/replay_g6_fr_combined_windows_engine.cjs"
            response=json.loads(subprocess.run(["node",str(runner),str(self.engine)],input=j(jobs),text=True,capture_output=True,check=True,timeout=240).stdout)
            if len(response["results"])!=len(jobs) or len(response["guards"])!=4 or not all(response["guards"].values()):raise ValueError("Candidate guard failure")
            for (key,parts,family),job,r in zip(pending,jobs,response["results"]):
                if r["signature"]!=job["signature"] or r["scenario"]!=job["fixture"]["id"]:raise ValueError("Candidate order")
                if engine_agrees(parts,r):output[key]=result(PASS,parts=parts,canonical=parts);continue
                seg=None
                if family in FAMILIES:
                    try:seg,_=segment_oracle(job["rules"],job["fixture"])
                    except (ValueError,KeyError,TypeError,ArithmeticError):pass
                if seg is not None and explain(parts,seg,r):
                    output[key]=result(ROUNDING,parts=seg,canonical=parts,segmented=seg)
                else:output[key]=result("ENGINE_OR_ROUNDING_REVIEW","ENGINE_OR_ROUNDING_REVIEW")
        return output

    def quote(self,requests):
        results=[];pending={};jobs={}
        for i,r in enumerate(requests):
            if not isinstance(r,dict) or set(r)!=set(("country","channel","session",*SCOPE)):
                results.append(result("REQUEST_INVALID","REQUEST_FIELDS_INVALID"));continue
            if r["country"]!="FR" or r["channel"]!="Electroverse" or any(not isinstance(r[k],str) for k in SCOPE):
                results.append(result("SCOPE_REFUSED","COUNTRY_CHANNEL_OR_ID_INVALID"));continue
            p=self.bound.get(r["nationalConnectorKey"])
            if not p or any(r[k]!=p[k] for k in SCOPE):
                results.append(result("SCOPE_REFUSED","IDENTITY_OR_SIGNATURE_MISMATCH"));continue
            try:f=fixture(r["session"])
            except (ValueError,KeyError,TypeError,ArithmeticError) as ex:
                results.append(result("SESSION_REFUSED",str(ex)));continue
            key=(p["tariff_signature"],j(f));jobs[key]=(p["tariff_signature"],f)
            pending[i]=(key,r,p);results.append(None)
        quotes=self.evaluate_signatures(jobs)
        for i,(key,r,p) in pending.items():
            results[i]=dict(quotes[key],scope={k:r[k] for k in SCOPE},session=r["session"],nationalId=p["national_id"],lineage=self.lineage)
        return results,len(jobs)
