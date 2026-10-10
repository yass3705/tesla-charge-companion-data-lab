#!/usr/bin/env python3
"""Midhope Road UK — reconcile customer screenshots against exact CK guest tariffs.

Evidence first. Preserve all four socket-specific identities; generate a
manual CPO override CANDIDATE only, not an automatically rankable V9 offer.
"""
import csv
import json
from pathlib import Path
from datetime import datetime,timezone
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1]
DEEP=ROOT/"reports/uk/connected-kerb-deep-fee-evidence-2026-10-10.json"
P1=ROOT/"reports/uk/connected-kerb-priority-ambiguities-2026-10-10.csv"
OUT=ROOT/"reports/uk/connected-kerb-midhope-verified-2026-10-10.json"
CANDIDATE=ROOT/"v9-production-runtime/data/v9/uk-connected-kerb-midhope-guest.candidate.json"
IDS={"GB*CK0*E19825","GB*CK0*E19865","GB*CK0*E19716","GB*CK0*E19707"}

def main():
    raw=json.loads(DEEP.read_text(encoding="utf-8"))
    midhope=[r for r in raw["records"] if r["stationName"]=="Midhope Road" and r["reason"]=="fee_unit_verification_pending"]
    assert len(midhope)==4
    assert {r["evseId"] for r in midhope}==IDS
    with P1.open(newline="",encoding="utf-8") as fh:
        shortlist=[r for r in csv.DictReader(fh) if r["stationName"]=="Midhope Road"]
    assert len(shortlist)==4
    evidence=[]
    for row in midhope:
        assert len(row["socketEvidence"])==1
        entry=row["socketEvidence"][0]
        assert len(entry["unifiedMatchingTariffs"])==1
        unified=entry["unifiedMatchingTariffs"][0]
        assert len(entry["fullTariffSpecification"])==1
        spec=entry["fullTariffSpecification"][0]
        assert unified["id"]==spec["id"]
        assert spec["tariffOption"]=="REGULAR"
        assert "Parking fee: £1.60/hour" in spec["description"]
        assert "Monday - Saturday 08:30-18:00" in spec["description"]
        assert "Energy: £0.40p/kWh" in spec["description"]
        slices=unified["slices"]
        assert set(slices)=={"CHARGING_TIME","IDLE_TIME","ENERGY"}
        assert len(slices["CHARGING_TIME"])==len(slices["IDLE_TIME"])==len(slices["ENERGY"])==1
        energy=slices["ENERGY"][0]
        charging=slices["CHARGING_TIME"][0]
        idle=slices["IDLE_TIME"][0]
        assert abs(energy["price"]-.39996)<.00001
        for component in (charging,idle):
            assert abs(component["price"]-.80004)<.00001
            assert component["stepSize"]==1800
            assert component["startTime"]=="07:30:00" and component["endTime"]=="17:00:00"
            assert component["dayOfWeek"]==["MONDAY","TUESDAY","WEDNESDAY","THURSDAY","FRIDAY","SATURDAY"]
        assert entry["qrCode"]==row["physicalReference"]
        proof={
            "evseId":row["evseId"],"connectorId":row["connectorId"],
            "qrCode":entry["qrCode"],"operatorLocationId":row["locationId"],
            "appSocketId":entry["socketId"],"appTariffId":unified["id"],
            "originalOcpiTariffIds":[x["tariffId"] for x in row["operatorOcpiTariffElements"]],
            "originalOcpiGrossGbpPerHourTimeAndParking":[
                round(x["components"][0]["price"]*1.2,5)
                for x in row["operatorOcpiTariffElements"]
                if x["components"][0]["type"] in ("TIME","PARKING_TIME")],
            "appEnergyGbpPerKwhGross":energy["price"],
            "appParkingRawGbpPer1800SecondsGross":charging["price"],
            "appIdleTimeParkingRawGbpPer1800SecondsGross":idle["price"],
        }
        assert proof["originalOcpiGrossGbpPerHourTimeAndParking"]==[.80004,.80004]
        evidence.append(proof)
    assert len({r["connectorId"] for r in evidence})==4
    # Screenshot is displayed with Europe/Paris local time (user in France).
    when=datetime(2026,10,10,7,30,tzinfo=timezone.utc)
    assert when.astimezone(ZoneInfo("Europe/London")).strftime("%H:%M")=="08:30"
    assert when.astimezone(ZoneInfo("Europe/Paris")).strftime("%H:%M")=="09:30"
    # 1.60 GBP per clock hour is 2 started half-hour tariff blocks of 0.80004,
    # rounded by the customer-facing display to pence. Do not double-charge
    # TIME and PARKING_TIME on top of the parking fee: alternative phases.
    assert round(2*.80004,2)==1.60
    candidate={
        "schemaVersion":1,"country":"GB","operator":"Connected Kerb",
        "station":"Midhope Road","city":"Woking","postalCode":"GU22 7LQ",
        "status":"customer_app_rates_verified_engine_not_activated",
        "verifiedExactSockets":evidence,
        "evidence":{
            "type":"user-supplied-first-party-guest-app-screenshots",
            "screenshots":["IMG_8107.png","IMG_8108.png"],
            "capturedAtLocalDisplay":"2026-10-10 14:19 Europe/Paris",
            "guestAuthorization":"payment card / Apple Pay, guest account",
            "scope":"app socket 19865 visible, socket 19707 visible; four matching socket details verified by CK guest source",
        },
        "pricing":{
            "currency":"GBP","includesVat":True,
            "energyGbpPerKwhDisplayed":.40,"energyGbpPerKwhSource":.39996,
            "parkingGbpPerHourDisplayed":1.60,
            "parkingGbpPerStarted30MinutesSource":.80004,
            "parkingSourceStepSeconds":1800,
            "parkingPhases":"charging and non-charging time, alternative occupancy phases not additive",
            "parkingSourceUtc":{"start":"07:30","end":"17:00","daysOfWeek":[1,2,3,4,5,6]},
            "parkingDescriptionLondonSummer":{"start":"08:30","end":"18:00"},
            "parkingScreenshotParisSummer":{"start":"09:30","end":"19:00"},
            "parkingSunday":"free",
            "idleSupplementGbpPerMinute":.01,
            "idleSupplementCondition":"vehicle is not charging; separate from occupancy parking fee",
            "guestPreAuthorizationGbp":25,
            "guestPreAuthorizationCountedAsSessionCost":False,
            "precision":"customer-facing hourly 2 decimals; raw source fractional pence preserved",
        },
        "guardrails":[
            "No double billing the raw CHARGING_TIME and IDLE_TIME parking phase on same minutes",
            "No automatic 20 percent UK VAT reapplication; customer values already gross",
            "Do not include preauthorization in session price",
            "Winter time adjustment from guest app must be reverified; current 07:30 UTC schedule is a source observation, not a perpetual UK local schedule",
            "Billing rounding across change of occupancy phase/window and idle supplement not validated by receipt",
            "No V9 promotion without exact connector binding and timed/phase billing engine regression",
        ]
    }
    OUT.write_text(json.dumps(candidate,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    CANDIDATE.parent.mkdir(parents=True,exist_ok=True)
    CANDIDATE.write_text(json.dumps(candidate,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("UK_MIDHOPE_EVIDENCE="+json.dumps({
      "count":len(evidence),"customerRateGbpPerKwh":.4,
      "parkingGbpPerHour":1.6,"parkingSourcePer30Min":.80004,
      "idleGbpPerMinute":.01,"preAuthGbpNotFee":25,
      "winterAndCrossPhaseBillingPending":True,"activated":False,
    }))
if __name__=="__main__":main()
