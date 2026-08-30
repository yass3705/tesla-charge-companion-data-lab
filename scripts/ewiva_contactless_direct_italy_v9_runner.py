#!/usr/bin/env python3
from __future__ import annotations

import re
import time

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options

import ewiva_contactless_direct_italy_v9 as impl

ADDRESS_RE = re.compile(r"^(via|viale|corso|piazza|strada|s\.?\s*p\.?|s\.?\s*s\.?|contrada|localita|v\.|punto|lungomare|centro commerciale|fashion district|aeroporto)\b", re.I)
REGIONS = {
    "abruzzo","basilicata","calabria","campania","emilia romagna","friuli venezia giulia","lazio","liguria","lombardia","marche","molise","piemonte","puglia","sardegna","sicilia","toscana","trentino alto adige","umbria","valle d'aosta","veneto"
}


def add(rows, seen, city, address):
    city = " ".join(str(city or "").split())
    address = " ".join(str(address or "").split())
    key = (impl.norm(city), impl.norm(address))
    if not key[0] or not key[1] or key in seen:
        return
    if key[0] in REGIONS or any(x in key[0] for x in ("dove trovo", "pagamento", "scopri", "stazioni")):
        return
    seen.add(key)
    rows.append({"city": city, "address": address})


def rendered_pos_sites():
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1920,1200")
    opts.add_argument(f"--user-agent={impl.USER_AGENT}")
    driver = webdriver.Chrome(options=opts)
    try:
        driver.set_page_load_timeout(60)
        driver.get(impl.POS_LIST_URL)
        time.sleep(5)
        html = driver.page_source
        body_text = driver.find_element(By.TAG_NAME, "body").text
    finally:
        driver.quit()

    soup = BeautifulSoup(html, "html.parser")
    rows = []
    seen = set()

    # First pass: rendered heading/card structure.
    for heading in soup.find_all(["h3", "h4", "h5", "h6"]):
        city = heading.get_text(" ", strip=True)
        parent = heading.parent
        if not city or not parent:
            continue
        texts = [x.strip() for x in parent.stripped_strings if x.strip()]
        try:
            idx = texts.index(city)
        except ValueError:
            idx = -1
        candidates = texts[idx + 1 : idx + 8] if idx >= 0 else []
        address = next((x for x in candidates if ADDRESS_RE.search(x) and x.casefold() not in {"vai al sito", "go to site"}), None)
        if address:
            add(rows, seen, city, address)

    # Second pass: visible-text city/address pairs. This is intentionally strict.
    lines = [" ".join(x.split()) for x in body_text.splitlines() if x.strip()]
    for i in range(len(lines) - 1):
        city, address = lines[i], lines[i + 1]
        if len(city) > 100 or len(address) > 180:
            continue
        if ADDRESS_RE.search(address):
            add(rows, seen, city, address)

    if len(rows) < 50:
        raise RuntimeError(f"Rendered Ewiva POS parser found only {len(rows)} candidate sites")
    print(f"Rendered Ewiva POS sites: {len(rows)}")
    return rows


impl.extract_pos_sites = rendered_pos_sites

if __name__ == "__main__":
    impl.main()
