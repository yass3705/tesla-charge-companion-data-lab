#!/usr/bin/env python3
"""Publish ONLY four exact Midhope Road guest-verified sockets for V9.
Requires screenshot/source evidence and a successful, pinned production engine QA.
This source is separate from the broader Connected Kerb dataset.
"""
import gzip, hashlib, json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
def read(path):
    p=ROOT/path
    with (gzip.open(p,"rt",encoding="utf8") if p.suffix==".gz" else open(p,encoding="utf8")) as f:return json.load(f)
def main():
    proof=read("reports/uk/connected-kerb-midhope-verified-2026-10-10.json")
    raw=read("data/national/uk_connected_kerb_locations.json.gz")
    assert proof["status"]=="customer_app_rates_verified_engine_not_activated"
    assert len(proof["verifiedExactSockets"])==4
    station_id="cd20ba89-4241-4b39-b738-514f49093e8d"
    candidates=[x for x in raw["locations"] if x.get("id")==station_id and x.get("publish") is True]
    assert candidates
    loc=max(candidates,key=lambda x:x.get("last_updated",""))
    assert loc.get("name")=="Midhope Road"
    assert loc.get("city")=="Woking"
    evses,offers=[],[]
    for source in proof["verifiedExactSockets"]:
        matches=[]
        for evse in loc["evses"]:
            for conn in evse["connectors"]:
                if evse.get("evse_id")==source["evseId"] and conn.get("id")==source["connectorId"]:
                    matches.append((evse,conn))
        assert len(matches)==1,source
        evse,conn=matches[0]
        assert str(evse.get("physical_reference"))==source["qrCode"]
        assert source["operatorLocationId"]==station_id
        assert source["appTariffId"]
        offer={
           "id":"connected-kerb-midhope-verified:"+source["connectorId"],
           "provider":"Connected Kerb","kind":"direct","countries":["GB"],"currency":"GBP",
           "stationIds":[station_id],"evseIds":[source["evseId"]],
           "connectorIds":[source["connectorId"]],
           "directOperatorOnly":True,"validFrom":"2026-10-10",
           "pricing":{"type":"connected_kerb_midhope_guest_verified",
               "verifiedSourceVersion":"2026-10-10-midhope-exact-4","includesVat":True,
               "energyPerKwhGbp":.39996,"parkingPerStarted30minGbp":.80004,
               "idleSupplementPerMinuteGbp":.01},
           "metadata":{"connectorId":source["connectorId"],
               "pricingScope":"cpo_direct_guest_exact_connector",
               "sourceEvidence":"midhope-guest-2026-10-10",
               "pricingTimeZone":"Europe/London",
               "scheduleBasis":"customer app 09:30-19:00 Europe/Paris = 08:30-18:00 Europe/London, including DST",
               "tariffObservedAt":"2026-10-10",
               "refreshPolicy":"revalidate exact CPO guest price on new tariff evidence; DST alone does not expire the price",
               "feeRateScope":"parked occupancy, no charging/idle double billing",
               "guestPreAuthorisationGbpNotCost":25,
               "winterEvidence":"not_confirmed_not_activated"}
        }
        offers.append(offer)
        evses.append({**evse,"connectors":[{**conn,"validatedV9Offer":offer}]})
    assert len({v["evse_id"] for v in evses})==4
    payload={"country":"GB","collectedAt":raw["collectedAt"],
        "source":"Connected Kerb guest app exact socket rates + user screenshots 2026-10-10",
        "activationPolicy":"Europe/London local time schedule; no DST-only expiration; revalidate price on new CPO evidence",
        "sources":[{"id":"connected-kerb-midhope-guest-verified","name":"Connected Kerb",
            "partyIdsExpected":["CK0"],"country":"GB","pricingScope":"cpo_direct_guest_exact_connector",
            "locations":[{**loc,"evses":evses}],"tariffs":[]}]}
    out=ROOT/"data/national/uk_connected_kerb_midhope_verified_v9.json.gz"
    with gzip.open(out,"wt",encoding="utf8") as f:json.dump(payload,f,ensure_ascii=False,separators=(",",":"))
    report={"schemaVersion":1,"sourceCollectedAt":raw["collectedAt"],
        "exactConnectorCount":len(offers),"exactStationCount":1,
        "stationId":station_id,"evseIds":sorted(v["evseIds"][0] for v in offers),
        "connectorIds":sorted(v["connectorIds"][0] for v in offers),
        "tariffValidFrom":"2026-10-10","tariffValidThrough":None,
        "winter":"Europe/London automatic DST conversion; tariff freshness independently reviewed",
        "evidence":"reports/uk/connected-kerb-midhope-verified-2026-10-10.json",
        "runtimeType":"connected_kerb_midhope_guest_verified",
        "stagedFile":"data/national/uk_connected_kerb_midhope_verified_v9.json.gz",
        "status":"local_time_dst_verified_exact_connector_candidate"}
    report_file=ROOT/"reports/uk/connected-kerb-midhope-runtime-stage-2026-10-10.json"
    report_file.write_text(json.dumps(report,indent=2)+"\n",encoding="utf8")
    print(json.dumps(report))
if __name__=="__main__":main()
