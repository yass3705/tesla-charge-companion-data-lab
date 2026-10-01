import fs from 'node:fs/promises';
import zlib from 'node:zlib';

const CACHE='data/electroverse/tariff_cache';
const MANIFEST=CACHE+'/manifest.json';
const MAP='data/electroverse/irve_location_mapping.json';
const OVERLAY='data/platforms/electroverse/france-evse';
const OUT='reports/electroverse-fr-pd1-duplicate-ordinal-residual.json';
const norm=x=>String(x??'').trim().toUpperCase().replace(/[^A-Z0-9]/g,'');
const txt=x=>String(x??'').trim();

const mapping=JSON.parse(await fs.readFile(MAP,'utf8'));
const manifest=JSON.parse(await fs.readFile(MANIFEST,'utf8'));
const overlayManifest=JSON.parse(await fs.readFile(OVERLAY+'/manifest.json','utf8'));
const byPk=new Map((mapping.mappings||[]).map(m=>[String(m.electroverseLocationPk),m]));
const globalPdcOwners=new Map();
for(const m of mapping.mappings||[])for(const p of m.irvePdcIds||[]){
  const k=norm(p);if(!k)continue;
  const s=globalPdcOwners.get(k)||new Set();s.add(m.irveStationId);globalPdcOwners.set(k,s);
}
const published=new Set();
for(const t of overlayManifest.tiles||[]){
  const gz=await fs.readFile(OVERLAY+'/'+t.file);
  const p=JSON.parse(zlib.gunzipSync(gz).toString('utf8'));
  for(const o of p.emspOffers||[])for(const id of o.evseIds||[])published.add(norm(id));
}

const out={generatedAt:new Date().toISOString(),locations:0,candidateLocations:0,candidateTargets:0,candidateSourceEntries:0,duplicateSourceEntries:0,samples:[]};

for(const sh of manifest.shards||[]){
  const data=JSON.parse(await fs.readFile(CACHE+'/'+sh.file,'utf8'));
  for(const row of Object.values(data.stations||{})){
    const m=byPk.get(String(row.electroverseLocationPk));if(!m)continue;
    const local=[...new Set((m.irvePdcIds||row.irvePdcIds||[]).map(norm).filter(Boolean))];
    const missing=local.filter(p=>p.startsWith('FRPD1E')&&!published.has(p));
    if(!missing.length)continue;
    out.locations++;

    const unresolved=[];
    for(const e of row.tariff?.evses||[]){
      const raw=txt(e?.physicalReference);if(!raw)continue;
      const k=norm(raw);
      if(local.includes(k)||published.has(k))continue;
      const mm=raw.match(/^(.*?)[\s_\-\/]*([0-9]{1,2})$/);
      if(!mm||!mm[1])continue;
      unresolved.push({e,raw,stem:norm(mm[1]),ord:Number(mm[2])});
    }
    const byStem=new Map();
    for(const x of unresolved){
      const arr=byStem.get(x.stem)||[];arr.push(x);byStem.set(x.stem,arr);
    }

    const targetGroups=[];
    for(const width of [1,2]){
      const byPrefix=new Map();
      for(const p of missing){
        if(p.length<=width)continue;
        const tail=p.slice(-width);if(!/^\d+$/.test(tail))continue;
        const prefix=p.slice(0,-width),ord=Number(tail);
        const arr=byPrefix.get(prefix)||[];arr.push({p,ord,width});byPrefix.set(prefix,arr);
      }
      for(const [prefix,rows] of byPrefix){
        if(rows.some(r=>(globalPdcOwners.get(r.p)?.size||0)!==1))continue;
        if(new Set(rows.map(r=>r.ord)).size!==rows.length)continue;
        targetGroups.push({prefix,rows,width,ordSet:[...new Set(rows.map(r=>r.ord))].sort((a,b)=>a-b)});
      }
    }

    const candidates=[];
    for(const [stem,items] of byStem){
      const ords=[...new Set(items.map(x=>x.ord))].sort((a,b)=>a-b);
      if(!ords.length)continue;
      const duplicateCount=items.length-ords.length;
      if(duplicateCount<=0)continue;
      const matches=targetGroups.filter(g=>g.rows.length===ords.length&&g.ordSet.every((v,i)=>v===ords[i]));
      if(matches.length!==1)continue;
      candidates.push({stem,items,ords,duplicateCount,target:matches[0]});
    }

    const targetUse=new Map();
    for(const c of candidates)targetUse.set(c.target.prefix,(targetUse.get(c.target.prefix)||0)+1);
    const unique=candidates.filter(c=>(targetUse.get(c.target.prefix)||0)===1);
    if(!unique.length)continue;
    const targets=unique.reduce((n,c)=>n+c.target.rows.length,0);
    out.candidateLocations++;
    out.candidateTargets+=targets;
    out.candidateSourceEntries+=unique.reduce((n,c)=>n+c.items.length,0);
    out.duplicateSourceEntries+=unique.reduce((n,c)=>n+c.duplicateCount,0);
    if(out.samples.length<30)out.samples.push({
      locationPk:String(row.electroverseLocationPk),
      groups:unique.map(c=>({
        stem:c.stem,
        refs:c.items.map(x=>x.raw),
        ords:c.ords,
        duplicateCount:c.duplicateCount,
        targetPdcs:c.target.rows.map(r=>r.p)
      }))
    });
  }
}
await fs.mkdir('reports',{recursive:true});
await fs.writeFile(OUT,JSON.stringify(out,null,2)+'\n');
console.log(JSON.stringify(out,null,2));
