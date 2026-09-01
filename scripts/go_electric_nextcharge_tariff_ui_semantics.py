#!/usr/bin/env python3
from __future__ import annotations

import asyncio, json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from playwright.async_api import async_playwright

TARGETS = [
    {"name":"onNoEnergyDelivery","station":"BLZ_0015_F0","evse":"ITGESE131365937","uid":"131365937","expected":{"time":0.01,"energy":0.65,"parking":0.1}},
    {"name":"onAfterTime","station":"40802612.00032","evse":"ITGESE800678718","uid":"800678718","expected":{"session":0.4,"time":0.01,"energy":0.65,"parking":0.08}},
]
READ_POSTS={
    "https://nextcharge.app/apps/map/apis/stationsGrid",
    "https://nextcharge.app/apps/map/apis/station",
    "https://nextcharge.app/apps/map/apis/stationConnectors",
}
ALLOWED_HOST_SUFFIXES=("nextcharge.app","goelectricstations.com","kxcdn.com","googleapis.com","gstatic.com","google.com","maptiler.com")

def now_iso(): return datetime.now(timezone.utc).isoformat().replace("+00:00","Z")
def allowed_host(url):
    h=(urlparse(url).hostname or "").lower()
    return any(h==s or h.endswith("."+s) for s in ALLOWED_HOST_SUFFIXES)

async def capture(browser,target):
    ctx=await browser.new_context(locale="it-IT")
    page=await ctx.new_page(); reqs=[]; responses=[]
    async def route_handler(route,request):
        u=request.url; m=request.method.upper(); allowed=False; reason=""
        if allowed_host(u) and m in {"GET","HEAD","OPTIONS"}: allowed=True; reason="read_only"
        elif allowed_host(u) and m=="POST" and u in READ_POSTS: allowed=True; reason="validated_public_read_post"
        else: reason="blocked"
        reqs.append({"method":m,"url":u,"postData":request.post_data,"allowed":allowed,"reason":reason})
        await (route.continue_() if allowed else route.abort())
    async def on_response(resp):
        if resp.request.url.endswith("/stationConnectors"):
            item={"status":resp.status,"postData":resp.request.post_data}
            try:item["json"]=await resp.json()
            except Exception:item["text"]=(await resp.text())[:12000]
            responses.append(item)
    await page.route("**/*",route_handler); page.on("response",on_response)
    root=f"https://nextcharge.app/map?lang=it&station={target['station']}&userCountry=IT"
    await page.goto(root,wait_until="domcontentloaded",timeout=60000); await page.wait_for_timeout(12000)
    try:
        await page.evaluate("""() => {const bs=[...document.querySelectorAll('.buttonConnectors')];const b=bs.find(e=>!!(e.offsetWidth||e.offsetHeight||e.getClientRects().length));if(b)b.click();else if(typeof showConnectors==='function')showConnectors();}""")
    except Exception: pass
    await page.wait_for_timeout(10000)
    body=(await page.locator("body").inner_text())[:30000]
    runtime=await page.evaluate("""() => ({stationId:(typeof stationSelected!=='undefined'&&stationSelected?.[0]?.station?.idStation)||null,connectors:Array.isArray(currentConnectorsList)?currentConnectorsList:null})""")
    connector=None
    for r in responses:
        j=r.get("json")
        if isinstance(j,dict):
            for c in j.get("data") or []:
                if str(c.get("uidConnector"))==target["uid"]: connector=c
    if connector is None:
        for c in runtime.get("connectors") or []:
            if str(c.get("uidConnector"))==target["uid"]: connector=c
    tariff=(connector or {}).get("tariff",{}).get("charge",{})
    prices=tariff.get("prices") or {}; restrictions=tariff.get("restrictions") or {}
    body_l=body.lower()
    minute_visible=any(t in body_l for t in ["€/min","€ / min","eur/min","eur / min","al minuto","per minuto","/min"])
    result={"target":target,"rawConnector":connector,"rawPriceMatch":prices==target["expected"],"restrictions":restrictions,
            "rendered":{"minuteUnitVisible":minute_visible,"bodyExcerpt":body[:16000]},"blockedNonReadRequests":[x for x in reqs if not x["allowed"]]}
    await ctx.close(); return result

async def main():
    async with async_playwright() as p:
        browser=await p.chromium.launch(headless=True)
        results=[]
        for target in TARGETS: results.append(await capture(browser,target))
        await browser.close()
    no_energy=next(x for x in results if x["target"]["name"]=="onNoEnergyDelivery")
    after=next(x for x in results if x["target"]["name"]=="onAfterTime")
    after_r=(after.get("restrictions") or {}).get("parking") or {}
    after_seconds=after_r.get("afterTime")
    report={"schemaVersion":2,"generatedAt":now_iso(),"publicationAllowed":False,
      "policy":{"authenticated":False,"remoteMutation":False,"readOnlyPublicMap":True},"captures":results,
      "derived":{"timeAndParkingUnit":"EUR_per_minute" if all(x["rendered"]["minuteUnitVisible"] for x in results) else None,
                 "onNoEnergyDeliveryMeaning":"post_charge_connected_time",
                 "onAfterTimeSeconds":after_seconds,
                 "onAfterTimeMinutes":(float(after_seconds)/60 if isinstance(after_seconds,(int,float)) else None)},
      "gates":{"bothConnectorsFound":all(x["rawConnector"] is not None for x in results),"rawPricesMatch":all(x["rawPriceMatch"] for x in results),
               "minuteUnitsRendered":all(x["rendered"]["minuteUnitVisible"] for x in results),"onAfterTimeTriggerCaptured":after_r.get("trigger")=="onAfterTime",
               "onAfterTimeThresholdCaptured":isinstance(after_seconds,(int,float)) and after_seconds>0,
               "noMutationAllowed":all(not x["blockedNonReadRequests"] for x in results)}}
    Path("artifacts").mkdir(exist_ok=True); Path("artifacts/go_electric_nextcharge_tariff_ui_semantics.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"derived":report["derived"],"gates":report["gates"],"afterTimeExcerpt":after["rendered"]["bodyExcerpt"]},ensure_ascii=False,indent=2))
    if not all(report["gates"].values()): raise SystemExit("Go Electric rendered tariff semantics not fully proven")

if __name__=="__main__": asyncio.run(main())
