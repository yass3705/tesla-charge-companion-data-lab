#!/usr/bin/env python3
import json,re,urllib.request,html
from pathlib import Path
from datetime import datetime,timezone

UA="TeslaChargeCompanion/9 fixed-tariff-refresh"
ROOT=Path(".")
HIST=ROOT/"data"/"tariff_history"
REPORT=ROOT/"reports"/"fixed-tariff-refresh-spain-latest.json"
HIST.mkdir(parents=True,exist_ok=True)
REPORT.parent.mkdir(parents=True,exist_ok=True)

def fetch(url):
    req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"text/html,*/*"})
    with urllib.request.urlopen(req,timeout=30) as r:
        raw=r.read().decode("utf-8","ignore")
    txt=re.sub(r"<script[^>]*>.*?</script>"," ",raw,flags=re.I|re.S)
    txt=re.sub(r"<style[^>]*>.*?</style>"," ",txt,flags=re.I|re.S)
    txt=re.sub(r"<[^>]+>"," ",txt)
    txt=html.unescape(txt).replace("\xa0"," ")
    txt=re.sub(r"\s+"," ",txt)
    return txt

def num(s):
    return float(s.replace(",", "."))

def find_one(text,patterns,label):
    vals=[]
    for p in patterns:
        for m in re.finditer(p,text,re.I|re.S):
            try: vals.append(num(m.group(1)))
            except: pass
    vals=sorted(set(round(x,4) for x in vals))
    if len(vals)!=1:
        raise ValueError(f"{label}: expected one value, got {vals}")
    return vals[0]

def sanity(v,lo=0.05,hi=2.0):
    if not (lo <= v <= hi): raise ValueError(f"value out of range: {v}")
    return v

