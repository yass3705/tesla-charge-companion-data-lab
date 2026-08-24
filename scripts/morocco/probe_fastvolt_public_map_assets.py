#!/usr/bin/env python3
import json, re, sys
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

BASE = "https://www.fastvolt.net/carte"
MAX_ASSETS = 20
MAX_BYTES = 2_000_000
UA = "TeslaChargeCompanionDataLab/1.0 (+public read-only diagnostics)"

class P(HTMLParser):
    def __init__(self):
        super().__init__(); self.scripts=[]; self.links=[]
    def handle_starttag(self, tag, attrs):
        d=dict(attrs)
        if tag == "script" and d.get("src"): self.scripts.append(d["src"])
        if tag == "link" and d.get("href"): self.links.append(d["href"])

def fetch(url):
    req=Request(url, headers={"User-Agent":UA, "Accept":"text/html,application/javascript,text/javascript,*/*;q=0.1"}, method="GET")
    with urlopen(req, timeout=20) as r:
        data=r.read(MAX_BYTES+1)
        truncated=len(data)>MAX_BYTES
        data=data[:MAX_BYTES]
        return {
            "status": getattr(r, "status", 200),
            "content_type": r.headers.get("Content-Type"),
            "bytes_read": len(data),
            "truncated": truncated,
            "text": data.decode("utf-8", "replace")
        }

def same_origin(url):
    return urlparse(url).hostname in {"www.fastvolt.net","fastvolt.net"}

def literals(text):
    pats = [
        r'https?://[^"\'\s<>]+',
        r'(?<![A-Za-z0-9_])/(?:api|app|map|maps|station|stations|charging|charger|chargers|borne|bornes)[A-Za-z0-9_./?=&%:-]*'
    ]
    out=set()
    for p in pats:
        for m in re.findall(p, text, flags=re.I):
            s=m.rstrip("'),;]}")
            if len(s) <= 300: out.add(s)
    return sorted(out)

def graphql_static_hints(text):
    """Return only GraphQL-looking identifiers already present in public JS assets.
    No schema guessing, brute force, variables, values or raw source persistence.
    """
    operation_names=set(); root_field_hints=set(); associations=[]
    seen_assoc=set()
    pat=r'\b(query|subscription)\s+([A-Za-z_][A-Za-z0-9_]*)\s*(?:\([^{}]{0,500}\))?\s*\{'
    for m in re.finditer(pat, text):
        op=m.group(2); operation_names.add(op)
        tail=text[m.end():m.end()+1200]
        fm=re.search(r'\b([A-Za-z_][A-Za-z0-9_]*)\s*(?:\([^{}]{0,500}\))?\s*\{', tail)
        if fm and not fm.group(1).startswith('__'):
            root=fm.group(1); root_field_hints.add(root)
            key=(op,root)
            if key not in seen_assoc:
                associations.append({"operation":op,"root_field":root})
                seen_assoc.add(key)
    for m in re.finditer(r'\bquery\s*(?:\([^{}]{0,500}\))?\s*\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*(?:\([^{}]{0,500}\))?\s*\{', text):
        if not m.group(1).startswith('__'):
            root_field_hints.add(m.group(1))
    vocab=re.compile(r'(station|borne|charger|charging|location|map|point|connector|evse)', re.I)
    for m in re.finditer(r'\b([A-Za-z_][A-Za-z0-9_]{2,80})\b', text):
        token=m.group(1)
        if vocab.search(token):
            start=max(0,m.start()-180); end=min(len(text),m.end()+180)
            ctx=text[start:end].lower()
            if 'graphql' in ctx or 'gql' in ctx or 'query' in ctx or 'usequery' in ctx:
                root_field_hints.add(token)
    return sorted(operation_names), sorted(root_field_hints), sorted(associations,key=lambda x:(x['operation'],x['root_field']))

report={
  "schema_version":3,
  "generated_at":datetime.now(timezone.utc).isoformat(),
  "policy":{"read_only":True,"no_login":True,"no_mutations":True,"no_session_start":True,"same_origin_assets_only":True,"raw_bodies_persisted":False,"static_graphql_hints_only":True,"no_graphql_requests_from_this_probe":True},
  "page_url":BASE,
  "page":{},
  "same_origin_script_assets":[],
  "candidate_public_literals":[],
  "graphql_operation_names":[],
  "graphql_root_field_hints":[],
  "graphql_operation_root_associations":[],
  "errors":[]
}

try:
    page=fetch(BASE)
    report["page"]={k:v for k,v in page.items() if k!="text"}
    parser=P(); parser.feed(page["text"])
    scripts=[]
    for src in parser.scripts:
        u=urljoin(BASE,src)
        if same_origin(u) and u not in scripts: scripts.append(u)
    candidates=set(literals(page["text"]))
    op_names=set(); field_hints=set(); assoc_map=set()
    p_ops,p_fields,p_assoc=graphql_static_hints(page["text"])
    op_names.update(p_ops); field_hints.update(p_fields)
    for a in p_assoc: assoc_map.add((a['operation'],a['root_field']))
    for u in scripts[:MAX_ASSETS]:
        rec={"url":u}
        try:
            a=fetch(u)
            rec.update({k:v for k,v in a.items() if k!="text"})
            lits=literals(a["text"])
            rec["candidate_literal_count"]=len(lits)
            candidates.update(lits)
            ops,fields,assocs=graphql_static_hints(a["text"])
            rec["graphql_operation_name_count"]=len(ops)
            rec["graphql_root_field_hint_count"]=len(fields)
            if ops: rec["graphql_operation_names"]=ops[:50]
            if fields: rec["graphql_root_field_hints"]=fields[:100]
            if assocs: rec["graphql_operation_root_associations"]=assocs[:50]
            op_names.update(ops); field_hints.update(fields)
            for x in assocs: assoc_map.add((x['operation'],x['root_field']))
        except Exception as e:
            rec["error"]=type(e).__name__+": "+str(e)[:200]
        report["same_origin_script_assets"].append(rec)
    report["candidate_public_literals"]=sorted(candidates)
    report["graphql_operation_names"]=sorted(op_names)
    report["graphql_root_field_hints"]=sorted(field_hints)
    report["graphql_operation_root_associations"]=[{"operation":o,"root_field":r} for o,r in sorted(assoc_map)]
except Exception as e:
    report["errors"].append(type(e).__name__+": "+str(e)[:300])

json.dump(report, sys.stdout, ensure_ascii=False, indent=2)
print()
