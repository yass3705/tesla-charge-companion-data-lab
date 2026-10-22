#!/usr/bin/env python3
"""Read-only OZECAR national tariff extractor for Tesla Charge Companion.

Authority chain:
1. OZECAR producer dataset on data.gouv.fr -> exact FROZE EVSE inventory.
2. Monta public driver deep link /d/{FROZE_EVSE} -> rendered public
   station/status/tariff text without login.

No authentication, payment, charge start or write operation is performed.
Private/unresolved EVSEs are retained fail-closed.
"""
from __future__ import annotations
import argparse, asyncio, csv, datetime as dt, io, json, pathlib, re, urllib.request
from collections import Counter

DATASET_ID="65f3112cc53fbbd3b1d7208b"
DATASET_API=f"https://www.data.gouv.fr/api/1/datasets/{DATASET_ID}/"
MONTA_BASE="https://app.monta.app/d/"
UA="Tesla-Charge-Companion-OZECAR-ReadOnly/1.0"
EVSE_RE=re.compile(r"^FR\*?OZE\*?E",re.I)
MONEY_RE=re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:€|EUR)\s*(?:/\s*)?(kWh|min(?:ute)?|session)?",re.I)
STATUS_WORDS=("available","busy","charging","occupied","unavailable","out of order","private charger")
PRICE_TYPES=("dynamic price","fixed price")
PUBLIC_IRVE_FIELDS=(
    "id_station_itinerance", "id_station_local", "nom_station", "adresse_station",
    "code_insee_commune", "coordonneesXY", "id_pdc_itinerance", "id_pdc_local",
    "puissance_nominale", "prise_type_ef", "prise_type_2", "prise_type_combo_ccs",
    "prise_type_chademo", "prise_type_autre", "condition_acces",
    "date_mise_en_service", "date_maj", "nom_operateur",
)
PUBLIC_LIVE_FIELDS=("status", "pricingType", "priceComponents", "evse", "url", "httpStatus", "resolved")

def public_fields(row, fields):
    return {key: row[key] for key in fields if key in row}

def get_bytes(url,timeout=60):
    req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"application/json,text/csv,*/*"})
    with urllib.request.urlopen(req,timeout=timeout) as r:return r.read()

def latest_csv():
    meta=json.loads(get_bytes(DATASET_API).decode())
    resources=[r for r in meta.get("resources",[]) if str(r.get("format","")).lower()=="csv" and r.get("url")]
    if not resources: raise RuntimeError("No CSV resource in OZECAR dataset")
    resources.sort(key=lambda r:(r.get("last_modified") or r.get("latest") or r.get("created") or ""),reverse=True)
    r=resources[0]
    return r,get_bytes(r["url"])

def decode_csv(raw):
    text=None
    for enc in ("utf-8-sig","utf-8","cp1252"):
        try:text=raw.decode(enc);break
        except UnicodeDecodeError:pass
    if text is None: raise RuntimeError("Unable to decode CSV")
    sample=text[:8192]
    try: dialect=csv.Sniffer().sniff(sample,delimiters=",;\t")
    except csv.Error: dialect=csv.excel
    return list(csv.DictReader(io.StringIO(text),dialect=dialect))

def norm(v):return re.sub(r"[^A-Z0-9]","",str(v or "").upper())

def inventory(rows):
    by={}
    for row in rows:
        evse=str(row.get("id_pdc_itinerance") or "").strip()
        if not EVSE_RE.match(evse): continue
        key=norm(evse)
        prev=by.get(key)
        if prev is None or str(row.get("date_maj") or "")>=str(prev.get("date_maj") or ""): by[key]=row
    return by

def parse_text(text):
    clean="\n".join(x.strip() for x in text.splitlines() if x.strip())
    low=clean.lower()
    prices=[]
    for m in MONEY_RE.finditer(clean):
        value=float(m.group(1).replace(",","."))
        unit=(m.group(2) or "").lower()
        if value>1000: continue
        # Unitless amounts can be either a fixed tariff fee or the live total of an
        # ongoing session. Only accept unitless values that are explicitly
        # adjacent to fee wording; never promote arbitrary session totals.
        raw_match=m.group(0)
        if not unit:
            left=clean[max(0,m.start()-80):m.start()].lower()
            right=clean[m.end():min(len(clean),m.end()+80)].lower()
            fee_ctx=left+" "+right
            if not any(token in fee_ctx for token in ("fee","frais","start","démarrage","demarrage","session fee","additional fee")):
                continue
        prices.append({"value":value,"currency":"EUR","unit":unit or None,"raw":raw_match})
    # De-duplicate preserving order.
    seen=set(); unique=[]
    for p in prices:
        k=(p["value"],p["unit"])
        if k not in seen: seen.add(k);unique.append(p)
    status=next((s for s in STATUS_WORDS if s in low),None)
    pricing_type=next((s for s in PRICE_TYPES if s in low),None)
    return {"status":status,"pricingType":pricing_type,"priceComponents":unique,"text":clean[:12000]}

