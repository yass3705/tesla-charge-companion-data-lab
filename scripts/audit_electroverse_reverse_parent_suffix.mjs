import fs from 'node:fs/promises';
import zlib from 'node:zlib';

const CACHE='data/electroverse/tariff_cache', MAP='data/electroverse/irve_location_mapping.json', OVERLAY='data/platforms/electroverse/france-evse';
const norm=x=>String(x??'').trim().toUpperCase().replace(/[^A-Z0-9]/g,'');
const text=x=>String(x??'').trim();
const opOf=p=>{const m=String(p||'').match(/^FR([A-Z0-9]{1,6})E/);return m?m[1]:'UNKNOWN';};

const mapping=JSON.parse(await fs.readFile(MAP,'utf8'));
const manifest=JSON.parse(await fs.readFile(CACHE+'/manifest.json','utf8'));
const om=JSON.parse(await fs.readFile(OVERLAY+'/manifest.json','utf8'));
const byPk=new Map((mapping.mappings||[]).map(m=>[String(m.electroverseLocationPk),m]));
const globalOwners=new Map();
for(const m of mapping.mappings||[])for(const p of m.irvePdcIds||[]){const k=norm(p);const s=globalOwners.get(k)||new Set();s.add(m.irveStationId);globalOwners.set(k,s);}
const published=new Set();
for(const t of om.tiles||[]){const p=JSON.parse(zlib.gunzipSync(await fs.readFile(OVERLAY+'/'+t.file)).toString('utf8'));for(const o of p.emspOffers||[])for(const id of o.evseIds||[])published.add(norm(id));}

const byOp={}, samples=[];
for(const sh of manifest.shards||[]){
  const data=JSON.parse(await fs.readFile(CACHE+'/'+sh.file,'utf8'));
  for(const row of Object.values(data.stations||{})){
    const m=byPk.get(String(row.electroverseLocationPk));if(!m)continue;
    const local=[...new Set((m.irvePdcIds||row.irvePdcIds||[]).map(norm).filter(Boolean))];
    const unclaimed=local.filter(p=>!published.has(p));if(!unclaimed.length)continue;
    for(const e of row.tariff?.evses||[]){
      const raw=text(e?.physicalReference);if(!raw)continue;
      const k=norm(raw);if(local.includes(k)||published.has(k))continue;
      const candidates=[];
      for(const width of [1,2]){
        const hits=unclaimed.filter(p=>p.length>width && p.slice(0,-width).endsWith(k) && /^\d+$/.test(p.slice(-width)));
        if(hits.length)candidates.push({width,hits});
      }
      // Accept only one connector-suffix width, with one or more globally unique targets,
      // and no target shared by another source ref at this station.
      if(candidates.length!==1)continue;
      const {width,hits}=candidates[0];
      if(hits.some(p=>(globalOwners.get(p)?.size||0)!==1))continue;
      const opSet=new Set(hits.map(opOf));if(opSet.size!==1)continue;
      const op=[...opSet][0];
      const rec=byOp[op]||(byOp[op]={sourceRefs:0,targetPdcs:new Set(),locations:new Set(),groups:0,widths:{}});
      rec.sourceRefs++;rec.groups++;rec.locations.add(String(row.electroverseLocationPk));rec.widths[width]=(rec.widths[width]||0)+1;for(const p of hits)rec.targetPdcs.add(p);
      if(samples.length<100)samples.push({operator:op,locationPk:String(row.electroverseLocationPk),raw,k,width,hits});
    }
  }
}
const operators=Object.entries(byOp).map(([operator,r])=>({operator,sourceRefs:r.sourceRefs,targetPdcs:r.targetPdcs.size,locations:r.locations.size,groups:r.groups,widths:r.widths})).sort((a,b)=>b.targetPdcs-a.targetPdcs);
const out={generatedAt:new Date().toISOString(),operators,samples};
await fs.mkdir('reports',{recursive:true});await fs.writeFile('reports/electroverse-fr-reverse-parent-suffix-audit.json',JSON.stringify(out,null,2)+'\n');
console.log(JSON.stringify(out,null,2));
