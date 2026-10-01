import fs from 'node:fs/promises';
import zlib from 'node:zlib';

const URL='https://static.data.gouv.fr/resources/bornes-de-recharge-irve-du-reseau-r3-groupe-dbt/20260107-173608/data.csv';
const CACHE='data/electroverse/tariff_cache';
const MAP='data/electroverse/irve_location_mapping.json';
const OVERLAY='data/platforms/electroverse/france-evse';
const OUT='reports/electroverse-r3m-official-technical.json';
const norm=x=>String(x??'').trim().toUpperCase().replace(/[^A-Z0-9]/g,'');

function parseCsv(s){
  const rows=[];let row=[],cell='',q=false;
  for(let i=0;i<s.length;i++){
    const ch=s[i];
    if(q){
      if(ch==='"'&&s[i+1]==='"'){cell+='"';i++;}
      else if(ch==='"')q=false;
      else cell+=ch;
    }else{
      if(ch==='"')q=true;
      else if(ch===','){row.push(cell);cell='';}
      else if(ch==='\n'){row.push(cell.replace(/\r$/,''));rows.push(row);row=[];cell='';}
      else cell+=ch;
    }
  }
  if(cell.length||row.length){row.push(cell.replace(/\r$/,''));rows.push(row);}
  const h=rows.shift()||[];
  return rows.filter(r=>r.some(Boolean)).map(r=>Object.fromEntries(h.map((k,i)=>[k,r[i]??''])));
}
const csv=await (await fetch(URL)).text();
const irve=parseCsv(csv);
const idKey=['id_pdc_itinerance','id_pdc_itinerance '].find(k=>irve[0]&&k in irve[0])||'id_pdc_itinerance';
const pwrKey=['puissance_nominale','puissance_nominale '].find(k=>irve[0]&&k in irve[0])||'puissance_nominale';
const type2Key=['prise_type_2','prise_type_2 '].find(k=>irve[0]&&k in irve[0])||'prise_type_2';
const ccsKey=['prise_type_combo_ccs','prise_type_combo_ccs '].find(k=>irve[0]&&k in irve[0])||'prise_type_combo_ccs';
const chaKey=['prise_type_chademo','prise_type_chademo '].find(k=>irve[0]&&k in irve[0])||'prise_type_chademo';
const bool=v=>/^(1|true|vrai|yes|oui)$/i.test(String(v??'').trim());
const kw=n=>{n=Number(String(n??'').replace(',','.'));return Number.isFinite(n)?Math.round(n):null;};
function techTarget(r){
  const k=kw(r[pwrKey]);
  if(k==null)return null;
  if(bool(r[ccsKey])||bool(r[chaKey]))return 'DC'+k;
  if(bool(r[type2Key]))return 'ACS'+k;
  return k<=43?'ACS'+k:'DC'+k;
}
const techByPdc=new Map();
for(const r of irve){
  const p=norm(r[idKey]);if(!p)continue;
  techByPdc.set(p,{tech:techTarget(r),row:r});
}

const mapping=JSON.parse(await fs.readFile(MAP,'utf8'));
const byPk=new Map((mapping.mappings||[]).map(m=>[String(m.electroverseLocationPk),m]));
const owners=new Map();
for(const m of mapping.mappings||[])for(const p of m.irvePdcIds||[]){
  const k=norm(p);if(!k)continue;const s=owners.get(k)||new Set();s.add(String(m.irveStationId??''));owners.set(k,s);
}
const oman=JSON.parse(await fs.readFile(OVERLAY+'/manifest.json','utf8'));
const publishedTargets=new Set(),publishedSources=new Set();
for(const t of oman.tiles||[]){
  const tile=JSON.parse(zlib.gunzipSync(await fs.readFile(OVERLAY+'/'+t.file)));
  for(const o of tile.emspOffers||[]){
    for(const p of o.evseIds||[])publishedTargets.add(norm(p));
    if(o?.metadata?.electroverseEvsePk!=null)publishedSources.add(String(o.metadata.electroverseEvsePk));
    for(const pk of o?.metadata?.electroverseEvsePks||[])if(pk!=null)publishedSources.add(String(pk));
  }
}
const cman=JSON.parse(await fs.readFile(CACHE+'/manifest.json','utf8'));
const result={generatedAt:new Date().toISOString(),officialRows:irve.length,officialR3PdcRows:[...techByPdc.keys()].filter(p=>p.startsWith('FRR3ME')).length,
  locations:0,missingTargets:0,sourceResidual:0,candidateLocations:0,candidateTargets:0,byTech:{},samples:[]};
