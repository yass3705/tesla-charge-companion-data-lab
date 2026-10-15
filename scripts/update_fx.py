#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.request import Request, urlopen

SUPPORTED = (
    "EUR", "CHF", "GBP", "NOK", "SEK", "DKK", "PLN",
    "CZK", "HUF", "RON", "BGN", "MAD", "DZD", "TND",
)
PRIMARY_URL = "https://api.frankfurter.dev/v2/rates?base=EUR&quotes=CHF,GBP,NOK,SEK,DKK,PLN,CZK,HUF,RON,BGN,MAD,DZD,TND"
FALLBACK_URL = "https://open.er-api.com/v6/latest/EUR"
USER_AGENT = "TeslaChargeCompanion/7.1.0"


def fetch_json(url: str) -> dict:
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def read_previous(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {"rates": {"EUR": 1}}


def filter_rates(raw: dict) -> dict[str, float]:
    rates = {"EUR": 1.0}
    for code in SUPPORTED:
        value = raw.get(code)
        if code == "EUR":
            continue
        if isinstance(value, (int, float)) and value > 0:
            rates[code] = float(value)
    return rates


def provider_date(value: object) -> str | None:
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc).date().isoformat()
    if isinstance(value, str) and value.strip():
        raw = value.strip()
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00")).date().isoformat()
        except ValueError:
            pass
        try:
            return parsedate_to_datetime(raw).date().isoformat()
        except (TypeError, ValueError, OverflowError):
            return raw[:10] if len(raw) >= 10 else raw
    return None


def main() -> int:
    now = datetime.now(timezone.utc)
    checked_at = now.replace(microsecond=0).isoformat().replace("+00:00", "Z")
    data_dir = Path("data/fx")
    data_dir.mkdir(parents=True, exist_ok=True)
    rates_path = data_dir / "exchange_rates.json"
    previous = read_previous(rates_path)
    previous_rates = filter_rates(previous.get("rates", {}))

    source = ""
    remote_raw: object = None
    fresh_rates: dict[str, float] = {}

    try:
        rows = fetch_json(PRIMARY_URL)
        if not isinstance(rows, list) or not rows:
            raise RuntimeError("Réponse Frankfurter v2 invalide")
        frankfurter_rates = {}
        dates = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            quote = row.get("quote")
            rate = row.get("rate")
            if quote in SUPPORTED and isinstance(rate, (int, float)) and rate > 0:
                frankfurter_rates[quote] = float(rate)
            if isinstance(row.get("date"), str):
                dates.append(row["date"])
        fresh_rates = filter_rates(frankfurter_rates)
        if len(fresh_rates) < len(SUPPORTED):
            missing_primary = [code for code in SUPPORTED if code not in fresh_rates]
            raise RuntimeError("Devises absentes chez Frankfurter: " + ", ".join(missing_primary))
        remote_raw = max(dates) if dates else None
        source = "api.frankfurter.dev/v2"
    except Exception as primary_error:
        data = fetch_json(FALLBACK_URL)
        if data.get("result") not in (None, "success"):
            raise RuntimeError(data.get("error-type") or "Réponse de secours invalide")
        fresh_rates = filter_rates(data.get("rates", {}))
        remote_raw = data.get("time_last_update_utc") or data.get("time_last_update_unix")
        source = f"open.er-api.com (secours; Frankfurter indisponible: {type(primary_error).__name__})"

    merged = {**previous_rates, **fresh_rates, "EUR": 1.0}
    missing = [code for code in SUPPORTED if code not in merged]
    if missing:
        raise RuntimeError("Taux manquants sans valeur précédente : " + ", ".join(missing))

    published_date = provider_date(remote_raw) or now.date().isoformat()
    out = {
        "base": "EUR",
        "date": published_date,
        "providerDate": remote_raw,
        "checkedAt": checked_at,
        "source": source,
        "rates": {code: merged[code] for code in SUPPORTED},
    }
    rates_path.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    metadata_path = data_dir / "metadata.json"
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        metadata = {}
    metadata["version"] = "7.1.0"
    metadata["fxUpdated"] = published_date
    metadata["fxCheckedAt"] = checked_at
    metadata["fxSource"] = source
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"Source              : {source}")
    print(f"Date source         : {published_date}")
    print(f"Vérification UTC    : {checked_at}")
    print(f"CHF                 : {out['rates']['CHF']}")
    print(f"GBP                 : {out['rates']['GBP']}")
    print(f"MAD                 : {out['rates']['MAD']}")
    print(f"{len(out['rates'])} devises enregistrées dans {rates_path}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
