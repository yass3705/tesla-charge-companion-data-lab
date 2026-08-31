#!/usr/bin/env python3
"""Capture public NextCharge frontend network traffic without allowing mutations.

The browser loads the public map. GET/HEAD requests are allowed. Non-GET requests
are recorded then aborted, so the first pass can reveal runtime bootstrap/API URLs
and payloads without changing any remote state or initiating charging actions.
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from playwright.async_api import async_playwright

ROOT = "https://nextcharge.app/map?nextcharge=only"
ALLOWED_HOST_SUFFIXES = (
    "nextcharge.app",
    "goelectricstations.com",
    "kxcdn.com",
    "googleapis.com",
    "gstatic.com",
    "google.com",
)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def allowed_host(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return any(host == suffix or host.endswith("." + suffix) for suffix in ALLOWED_HOST_SUFFIXES)


def redact(headers: dict[str, str]) -> dict[str, str]:
    blocked = {"authorization", "cookie", "set-cookie", "proxy-authorization"}
    return {k: v for k, v in headers.items() if k.lower() not in blocked}


async def main() -> None:
    events: list[dict[str, object]] = []
    console: list[dict[str, str]] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(locale="en-US")
        page = await context.new_page()

        async def route_handler(route, request):
            method = request.method.upper()
            url = request.url
            record = {
                "time": now_iso(),
                "method": method,
                "url": url,
                "resourceType": request.resource_type,
                "headers": redact(await request.all_headers()),
                "postData": request.post_data,
                "allowed": False,
                "reason": "",
            }
            if not allowed_host(url):
                record["reason"] = "host_not_in_public_frontend_allowlist"
                events.append(record)
                await route.abort()
                return
            if method in {"GET", "HEAD", "OPTIONS"}:
                record["allowed"] = True
                record["reason"] = "read_only_method"
                events.append(record)
                await route.continue_()
                return
            record["reason"] = "non_get_recorded_and_blocked_first_pass"
            events.append(record)
            await route.abort()

        await page.route("**/*", route_handler)
        page.on("console", lambda msg: console.append({"type": msg.type, "text": msg.text[:2000]}))

        navigation_error = None
        try:
            await page.goto(ROOT, wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(15000)
        except Exception as exc:
            navigation_error = f"{type(exc).__name__}: {exc}"

        title = await page.title()
        final_url = page.url
        await browser.close()

    non_get = [e for e in events if e["method"] not in {"GET", "HEAD", "OPTIONS"}]
    interesting = [
        e for e in events
        if any(token in str(e["url"]).lower() for token in (
            "api", "station", "token", "session", "config", "setting", "user", "bootstrap", "grid"
        ))
    ]
    report = {
        "schemaVersion": 1,
        "generatedAt": now_iso(),
        "policy": {
            "publicFrontendOnly": True,
            "authenticated": False,
            "remoteMutation": False,
            "getHeadOptionsAllowed": True,
            "nonGetRequestsBlocked": True,
            "chargingActionsAllowed": False,
        },
        "rootUrl": ROOT,
        "finalUrl": final_url,
        "title": title,
        "navigationError": navigation_error,
        "requestCount": len(events),
        "nonGetCount": len(non_get),
        "interestingCount": len(interesting),
        "nonGetRequests": non_get,
        "interestingRequests": interesting,
        "allRequests": events,
        "console": console[-200:],
    }
    out = Path("artifacts/go_electric_nextcharge_network_capture.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "requestCount": len(events),
        "nonGetCount": len(non_get),
        "interestingCount": len(interesting),
        "navigationError": navigation_error,
    }, indent=2))
    for e in non_get[:50]:
        print(e["method"], e["url"], (e.get("postData") or "")[:800])


if __name__ == "__main__":
    asyncio.run(main())