async def one(context,evse,sem):
    async with sem:
        page=await context.new_page()
        url=MONTA_BASE+evse
        try:
            resp=await page.goto(url,wait_until="domcontentloaded",timeout=45000)
            try: await page.wait_for_timeout(2500)
            except Exception: pass
            text=await page.locator("body").inner_text(timeout=10000)
            parsed=parse_text(text)
            parsed.update({"evse":evse,"url":url,"httpStatus":resp.status if resp else None,"resolved":bool(parsed["priceComponents"]),"error":None})
            return parsed
        except Exception as e:
            return {"evse":evse,"url":url,"resolved":False,"priceComponents":[],"status":None,"pricingType":None,"error":f"{type(e).__name__}: {e}"}
        finally:
            await page.close()

async def run_all(evses,workers):
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser=await p.chromium.launch(headless=True)
        context=await browser.new_context(user_agent=UA,locale="fr-FR")
        sem=asyncio.Semaphore(max(1,workers))
        results=await asyncio.gather(*(one(context,e,sem) for e in evses))
        await browser.close()
        return results

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--workers",type=int,default=6)
    ap.add_argument("--max-evses",type=int,default=0)
    ap.add_argument("--out",required=True);ap.add_argument("--report",required=True)
    args=ap.parse_args()
    resource,raw=latest_csv(); rows=decode_csv(raw); inv=inventory(rows)
    keys=sorted(inv)
    if args.max_evses: keys=keys[:args.max_evses]
    # Use producer spelling for public deep link; normalized IDs are only keys.
    evses=[str(inv[k]["id_pdc_itinerance"]).strip() for k in keys]
    results=asyncio.run(run_all(evses,args.workers))
    technical_errors=[r.get("evse") for r in results if r.get("error")]
    by_norm={norm(r["evse"]):r for r in results}
    records=[]
    for k in keys:
        live=by_norm.get(k,{})
        records.append({"evseKey":k,"irve":public_fields(inv[k],PUBLIC_IRVE_FIELDS),"live":public_fields(live,PUBLIC_LIVE_FIELDS),"directTariff":live.get("priceComponents") or [],"rankableDirect":bool(live.get("resolved")) and live.get("status")!="private charger"})
    resolved=[r for r in records if r["rankableDirect"]]
    private=[r for r in records if (r["live"].get("status")=="private charger")]
    unresolved=[r for r in records if not r["rankableDirect"] and r not in private]
    signatures=Counter(json.dumps(r["directTariff"],sort_keys=True,ensure_ascii=False) for r in resolved)
    now=dt.datetime.now(dt.timezone.utc).isoformat()
    payload={"schemaVersion":1,"country":"FR","cpo":"OZECAR","generatedAt":now,
      "source":{"inventory":{"authority":"OZECAR producer data.gouv.fr","datasetId":DATASET_ID,"resourceId":resource.get("id"),"resourceUrl":resource.get("url"),"lastModified":resource.get("last_modified")},
      "live":{"authority":"Monta public driver surface","template":MONTA_BASE+"{id_pdc_itinerance}","authentication":"none","readOnly":True}},
      "records":records}
    report={"schemaVersion":1,"country":"FR","cpo":"OZECAR","generatedAt":now,
      "producerRows":len(rows),"uniqueFrozeEvses":len(inv),"queriedEvses":len(records),
      "rankableDirect":len(resolved),"private":len(private),"unresolved":len(unresolved),
      "coveragePct":round(100*len(resolved)/len(records),2) if records else 0,
      "pricingTypes":dict(Counter((r["live"].get("pricingType") or "<unspecified>") for r in resolved)),
      "statusCounts":dict(Counter((r["live"].get("status") or "<unspecified>") for r in records)),
      "uniqueTariffSignatures":len(signatures),
      "tariffSignatures":[{"count":n,"components":json.loads(s)} for s,n in signatures.most_common()],
      "privateEvses":[r["irve"].get("id_pdc_itinerance") for r in private],
      "unresolvedEvses":[r["irve"].get("id_pdc_itinerance") for r in unresolved],
      "technicalErrorEvses":technical_errors,
      "classification":{"exactEvseOnly":True,"nationalConstantAllowed":False,"privateOrUnresolved":"fail_closed_then_TCC_fallback","preserveComponents":True}}
    for path,obj in ((args.out,payload),(args.report,report)):
        p=pathlib.Path(path);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=="__main__":main()
