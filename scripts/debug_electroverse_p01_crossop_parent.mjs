import fs from 'node:fs/promises';
import zlib from 'node:zlib';

const CACHE='data/electroverse/tariff_cache';
const MAP='data/electroverse/irve_location_mapping.json';
const OVERLAY='data/platforms/electroverse/france-evse';
const norm=x=>String(x??'').trim().toUpperCase().replace(/[^A-Z0-9]/g,'');
const body=x=>{
  const n=norm(x);
  const m=n.match(/^FR[A-Z0-9]{1,8}E(.+)$/);
  return m?m[1]:null;
};
const op=x=>{
  const s=String(x??'').trim(), star=s.split('*').filter(Boolean);
  if(star.length>=2&&/^FR$/i.test(star[0]))return star[1].toUpperCase();
  return '';
};

const mapping=JSON.parse(await fs.readFile(MAP,'utf8'));
const byPk=new Map((mapping.mappings||[]).map(m=>[String(m.electroverseLocationPk),m]));
const owners=new Map();
for(const m of mapping.mappings||[])for(const p of m.irvePdcIds||[]){
  const k=norm(p);if(!k)continue;const s=owners.get(k)||new Set();s.add(String(m.irveStationId??''));owners.set(k,s);
}
const oman=JSON.parse(await fs.readFile(OVERLAY+'/manifest.json','utf8'));
const publishedSource=new Set(),publishedTargets=new Set();
for(const t of oman.tiles||[]){
 const tile=JSON.parse(zlib.gunzipSync(await fs.readFile(OVERLAY+'/'+t.file)));
 for(const o of tile.emspOffers||[]){
   for(const pk of o?.metadata?.electroverseEvsePks||[])if(pk!=null)publishedSource.add(String(pk));
   if(o?.metadata?.electroverseEvsePk!=null)publishedSource.add(String(o.metadata.electroverseEvsePk));
   for(const id of o.evseIds||[])publishedTargets.add(norm(id));
 }
}
const cman=JSON.parse(await fs.readFile(CACHE+'/manifest.json','utf8'));
let residual=0,matched=0,ambiguous=0,none=0;
const byLocation=[];
for(const sh of cman.shards||[]){
 const d=JSON.parse(await fs.readFile(CACHE+'/'+sh.file,'utf8'));
 for(const row of Object.values(d.stations||{})){
  const es=(row?.tariff?.evses||[]).filter(e=>e?.pk!=null&&!publishedSource.has(String(e.pk))&&op(e.physicalReference)==='P01');
  if(!es.length)continue;
  const m=byPk.get(String(row.electroverseLocationPk));
  const local=[...new Set((m?.irvePdcIds||row.irvePdcIds||[]).map(norm).filter(Boolean))];
  const avail=local.filter(p=>!publishedTargets.has(p));
  const rows=[];
  for(const e of es){
    residual++;
    const sb=body(e.physicalReference);
    const candidates=[];
    for(const p of avail){
      const pb=body(p); if(!sb||!pb||!sb.startsWith(pb)||sb.length<=pb.length)continue;
      const suffix=sb.slice(pb.length);
      if(!/^\d{1,2}$/.test(suffix))continue;
      if((owners.get(p)?.size||0)!==1)continue;
      candidates.push({target:p,suffix});
    }
    if(candidates.length===1){matched++;rows.push({evsePk:e.pk,ref:e.physicalReference,...candidates[0],connectors:(e.connectors||[]).map(c=>({kw:c.kilowatts??null,standard:c.standard?.name??c.standard??null}))});}
    else if(candidates.length>1){ambiguous++;rows.push({evsePk:e.pk,ref:e.physicalReference,ambiguous:candidates});}
    else{none++;rows.push({evsePk:e.pk,ref:e.physicalReference,noMatch:true});}
  }
  byLocation.push({locationPk:String(row.electroverseLocationPk),station:m?.irveStationId??null,residual:es.length,available:avail.length,matched:rows.filter(x=>x.target).length,rows:rows.slice(0,80)});
 }
}
console.log(JSON.stringify({residual,matched,ambiguous,none,fullyMatchedLocations:byLocation.filter(x=>x.matched===x.residual).length,locations:byLocation.length,top:byLocation.sort((a,b)=>b.residual-a.residual).slice(0,30)},null,2));
