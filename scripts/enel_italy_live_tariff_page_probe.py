#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

URL = "https://www.enel.it/it-it/mobilita-elettrica/tariffe-abbonamenti"
OUT = Path("data/reports/enel_italy_live_tariff_page_probe.json")

PRICE_RE = re.compile(r"(\d+[,.]\d+)\s*€/kWh")
PLAN_NAMES = ["PlugAndGo Explorer", "PlugAndGo Super", "Pay Per Use Basic", "Pay Per Use Premium"]


def clean(text: str) -> str:
    return "\n".join(line.strip() for line in text.splitlines() if line.strip())


def excerpt(body: str, marker: str, span: int = 1500) -> str:
    pos = body.find(marker)
    if pos < 0:
        return ""
    return body[pos : pos + span]


def capture(driver: webdriver.Chrome, label: str) -> dict:
    body = clean(driver.find_element(By.TAG_NAME, "body").text)
    plans = {}
    for plan in PLAN_NAMES:
        txt = excerpt(body, plan)
        plans[plan] = {
            "excerpt": txt[:1200],
            "prices": [p.replace(",", ".") for p in PRICE_RE.findall(txt[:1200])],
        }
    return {"label": label, "bodyPrefix": body[:5000], "plans": plans}


def click_text(driver: webdriver.Chrome, text: str) -> list[dict]:
    results = []
    xpath = f"//*[normalize-space(text())='{text}']"
    for el in driver.find_elements(By.XPATH, xpath):
        try:
            displayed = el.is_displayed()
            rect = el.rect
            if not displayed or rect.get("width", 0) <= 0 or rect.get("height", 0) <= 0:
                continue
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
            driver.execute_script("arguments[0].click();", el)
            time.sleep(0.8)
            results.append({"tag": el.tag_name, "text": el.text, "clicked": True})
        except Exception as exc:
            results.append({"tag": getattr(el, "tag_name", None), "text": getattr(el, "text", None), "clicked": False, "error": f"{type(exc).__name__}: {exc}"})
    return results


def main() -> None:
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1440,1600")
    opts.add_argument("--lang=it-IT")
    driver = webdriver.Chrome(options=opts)
    try:
        driver.get(URL)
        time.sleep(5)
        # Best-effort cookie dismissal; absence is harmless.
        for needle in ["Accetta tutti", "Accetta", "Accept all"]:
            try:
                for el in driver.find_elements(By.XPATH, f"//*[contains(normalize-space(text()), '{needle}')]"):
                    if el.is_displayed():
                        driver.execute_script("arguments[0].click();", el)
                        time.sleep(0.5)
                        break
            except Exception:
                pass
        initial = capture(driver, "initial")
        day_clicks = click_text(driver, "Giorno")
        after_day = capture(driver, "after_click_giorno")
        night_clicks = click_text(driver, "Notte")
        after_night = capture(driver, "after_click_notte")
        payload = {
            "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "url": URL,
            "title": driver.title,
            "clicks": {"giorno": day_clicks, "notte": night_clicks},
            "captures": [initial, after_day, after_night],
        }
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(payload, ensure_ascii=False, indent=2)[:30000])
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
