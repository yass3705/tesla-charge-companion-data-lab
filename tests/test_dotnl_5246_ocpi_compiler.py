#!/usr/bin/env python3
"""Regression checks: DOT-NL 5246 source-tariff compiler fixes.
Tests OCPI 2.2.1 hourly prices, FLAT restriction, energy Wh/parking seconds.
"""
from __future__ import annotations
import sys,unittest,datetime as dt
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import dotnl_netherlands_runtime as eng
TODAY=dt.date(2026,10,11)
def pc(typ,price,step=1):
    return {"type":typ,"priceInclVat":price,"stepSize":step}
def el(comps,restrictions=None):
    return {"priceComponents":comps,"restrictions":restrictions}
def t(elements,typ=None):
    return {"type":typ,"currency":"EUR","elements":elements}
def rule_at(rules,minute,day):
    for r in rules:
        if day in (r[11] or []):
            if eng.in_window(minute,r[1],r[2]):return r
    return None
class TariffTests(unittest.TestCase):
    def test_efl_zero_flat_with_weekday_daypart_and_fallback(self):
        orig=t([
            el([pc("FLAT",0),pc("TIME",0.41),pc("ENERGY",0.5717)],
               {"start_time":"16:00","end_time":"22:00",
                 "day_of_week":["MONDAY","TUESDAY","WEDNESDAY","THURSDAY","FRIDAY","SATURDAY","SUNDAY"]}),
            el([pc("FLAT",0),pc("TIME",0.41),pc("ENERGY",0.5417)])
        ])
        rules,error=eng.compile_tariff(orig,TODAY)
        self.assertIsNone(error)
        r1=rule_at(rules,17*60,0)
        r2=rule_at(rules,9*60,0)
        self.assertAlmostEqual(r1[5],0.5717)
        self.assertAlmostEqual(r2[5],0.5417)
        self.assertAlmostEqual(r1[6],0.41/60,places=8)
        self.assertAlmostEqual(r1[7],0.0)
        self.assertEqual(r1[13],{})
    def test_positive_flat_daypart_is_session_fee_not_hourly(self):
        orig=t([
            el([pc("FLAT",1.25),pc("ENERGY",.48)],
                {"start_time":"18:00","end_time":"21:00","day_of_week":["SUNDAY"]}),
            el([pc("FLAT",.50),pc("ENERGY",.46)])
        ])
        r,e=eng.compile_tariff(orig,TODAY)
        self.assertIsNone(e)
        self.assertEqual(rule_at(r,19*60,0)[7],1.25)
        self.assertEqual(rule_at(r,11*60,0)[7],.50)
        self.assertEqual(rule_at(r,19*60,1)[7],.50)
    def test_flat_zero_step_zero_is_valid(self):
        r,e=eng.compile_tariff(t([el([pc("FLAT",0,0)])]),TODAY)
        self.assertIsNone(e)
        self.assertEqual(r[0][7],0)
    def test_energy_1000_wh_rounding_preserved(self):
        r,e=eng.compile_tariff(t([el([pc("ENERGY",.57,1000)])]),TODAY)
        self.assertIsNone(e)
        self.assertEqual(r[0][13]["energyStepWh"],1000)
        self.assertAlmostEqual(r[0][5],.57)
    def test_time_900_seconds_is_step_not_price_unit(self):
        r,e=eng.compile_tariff(t([el([pc("TIME",6,900),pc("PARKING_TIME",1.45,900)])]),TODAY)
        self.assertIsNone(e)
        self.assertAlmostEqual(r[0][6],.1)
        self.assertAlmostEqual(r[0][8],1.45/60,places=8)
        self.assertEqual(r[0][13]["chargingTimeStepSeconds"],900)
        self.assertEqual(r[0][13]["parkingTimeStepSeconds"],900)
    def test_legacy_step_1_second_hourly_not_per_minute(self):
        r,e=eng.compile_tariff(t([el([pc("TIME",.41,1)])]),TODAY)
        self.assertIsNone(e)
        self.assertAlmostEqual(r[0][6],.41/60,places=8)
        self.assertEqual(r[0][13],{})
    def test_outdated_tariff_stays_unknown(self):
        r,e=eng.compile_tariff(t([el([pc("ENERGY",.35)],{"end_date":"2026-03-31"})]),TODAY)
        self.assertIsNone(r)
        self.assertEqual(e,"no_current_element")
    def test_duration_limited_flat_is_not_silently_removed(self):
        r,e=eng.compile_tariff(t([
            el([pc("FLAT",2)],{"min_duration":3600}),
            el([pc("FLAT",0)],{"max_duration":3600})
        ]),TODAY)
        self.assertIsNone(e)
        rr=r[0]
        bands=[b for b in rr[12] if b[0]=="FLAT"]
        self.assertTrue(bands)
        self.assertTrue(any(b[1]>=3600 and abs(b[3]-2)<1e-8 for b in bands))

if __name__=="__main__":unittest.main()
