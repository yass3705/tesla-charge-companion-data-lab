#!/usr/bin/env python3
"""Create a sanitized inventory of current myAtlante endpoint/query strings from decompiled code."""
import json,re,sys
from pathlib import Path
src=Path(sys.argv[1]).read_text(encoding='utf-8',errors='ignore')
# quoted literals only; exclude opaque credential-like values
vals=[]
for q,s in re.findall(r'''(["'])(.{1,240}?)\1''',src,re.S):
    if '\n' in s: continue
    low=s.lower()
    if any(k in low for k in ('map-location','map_location','locations/','/locations','tariff','include-cpo','includecpo','cpo','latlong','connector','evsetype','locationstatus')):
        if re.fullmatch(r'[A-Za-z0-9_+/=-]{24,96}',s):
            continue
        vals.append(s)
# Also gather identifier-like query parameter names from textual neighborhoods.
anchors=[]
for m in re.finditer(r'map-locations|mapLocations|map_locations|includeCpos|latLongBottomLeft|latLongTopRight',src,re.I):
    reg=src[max(0,m.start()-3000):min(len(src),m.end()+3000)]
    # mask opaque strings defensively
    reg=re.sub(r'(["\'])[A-Za-z0-9_+/=-]{24,96}\1',r'"<opaque>"',reg)
    ids=sorted(set(re.findall(r'\b[A-Za-z_][A-Za-z0-9_]{2,50}\b',reg)))
    anchors.append({'anchor':m.group(0),'identifiers':[x for x in ids if any(k in x.lower() for k in ('map','location','cpo','lat','long','evse','connector','status','filter','tenant','country'))][:120]})
out={'endpointStrings':sorted(set(vals))[:600],'anchorContexts':anchors[:80]}
Path('data/reports/atlante_bundle_endpoint_inventory.json').parent.mkdir(parents=True,exist_ok=True)
Path('data/reports/atlante_bundle_endpoint_inventory.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'endpointStringCount':len(out['endpointStrings']),'anchorCount':len(out['anchorContexts'])},indent=2))
