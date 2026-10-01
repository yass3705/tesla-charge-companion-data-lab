#!/usr/bin/env python3
"""Extract current first-party Shell Recharge UK station tariff samples.

This intentionally excludes Shell_RP_* provider/eMSP tariff payloads.
Only rendered first-party find.shell.com station pages are accepted here.
"""
from __future__ import annotations
import argparse, html, json, re, time
from datetime import datetime, timezone
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140 Safari/537.36"

STATIONS=[
 {"key":"fulham","url":"https://find.shell.com/gb/fuel/10018937-shell-recharge-waitrose-fulham/en_US"},
 {"key":"john_abbott","url":"https://find.shell.com/gb/fuel/10018989-shell-little-waitrose-john-abbott/en_US"},
 {"key":"reading","url":"https://find.shell.com/gb/fuel/13027071-ev-waitrose-reading/en_NA"},
 {"key":"upper_street","url":"https://find.shell.com/gb/fuel/10018902-shell-upper-street/en_GB"},
 {"key":"buckden","url":"https://find.shell.com/gb/fuel/10019180-shell-buckden/en_GB"},
 {"key":"rise_park","url":"https://find.shell.com/gb/fuel/10018844-shell-rise-park/en_GB"},
 {"key":"newport","url":"https://find.shell.com/gb/fuel/10019063-shell-newport/en_GB"},
 {"key":"oak_lane","url":"https://find.shell.com/gb/fuel/10018864-shell-oak-lane/en_GB"},
 {"key":"fouroaks","url":"https://find.shell.com/gb/fuel/10019132-shell-fouroaks/en_GB"},
 {"key":"evesham","url":"https://find.shell.com/gb/fuel/13161670-ev-waitrose-evesham/en_US"},
 {"key":"aldi_deal","url":"https://find.shell.com/gb/fuel/13058729-ev-aldi-deal/en_GB"},
 {"key":"aldi_rugeley","url":"https://find.shell.com/gb/fuel/13152220-ev-aldi-rugeley/en_GB"},
 {"key":"lancaster","url":"https://find.shell.com/gb/fuel/10019267-shell-lancaster/en_GB"}
]

def norm(s:str)->str:
    return re.sub(r"\s+"," ",html.unescape(s or "")).strip()

def render(url:str)->dict:
    opts=webdriver.ChromeOptions()
    opts.add_argument("--headless=new"); opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage"); opts.add_argument("--disable-gpu")
    opts.add_argument("--lang=en-GB"); opts.add_argument(f"--user-agent={UA}")
    d=webdriver.Chrome(options=opts)
    try:
        d.get(url)
        WebDriverWait(d,30).until(lambda x: len((x.find_element(By.TAG_NAME,"body").text or "").strip())>100)
        for _ in range(10):
            corpus=norm((d.find_element(By.TAG_NAME,"body").text or "")+" "+(d.page_source or ""))
            low=corpus.lower().replace(",",".")
            vals=[float(x) for x in re.findall(r"(\d+(?:\.\d+)?)\s*£\s*/\s*kwh",low)]
            if not vals:
                vals=[float(x) for x in re.findall(r"shell app\s*\|?\s*£?\s*(\d+(?:\.\d+)?)\s*£?\s*/?\s*kwh",low)]
            powers=[int(float(x)) for x in re.findall(r"(\d{2,3}(?:\.0)?)\s*kw",low)]
            if vals:
                return {"gbpPerKwh":vals[0],"powerKwObserved":sorted(set(powers)),
                        "channel":"first_party_shell_app",
                        "evidenceMode":"current_rendered_first_party_station_page"}
            time.sleep(2)
        raise RuntimeError("no GBP/kWh Shell App tariff found")
    finally:
        d.quit()

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--out",default="out/shell_recharge_uk")
    args=ap.parse_args(); out=Path(args.out); out.mkdir(parents=True,exist_ok=True)
    rows=[]; errors=[]
    for s in STATIONS:
        try:
            x=render(s["url"]); rows.append({**s,**x}); print(s["key"],x,flush=True)
        except Exception as e:
            errors.append({"key":s["key"],"url":s["url"],"error":f"{type(e).__name__}: {e}"})
    if len(rows)<5:
        raise RuntimeError(f"insufficient UK Shell station samples: {len(rows)}; errors={errors}")
    prices=sorted(set(round(x["gbpPerKwh"],4) for x in rows))
    payload={
      "schemaVersion":"1.0.0",
      "dataset":"shell-recharge-official-uk",
      "generatedAt":datetime.now(timezone.utc).isoformat().replace("+00:00","Z"),
      "operator":"Shell Recharge","country":"UK",
      "tariffChannel":"first_party_shell_app",
      "emspExclusion":"Shell_RP_* provider/eMSP tariffs are excluded and are not inputs to this dataset.",
      "stationLevelPricing":True,
      "observedPriceClassesGbpPerKwh":prices,
      "representativeStationChecks":rows,
      "errors":errors,
      "classification":{
        "singleNationalTariff":False,
        "exactStationLookupRequired":True,
        "source":"official find.shell.com rendered station pages"
      }
    }
    (out/"shell_recharge_official_uk.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n")
    (out/"SUMMARY.md").write_text(
      "# Shell Recharge UK official station pricing\n\n"
      f"- Validated first-party station pages: **{len(rows)}**\n"
      f"- Observed Shell App price classes: **{', '.join(f'£{p:.2f}/kWh' for p in prices)}**\n"
      "- Pricing is station-level; no national tariff is inferred.\n"
      "- Shell_RP_* provider/eMSP tariffs are excluded.\n"
    )

if __name__=="__main__": main()
