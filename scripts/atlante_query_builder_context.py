#!/usr/bin/env python3
import json,re,sys
from pathlib import Path
src=Path(sys.argv[1]).read_text(encoding='utf-8',errors='ignore')
anchors=['&includeCpos=','includeCpos','&excludeCpos=','getMapLocationsAsGuest','getMapLocations']
out=[]
for a in anchors:
    starts=[m.start() for m in re.finditer(re.escape(a),src,re.I)][:12]
    for p in starts:
        s=src[max(0,p-7000):min(len(src),p+7000)]
        # Remove comments/noise and mask all credential-shaped opaque constants.
        s=re.sub(r'(["\'])[A-Za-z0-9_+/=-]{24,120}\1',r'"<OPAQUE>"',s)
        s=re.sub(r'(?<![A-Za-z0-9])[A-Za-z0-9_+/=-]{28,120}(?![A-Za-z0-9])','<OPAQUE>',s)
        # Mask full URLs but preserve endpoint paths separately.
        s=re.sub(r'https?://[^\s"\']+','<URL>',s)
        out.append({'anchor':a,'context':s})
Path('data/reports/atlante_query_builder_context.json').parent.mkdir(parents=True,exist_ok=True)
Path('data/reports/atlante_query_builder_context.json').write_text(json.dumps({'contexts':out},ensure_ascii=False,indent=2)+'\n')
print({'contexts':len(out)})
