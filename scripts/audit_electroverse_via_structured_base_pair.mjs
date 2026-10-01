import fs from 'node:fs/promises';
import zlib from 'node:zlib';

const CACHE='data/electroverse/tariff_cache';
const MANIFEST=CACHE+'/manifest.json';
const MAP='data/electroverse/irve_location_mapping.json';
const OVERLAY='data/platforms/electroverse/france-evse';
const OUT='reports/electroverse-fr-via-structured-base-pair.json';
const norm=x=>String(x??'').trim().toUpperCase().replace(/[^A-Z0-9]/g,'');
const txt=x=>String(x??'').trim();

const mapping=JSON.parse(await fs.readFile(MAP,'utf8'));
const manifest=JSON.parse(await fs.readFile(MANIFEST,'utf8'));
const overlayManifest=JSON.parse(await fs.readFile(OVERLAY+'/manifest.json','utf8'));
const byPk=new Map((mapping.mappings||[]).map(m=>[String(m.electroverseLocationPk),m]));
const globalPdcOwners=new Map();
for(const m of mapping.mappings||[])for(const p of m.irvePdcIds||[]){
  const k=norm(p); if(!k)continue;
  const s=globalPdcOwners.get(k)||new Set(); s.add(m.irveStationId); globalPdcOwners.set(k,s);
}
const published=new Set();
for(const t of overlayManifest.tiles||[]){
  const gz=await fs.readFile(OVERLAY+'/'+t.file);
  const p=JSON.parse(zlib.gunzipSync(gz).toString('utf8'));
  for(const o of p.emspOffers||[])for(const id of o.evseIds||[])published.add(norm(id));
}
const out={generatedAt:new Date().toISOString(),locations:0,candidateLocations:0,candidateSources:0,candidateTargets:0,samples:[]};

for(const sh of manifest.shards||[]){
  const data=JSON.parse(await fs.readFile(CACHE+'/'+sh.file,'utf8'));
  for(const row of Object.values(data.stations||{})){
    const m=byPk.get(String(row.electroverseLocationPk));if(!m)continue;
    const local=[...new Set((m.irvePdcIds||row.irvePdcIds||[]).map(norm).filter(Boolean))];
    const missing=local.filter(p=>p.startsWith('FRVIAE')&&!published.has(p));
    if(!missing.length)continue;
    out.locations++;

    const refs=[];
    for(const e of row.tariff?.evses||[]){
      const raw=txt(e?.physicalReference);if(!raw)continue;
      const k=norm(raw);
      if(local.includes(k)||published.has(k))continue;
      const mm=raw.match(/^(\d{5,8})-(\d{2})$/);
      if(!mm)continue;
      refs.push({e,raw,stem:mm[1],n:Number(mm[2])});
    }
    if(!refs.length)continue;

    const byStem=new Map();
    for(const x of refs){const a=byStem.get(x.stem)||[];a.push(x);byStem.set(x.stem,a);}
    const candidates=[];
    for(const [stem,items] of byStem){
      if(new Set(items.map(x=>x.n)).size!==items.length)continue;
      const targets=[];
      for(const x of items){
        const g=Math.ceil(x.n/2),c=((x.n-1)%2)+1;
        const suffix=String(g).padStart(2,'0')+String(c);
        const expectedBase='FRVIAE20'+stem;
        const hits=missing.filter(p=>p.startsWith(expectedBase)&&p.endsWith(suffix));
        if(hits.length!==1)continue;
        const target=hits[0];
        if((globalPdcOwners.get(target)?.size||0)!==1)continue;
        targets.push({source:x,target,g,c});
      }
      if(targets.length!==items.length)continue;
      if(new Set(targets.map(x=>x.target)).size!==targets.length)continue;

      // Reject sites where the same base exposes connector ordinals other than 1/2,
      // because the flat 2-per-group transform would no longer be structurally proven.
      const sameBase=missing.filter(p=>p.startsWith('FRVIAE20'+stem));
      const bad=sameBase.some(p=>{
        const m=p.match(/(\d{2})(\d)$/); if(!m)return true;
        const c=Number(m[2]); return c!==1&&c!==2;
      });
      if(bad)continue;

      candidates.push({stem,targets});
    }
    if(!candidates.length)continue;
    const n=candidates.reduce((s,c)=>s+c.targets.length,0);
    out.candidateLocations++;
    out.candidateSources+=n;
    out.candidateTargets+=n;
    if(out.samples.length<30)out.samples.push({
      locationPk:String(row.electroverseLocationPk),
      candidates:candidates.map(c=>({
        stem:c.stem,
        mappings:c.targets.map(x=>({ref:x.source.raw,target:x.target}))
      }))
    });
  }
}
await fs.mkdir('reports',{recursive:true});
await fs.writeFile(OUT,JSON.stringify(out,null,2)+'\n');
console.log(JSON.stringify(out,null,2));
