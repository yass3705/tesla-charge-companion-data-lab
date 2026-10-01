import fs from 'node:fs/promises';
import zlib from 'node:zlib';

const CACHE='data/electroverse/tariff_cache';
const MAP='data/electroverse/irve_location_mapping.json';
const OVERLAY='data/platforms/electroverse/france-evse';
const POWERDOT='data/operator_direct/powerdot_evse_technical_inventory.json';
const norm=x=>String(x??'').trim().toUpperCase().replace(/[^A-Z0-9]/g,'');
const text=x=>String(x??'').trim();
const kwClass=n=>{n=Number(n);if(!Number.isFinite(n))return null;const bs=[3.7,7.4,11,22,24,40,43,50,60,75,100,120,150,160,180,200,240,300,320,360,400];let b=null,d=Infinity;for(const x of bs){const z=Math.abs(n-x);if(z<d){b=x;d=z;}}return d<=Math.max(1,b*.03)?b:Math.round(n*10)/10;};
const plug=s=>{const n=String(s?.name||'');if(n==='IEC_62196_T2')return'T2';if(n==='IEC_62196_T2_COMBO')return'CCS';if(n==='CHADEMO')return'CHA';if(n==='DOMESTIC_E')return'EF';return n||'OTHER';};
const eKey=e=>{const cs=e?.connectors||[];if(!cs.length)return null;return JSON.stringify({kw:kwClass(Math.max(...cs.map(c=>Number(c.kilowatts)||0))),plugs:[...new Set(cs.map(c=>plug(c.standard)))].sort()});};
const nKey=x=>{const kw=kwClass(x?.powerKw);if(kw==null)return null;return JSON.stringify({kw,plugs:[...new Set((x?.plugs||[]).map(String).filter(Boolean))].sort()});};
const psig=e=>JSON.stringify((e.connectors||[]).map(c=>({f:c?.isChargingFree??null,p:c?.priceComponents??null,x:c?.complexPricingDetail??null})));

const mapping=JSON.parse(await fs.readFile(MAP,'utf8'));
const byPk=new Map((mapping.mappings||[]).map(m=>[String(m.electroverseLocationPk),m]));
const power=JSON.parse(await fs.readFile(POWERDOT,'utf8'));
const pByEvse=new Map((power.evses||[]).map(x=>[norm(x.evseId),x]));
const oman=JSON.parse(await fs.readFile(OVERLAY+'/manifest.json','utf8'));
const pubTargets=new Set(),pubPks=new Set();
for(const t of oman.tiles||[]){const tile=JSON.parse(zlib.gunzipSync(await fs.readFile(OVERLAY+'/'+t.file)));for(const o of tile.emspOffers||[]){for(const id of o.evseIds||[])pubTargets.add(norm(id));for(const pk of o?.metadata?.electroverseEvsePks||[])if(pk!=null)pubPks.add(String(pk));if(o?.metadata?.electroverseEvsePk!=null)pubPks.add(String(o.metadata.electroverseEvsePk));}}
const cman=JSON.parse(await fs.readFile(CACHE+'/manifest.json','utf8'));
const pd1={locations:0,missingTargets:0,candidateTargets:0,candidateLocations:0,byKey:{},samples:[]};
const via={locations:0,missingTargets:0,residualSources:0,patterns:{},samples:[]};
for(const sh of cman.shards||[]){const data=JSON.parse(await fs.readFile(CACHE+'/'+sh.file,'utf8'));for(const row of Object.values(data.stations||{})){const m=byPk.get(String(row.electroverseLocationPk));if(!m)continue;const local=[...new Set((m.irvePdcIds||row.irvePdcIds||[]).map(norm).filter(Boolean))];
  const missPd1=local.filter(p=>p.startsWith('FRPD1E')&&!pubTargets.has(p));
  if(missPd1.length){pd1.locations++;pd1.missingTargets+=missPd1.length;const src=(row.tariff?.evses||[]).filter(e=>e?.pk!=null&&!pubPks.has(String(e.pk)));const sBy=new Map(),tBy=new Map();
    for(const e of src){const k=eKey(e);if(!k)continue;const a=sBy.get(k)||[];a.push(e);sBy.set(k,a);}
    for(const p of missPd1){const k=nKey(pByEvse.get(p));if(!k)continue;const a=tBy.get(k)||[];a.push(p);tBy.set(k,a);}
    let loc=0;const gs=[];
    for(const [k,ts] of tBy){const es=sBy.get(k)||[];if(!es.length||es.length!==ts.length)continue;const sigs=new Set(es.map(psig));if(sigs.size!==1)continue;loc+=ts.length;pd1.byKey[k]=(pd1.byKey[k]||0)+ts.length;gs.push({key:k,targets:ts,sourcePks:es.map(e=>e.pk)});}
    if(loc){pd1.candidateLocations++;pd1.candidateTargets+=loc;if(pd1.samples.length<15)pd1.samples.push({locationPk:String(row.electroverseLocationPk),groups:gs});}
  }
  const missVia=local.filter(p=>p.startsWith('FRVIAE')&&!pubTargets.has(p));
  if(missVia.length){via.locations++;via.missingTargets+=missVia.length;const src=(row.tariff?.evses||[]).filter(e=>e?.pk!=null&&!pubPks.has(String(e.pk)));via.residualSources+=src.length;
    const pats={};
    for(const e of src){const r=text(e.physicalReference);const key=/^\d{5,8}-\d{2}$/.test(r)?'stem-2digit':/^\d{5,8}-\d{2}-\d$/.test(r)?'stem-2digit-connector':/^FR\*VIA\*/i.test(r)?'ocpi-like':/^MAT[-_]?/i.test(r)?'mat':'other';pats[key]=(pats[key]||0)+1;via.patterns[key]=(via.patterns[key]||0)+1;}
    if(via.samples.length<20)via.samples.push({locationPk:String(row.electroverseLocationPk),missing:missVia.slice(0,20),refs:src.slice(0,30).map(e=>text(e.physicalReference)),patterns:pats});
  }
}}
const out={generatedAt:new Date().toISOString(),pd1,via};
await fs.mkdir('reports/electroverse',{recursive:true});
await fs.writeFile('reports/electroverse/pd1-via-current-gap.json',JSON.stringify(out,null,2)+'\n');
console.log(JSON.stringify(out,null,2));
