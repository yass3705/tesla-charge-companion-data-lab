#!/usr/bin/env python3
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
CFG=ROOT/"docs/v9-refresh-cadence.json"

def main():
    cfg=json.loads(CFG.read_text(encoding="utf-8"))
    assert cfg["policy"].startswith("collection-only")
    assert cfg["promotionRule"]
    ids=set()
    for row in cfg["refreshes"]:
        assert row["id"] not in ids, row["id"]
        ids.add(row["id"])
        p=ROOT/row["workflow"]
        assert p.exists(), f"missing workflow: {row['workflow']}"
        text=p.read_text(encoding="utf-8")
        cron=row["cron"]
        assert f"cron: \"{cron}\"" in text or f"cron: '{cron}'" in text, f"{row['id']} schedule drift: {cron}"
        assert "schedule:" in text, f"{row['id']} no schedule"
    print(json.dumps({"status":"ok","scheduledRefreshes":len(ids),"policy":cfg["policy"]}))

if __name__=="__main__":
    main()