for(const sh of cman.shards||[]){
  const data=JSON.parse(await fs.readFile(CACHE+'/'+sh.file,'utf8'));
  for(const row of Object.values(data.stations||{})){
    const m=byPk.get(String(row.electroverseLocationPk));if(!m)continue;
    const local=[...new Set((m.irvePdcIds||row.irvePdcIds||[]).map(norm).filter(Boolean))];
    const missing=local.filter(p=>p.startsWith('FRR3ME')&&!publishedTargets.has(p));
    if(!missing.length)continue;
    result.locations++;result.missingTargets+=missing.length;
    const es=(row.tariff?.evses||[]).filter(e=>e?.pk!=null&&!publishedSources.has(String(e.pk)));
    const src=[];
    for(const e of es){
      const raw=String(e.physicalReference??'').trim();
      let tech=null;
      let mm=raw.match(/\bACS(\d{2,3})\b/i);if(mm)tech='ACS'+Number(mm[1]);
      if(!tech){mm=raw.match(/\bDC(\d{2,3})\b/i);if(mm)tech='DC'+Number(mm[1]);}
      if(!tech){mm=raw.match(/\bMS(\d{2,3})\b/i);if(mm)tech='DC'+Number(mm[1]);}
      if(tech)src.push({e,raw,tech});
    }
    result.sourceResidual+=src.length;
    const targetByTech=new Map();
    for(const p of missing){
      const tech=techByPdc.get(p)?.tech||null;
      if(!tech)continue;const a=targetByTech.get(tech)||[];a.push(p);targetByTech.set(tech,a);
    }
    const srcByTech=new Map();
    for(const x of src){const a=srcByTech.get(x.tech)||[];a.push(x);srcByTech.set(x.tech,a);}
    const safe=[];
    for(const [tech,xs] of srcByTech){
      const ps=targetByTech.get(tech)||[];
      if(!ps.length||xs.length!==ps.length)continue;
      if(ps.some(p=>(owners.get(p)?.size||0)!==1))continue;
      const pricingSigs=new Set(xs.map(x=>JSON.stringify((x.e.connectors||[]).map(c=>({
        free:c?.isChargingFree??null,pc:c?.priceComponents??null,cp:c?.complexPricingDetail??null
      })))));
      const connectorCounts=new Set(xs.map(x=>(x.e.connectors||[]).length));
      if(pricingSigs.size!==1)continue;
      safe.push({tech,sourceCount:xs.length,targetCount:ps.length,uniformConnectorCount:connectorCounts.size===1,
        sourceEvsePks:xs.map(x=>x.e.pk),refs:xs.map(x=>x.raw),targetPdcs:ps});
      result.byTech[tech]=(result.byTech[tech]||0)+ps.length;
    }
    if(safe.length){
      result.candidateLocations++;
      result.candidateTargets+=safe.reduce((n,g)=>n+g.targetCount,0);
      if(result.samples.length<50)result.samples.push({locationPk:String(row.electroverseLocationPk),irveStationId:m.irveStationId??null,safe});
    }
  }
}
await fs.mkdir('reports',{recursive:true});
await fs.writeFile(OUT,JSON.stringify(result,null,2)+'\n');
console.log(JSON.stringify(result,null,2));
