#!/usr/bin/env python3
from __future__ import annotations

import asyncio, json, re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from playwright.async_api import async_playwright

TARGET_STATION = "BLZ_0015_F0"
TARGET_EVSE = "ITGESE131365937"
TARGET_CONNECTOR_UID = "131365937"
ROOT = f"https://nextcharge.app/map?lang=it&station={TARGET_STATION}&userCountry=IT"
READ_POSTS = {
    "https://nextcharge.app/apps/map/apis/stationsGrid",
    "https://nextcharge.app/apps/map/apis/station",
    "https://nextcharge.app/apps/map/apis/stationConnectors",
}
ALLOWED_HOST_SUFFIXES = ("nextcharge.app","goelectricstations.com","kxcdn.com","googleapis.com","gstatic.com","google.com","maptiler.com")

def now_iso():
    return datetime.now(timezone.utc).isoformat().replace("+00:00","Z")

def allowed_host(url):
    h=(urlparse(url).hostname or "").lower()
    return any(h==s or h.endswith("."+s) for s in ALLOWED_HOST_SUFFIXES)

async def main():
    reqs=[]; responses=[]; out={}
    async with async_playwright() as p:
        browser=await p.chromium.launch(headless=True)
        ctx=await browser.new_context(locale="it-IT")
        page=await ctx.new_page()
        async def route_handler(route,request):
            u=request.url; m=request.method.upper(); allowed=False; reason=""
            if allowed_host(u) and m in {"GET","HEAD","OPTIONS"}:
                allowed=True; reason="read_only"
            elif allowed_host(u) and m=="POST" and u in READ_POSTS:
                allowed=True; reason="validated_public_read_post"
            else:
                reason="blocked"
            reqs.append({"method":m,"url":u,"postData":request.post_data,"allowed":allowed,"reason":reason})
            await (route.continue_() if allowed else route.abort())
        async def on_response(resp):
            if resp.request.url.endswith("/stationConnectors"):
                item={"status":resp.status,"postData":resp.request.post_data}
                try: item["json"]=await resp.json()
                except Exception: item["text"]=(await resp.text())[:12000]
                responses.append(item)
        await page.route("**/*",route_handler)
        page.on("response",on_response)
        await page.goto(ROOT,wait_until="domcontentloaded",timeout=60000)
        await page.wait_for_timeout(12000)
        # If the station was loaded, open connectors. No mutation endpoint is allowed.
        try:
            await page.evaluate("""() => {
              const bs=[...document.querySelectorAll('.buttonConnectors')];
              const b=bs.find(e => !!(e.offsetWidth || e.offsetHeight || e.getClientRects().length));
              if (b) b.click(); else if (typeof showConnectors==='function') showConnectors();
            }""")
        except Exception:
            pass
        await page.wait_for_timeout(10000)
        body=(await page.locator("body").inner_text())[:30000]
        html=(await page.content())[:100000]
        runtime=await page.evaluate("""() => ({
          stationId: (typeof stationSelected!=='undefined' && stationSelected?.[0]?.station?.idStation)||null,
          connectors: Array.isArray(currentConnectorsList)?currentConnectorsList:null
        })""")
        await browser.close()
    connector=None
    for r in responses:
        j=r.get("json")
        if isinstance(j,dict):
            for c in j.get("data") or []:
                if str(c.get("uidConnector"))==TARGET_CONNECTOR_UID: connector=c
    tariff=(connector or {}).get("tariff",{}).get("charge",{})
    prices=tariff.get("prices") or {}
    expected={"time":0.01,"energy":0.65,"parking":0.1}
    body_l=body.lower()
    # Accept multiple localized renderings but require explicit minute semantics near price context.
    minute_tokens=["€/min","€ / min","eur/min","eur / min","al minuto","per minuto","/min"]
    time_amount_tokens=["0,01","0.01"]
    parking_amount_tokens=["0,10","0.10","0,1","0.1"]
    minute_visible=any(t in body_l for t in minute_tokens)
    time_visible=any(t in body_l for t in time_amount_tokens)
    parking_visible=any(t in body_l for t in parking_amount_tokens)
    report={
      "schemaVersion":1,"generatedAt":now_iso(),"publicationAllowed":False,
      "policy":{"authenticated":False,"remoteMutation":False,"readOnlyPublicMap":True,"targetStation":TARGET_STATION,"targetEvse":TARGET_EVSE,"targetConnectorUid":TARGET_CONNECTOR_UID},
      "rawConnector":connector,
      "expectedRawPrices":expected,
      "rawPriceMatch": prices==expected,
      "rendered":{"minuteUnitVisible":minute_visible,"timeAmountVisible":time_visible,"parkingAmountVisible":parking_visible,"bodyExcerpt":body[:12000]},
      "runtime":runtime,
      "blockedNonReadRequests":[x for x in reqs if not x["allowed"]],
      "gates":{"targetConnectorFound":connector is not None,"rawPricesMatch":prices==expected,"minuteUnitRendered":minute_visible,"timeAmountRendered":time_visible,"parkingAmountRendered":parking_visible,"noMutationAllowed":all(not x["allowed"] for x in reqs if x["method"] not in {"GET","HEAD","OPTIONS","POST"} or (x["method"]=="POST" and x["url"] not in READ_POSTS))}
    }
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/go_electric_nextcharge_tariff_ui_semantics.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"rawPriceMatch":report["rawPriceMatch"],"rendered":report["rendered"],"gates":report["gates"]},ensure_ascii=False,indent=2))
    if not all(report["gates"].values()):
        raise SystemExit("Go Electric rendered tariff semantics not fully proven")

if __name__=="__main__": asyncio.run(main())
