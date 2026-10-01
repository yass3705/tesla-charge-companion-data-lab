#!/usr/bin/env python3
"""Sanitized shape-only inspection of public GET /api/chargers."""
from __future__ import annotations
import json
import urllib.request
from pathlib import Path

URL='https://map.watt.ma/api/chargers'
OUT=Path('artifacts/morocco-watt-chargers-shape/summary.json')
req=urllib.request.Request(URL, headers={'User-Agent':'TeslaChargeCompanion-PublicShapeProbe/1.0','Accept':'application/json'})
with urllib.request.urlopen(req, timeout=20) as r:
    payload=json.loads(r.read().decode('utf-8'))

def shape(value, depth=0):
    if depth >= 3:
        return {'type':type(value).__name__}
    if isinstance(value, list):
        result={'type':'list','length':len(value)}
        if value:
            result['first_item']=shape(value[0], depth+1)
        return result
    if isinstance(value, dict):
        keys=sorted(value.keys())
        result={'type':'dict','keys':keys[:80],'key_count':len(keys)}
        result['children']={k:shape(value[k], depth+1) for k in keys[:40]}
        return result
    return {'type':type(value).__name__}

out={
  'schema_version':1,
  'url':URL,
  'policy':{'read_only':True,'http_method':'GET','credentials_used':False,'cookies_used':False,'raw_values_committed':False},
  'payload_shape':shape(payload),
}
OUT.parent.mkdir(parents=True,exist_ok=True)
OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(out['payload_shape'],ensure_ascii=False))
