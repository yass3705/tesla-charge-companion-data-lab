import fs from 'node:fs/promises';
import zlib from 'node:zlib';
import { execFileSync } from 'node:child_process';

const URL='https://www.data.gouv.fr/api/1/datasets/r/1bf98bac-94a9-4909-8726-47a203038a40';
const CSV='/tmp/powerdot.csv';
execFileSync('curl',['-L','--fail','--silent','--show-error',URL,'-o',CSV],{stdio:'inherit'});
const raw=await fs.readFile(CSV,'utf8');

function parseCsv(s){
  const rows=[];let row=[],field='',q=false;
  for(let i=0;i<s.length;i++){
    const ch=s[i];
    if(q){
      if(ch==='"'&&s[i+1]==='"'){field+='"';i++;}
      else if(ch==='"')q=false;
      else field+=ch;
    }else{
      if(ch==='"')q=true;
      else if(ch===','){row.push(field);field='';}
      else if(ch==='\n'){row.push(field.replace(/\r$/,''));rows.push(row);row=[];field='';}
      else field+=ch;
    }
  }
  if(field||row.length){row.push(field);rows.push(row);}
  return rows;
}
const rows=parseCsv(raw), headers=rows[0]||[];
const objs=rows.slice(1).filter(r=>r.some(Boolean)).map(r=>Object.fromEntries(headers.map((h,i)=>[h,r[i]??''])));

const CACHE='data/electroverse/tariff_cache';
const manifest=JSON.parse(await fs.readFile(CACHE+'/manifest.json','utf8'));
const mapping=JSON.parse(await fs.readFile('data/electroverse/irve_location_mapping.json','utf8'));
const OVERLAY='data/platforms/electroverse/france-evse';
const overlayManifest=JSON.parse(await fs.readFile(OVERLAY+'/manifest.json','utf8'));
const norm=x=>String(x??'').trim().toUpperCase().replace(/[^A-Z0-9]/g,'');
const kwClass=n=>{
  n=Number(n); if(!Number.isFinite(n))return null;
  const buckets=[3.7,7.4,11,22,43,50,60,75,100,120,150,160,180,200,240,300,320,360,400];
  let best=null,delta=Infinity;
  for(const b of buckets){const d=Math.abs(n-b);if(d<delta){best=b;delta=d;}}
  return delta<=Math.max(1,best*0.03)?best:Math.round(n*10)/10;
};
const bool=v=>String(v).toLowerCase()==='true';
const techKeyFromOfficial=o=>{
  const kw=kwClass(o.puissance_nominale); if(kw==null)return null;
  const plugs=[
    bool(o.prise_type_ef)?'EF':null,
    bool(o.prise_type_2)?'T2':null,
    bool(o.prise_type_combo_ccs)?'CCS':null,
    bool(o.prise_type_chademo)?'CHA':null,
    bool(o.prise_type_autre)?'OTHER':null
  ].filter(Boolean).sort();
  return JSON.stringify({kw,plugs});
};
const techKeyFromEvse=e=>{
  const cs=e?.connectors||[];if(!cs.length)return null;
  const kw=kwClass(Math.max(...cs.map(c=>Number(c.kilowatts)||0))); if(kw==null)return null;
  const plugs=[...new Set(cs.map(c=>{
    const n=String(c?.standard?.name||'');
    if(n==='IEC_62196_T2')return 'T2';
    if(n==='IEC_62196_T2_COMBO')return 'CCS';
    if(n==='CHADEMO')return 'CHA';
    if(n==='DOMESTIC_E')return 'EF';
    return n||'OTHER';
  }))].sort();
  return JSON.stringify({kw,plugs});
};
const priceSig=e=>JSON.stringify((e?.connectors||[]).map(c=>({
  isChargingFree:c?.isChargingFree??null,
  priceComponents:c?.priceComponents??null,
  complexPricingDetail:c?.complexPricingDetail??null
})));

const officialByPdc=new Map(objs.map(o=>[norm(o.id_pdc_itinerance),o]).filter(([k])=>k));
const byPk=new Map((mapping.mappings||[]).map(m=>[String(m.electroverseLocationPk),m]));
const globalPdcOwners=new Map();
for(const m of mapping.mappings||[])for(const p of m.irvePdcIds||[]){
  const k=norm(p); if(!k)continue;
  const s=globalPdcOwners.get(k)||new Set();s.add(m.irveStationId);globalPdcOwners.set(k,s);
}
const published=new Set();
for(const t of overlayManifest.tiles||[]){
  const gz=await fs.readFile(OVERLAY+'/'+t.file);
  const p=JSON.parse(zlib.gunzipSync(gz).toString('utf8'));
  for(const o of p.emspOffers||[])for(const id of o.evseIds||[])published.add(norm(id));
}

const out={generatedAt:new Date().toISOString(),officialRows:objs.length,locations:0,candidateLocations:0,candidateTargets:0,
 byTech:{},rejects:{},samples:[]};
const rej=k=>out.rejects[k]=(out.rejects[k]||0)+1;

for(const sh of manifest.shards||[]){
  const data=JSON.parse(await fs.readFile(CACHE+'/'+sh.file,'utf8'));
  for(const row of Object.values(data.stations||{})){
    const m=byPk.get(String(row.electroverseLocationPk));if(!m)continue;
    const local=[...new Set((m.irvePdcIds||row.irvePdcIds||[]).map(norm).filter(Boolean))];
    const missing=local.filter(p=>p.startsWith('FRPD1E')&&!published.has(p));
    if(!missing.length)continue;
    out.locations++;

    const targetsByTech=new Map();let targetBad=false;
    for(const p of missing){
      const o=officialByPdc.get(p);if(!o){targetBad=true;break;}
      const key=techKeyFromOfficial(o);
      if(!key||(globalPdcOwners.get(p)?.size||0)!==1){targetBad=true;break;}
      const arr=targetsByTech.get(key)||[];arr.push(p);targetsByTech.set(key,arr);
    }
    if(targetBad){rej('missing_official_technical_row_or_nonunique_target');continue;}

    const srcByTech=new Map();
    for(const e of row.tariff?.evses||[]){
      const rawRef=String(e?.physicalReference??'').trim();if(!rawRef)continue;
      const k0=norm(rawRef);
      if(local.includes(k0)||published.has(k0))continue;
      const key=techKeyFromEvse(e);if(!key)continue;
      const arr=srcByTech.get(key)||[];arr.push({e,rawRef,sig:priceSig(e)});srcByTech.set(key,arr);
    }

    const groups=[];
    for(const [key,targets] of targetsByTech){
      const src=srcByTech.get(key)||[];
      if(!src.length||src.length!==targets.length)continue;
      const sigs=new Set(src.map(x=>x.sig));
      if(sigs.size!==1)continue;
      groups.push({tech:JSON.parse(key),targets,refs:src.map(x=>x.rawRef)});
    }
    if(!groups.length){rej('no_exact_homogeneous_technical_group');continue;}
    const n=groups.reduce((s,g)=>s+g.targets.length,0);
    out.candidateLocations++;out.candidateTargets+=n;
    for(const g of groups){
      const k=JSON.stringify(g.tech);out.byTech[k]=(out.byTech[k]||0)+g.targets.length;
    }
    if(out.samples.length<30)out.samples.push({locationPk:String(row.electroverseLocationPk),groups});
  }
}
await fs.mkdir('reports',{recursive:true});
await fs.writeFile('reports/electroverse-fr-pd1-powerdot-technical-group-audit.json',JSON.stringify(out,null,2)+'\n');
console.log(JSON.stringify(out,null,2));