configs=[
  {
    "name":"Repsol","path":"data/operator_direct/repsol_official_spain.json",
    "url":"https://www.repsol.es/particulares/vehiculos/movilidad-electrica/pago-por-recarga/",
    "extract":lambda t:{
      "motorcyclesEurPerKwh":sanity(find_one(t,[r"Motos\s*[:\-]?\s*([0-9]+[,.][0-9]+)\s*€/kWh"],"repsol motorcycles")),
      "normalCarChargeEurPerKwh":sanity(find_one(t,[r"coches?\s+normal\s*[:\-]?\s*([0-9]+[,.][0-9]+)\s*€/kWh",r"Recarga\s+normal\s*[:\-]?\s*([0-9]+[,.][0-9]+)\s*€/kWh"],"repsol normal")),
      "ultraFastCarChargeEurPerKwh":sanity(find_one(t,[r"ultrarr[aá]pida\s*[:\-]?\s*([0-9]+[,.][0-9]+)\s*€/kWh"],"repsol ultra"))
    },
    "apply":lambda d,v:d["publicTariffs"].update(v)
  },
  {
    "name":"Eranovum","path":"data/operator_direct/eranovum_official_spain.json",
    "url":"https://eranovum.energy/es/nuestras-tarifas/",
    "extract":lambda t:{
      "upTo22KwEurPerKwh":sanity(find_one(t,[r"Hasta\s*22\s*kW\s*([0-9]+[,.][0-9]+)\s*€"],"eranovum 22")),
      "30KwEurPerKwh":sanity(find_one(t,[r"30\s*kW\s*([0-9]+[,.][0-9]+)\s*€"],"eranovum 30")),
      "60KwEurPerKwh":sanity(find_one(t,[r"60\s*kW\s*([0-9]+[,.][0-9]+)\s*€"],"eranovum 60")),
      "120KwEurPerKwh":sanity(find_one(t,[r"120\s*kW\s*([0-9]+[,.][0-9]+)\s*€"],"eranovum 120")),
      "from150KwEurPerKwh":sanity(find_one(t,[r"partir\s+de\s+150\s*kW\s*([0-9]+[,.][0-9]+)\s*€"],"eranovum 150"))
    },
    "apply":lambda d,v:d["publicTariffs"].update(v)
  },
  {
    "name":"Wenea","path":"data/operator_direct/wenea_official_spain.json",
    "url":"https://wenea.com/tarifas-de-carga/",
    "extract":lambda t:{
      "ac7_4To22KwEurPerKwh":sanity(find_one(t,[r"AC\s*[·\-]?\s*7[,.]4\s*kW\s*[–-]\s*22\s*kW.*?([0-9]+[,.][0-9]+)\s*€/kWh"],"wenea ac")),
      "dc50To150KwEurPerKwh":sanity(find_one(t,[r"DC\s*[·\-]?\s*50\s*kW\s*[–-]\s*150\s*kW.*?([0-9]+[,.][0-9]+)\s*€/kWh"],"wenea dc")),
      "hpc151To400KwEurPerKwh":sanity(find_one(t,[r"HPC\s*[·\-]?\s*151\s*kW\s*[–-]\s*400\s*kW.*?([0-9]+[,.][0-9]+)\s*€/kWh"],"wenea hpc"))
    },
    "apply":lambda d,v:d["publicTariffs"].update(v)
  },
  {
    "name":"Zunder","path":"data/operator_direct/zunder_official_spain.json",
    "url":"https://www.zunder.com/usuario-ve/",
    "extract":lambda t:{
      "standardAcUpTo50KwEurPerKwh":sanity(find_one(t,[r"Carga\s+AC\s*[·\-]?\s*hasta\s*50\s*kW\s*([0-9]+[,.][0-9]+)\s*€/kWh"],"zunder ac")),
      "standardFastOver50KwEurPerKwh":sanity(find_one(t,[r"Carga\s+r[aá]pida\s*[·\-]?\s*m[aá]s\s+de\s+50\s*kW\s*([0-9]+[,.][0-9]+)\s*€/kWh"],"zunder fast"))
    },
    "apply":lambda d,v:d["publicTariffs"].update(v)
  },
  {
    "name":"ACCIONA","path":"data/operator_direct/acciona_official_spain.json",
    "url":"https://recarga.acciona.com/es",
    "extract":lambda t:{
      "upTo22KwEurPerKwh":sanity(find_one(t,[r"hasta\s*22\s*kW.*?([0-9]+[,.][0-9]+)\s*€/kWh"],"acciona <=22")),
      "over22KwEurPerKwh":sanity(find_one(t,[r"m[aá]s\s+de\s+22\s*kW.*?([0-9]+[,.][0-9]+)\s*€/kWh"],"acciona >22"))
    },
    "apply":lambda d,v:d["publicTariffs"].update(v)
  }
]

now=datetime.now(timezone.utc).isoformat()
results=[]
for cfg in configs:
    p=ROOT/cfg["path"]
    data=json.loads(p.read_text())
    before=json.loads(json.dumps(data))
    try:
        text=fetch(cfg["url"])
        vals=cfg["extract"](text)
        cfg["apply"](data,vals)
        changed=(data!=before)
        data["verifiedAt"]=now
        data["refresh"]={
            "mode":"automatic_official_page_parser",
            "source":cfg["url"],
            "refreshedAt":now,
            "lastResult":"changed" if changed else "unchanged"
        }
        if changed:
            hist=HIST/(p.stem+".jsonl")
            with hist.open("a",encoding="utf-8") as h:
                h.write(json.dumps({"archivedAt":now,"previous":before},ensure_ascii=False)+"\n")
        p.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n")
        results.append({"operator":cfg["name"],"path":cfg["path"],"status":"changed" if changed else "unchanged","values":vals})
    except Exception as e:
        results.append({"operator":cfg["name"],"path":cfg["path"],"status":"failed_keep_last_valid","error":str(e)})

REPORT.write_text(json.dumps({"generatedAt":now,"results":results},ensure_ascii=False,indent=2)+"\n")
print(json.dumps({"generatedAt":now,"results":results},ensure_ascii=False,indent=2))
if any(r["status"]=="failed_keep_last_valid" for r in results):
    raise SystemExit(2)
