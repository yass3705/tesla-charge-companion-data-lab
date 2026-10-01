import fs from 'node:fs/promises';
import zlib from 'node:zlib';

const OPS=new Set(['55C','HPC','EVC']);
const CACHE='data/electroverse/tariff_cache';
const MANIFEST=CACHE+'/manifest.json';
const MAP='data/electroverse/irve_location_mapping.json';
const OVERLAY='data/platforms/electroverse/france-evse';

const norm=x=>String(x??'').trim().toUpperCase().replace(/[^A-Z0-9]/g,'');
const txt=x=>String(x??'').trim();
const opOf=p=>{const m=String(p||'').match(/^FR([A-Z0-9]{1,6})E/);return m?m[1]:'UNKNOWN';};
const top=o=>Object.entries(o).sort((a,b)=>b[1]-a[1]||a[0].localeCompare(b[0])).map(([key,count])=>({key,count}));

const mapping=JSON.parse(await fs.readFile(MAP,'utf8'));
const manifest=JSON.parse(await fs.readFile(MANIFEST,'utf8'));
const overlayManifest=JSON.parse(await fs.readFile(OVERLAY+'/manifest.json','utf8'));
const byPk=new Map((mapping.mappings||[]).map(m=>[String(m.electroverseLocationPk),m]));
const published=new Set();
for(const t of overlayManifest.tiles||[]){
  const gz=await fs.readFile(OVERLAY+'/'+t.file);
  const p=JSON.parse(zlib.gunzipSync(gz).toString('utf8'));
  for(const o of p.emspOffers||[])for(const id of o.evseIds||[])published.add(norm(id));
}
const reports={};
for(const op of OPS)reports[op]={generatedAt:new Date().toISOString(),operator:op,samples:[],shape:{},refLength:{},localPdcCount:{},uniqueMissingSuffixHitByLength:{},ordinalStemCounts:{},unresolvedToMissingSetCardinality:{},locations:0,unresolvedRefs:0,missingPdcs:new Set()};

for(const sh of manifest.shards||[]){
  const data=JSON.parse(await fs.readFile(CACHE+'/'+sh.file,'utf8'));
  for(const row of Object.values(data.stations||{})){
    const m=byPk.get(String(row.electroverseLocationPk)); if(!m)continue;
    const local=[...new Set((m.irvePdcIds||row.irvePdcIds||[]).map(norm).filter(Boolean))];
    for(const op of OPS){
      if(!local.some(p=>opOf(p)===op))continue;
      const r=reports[op];
      const missing=local.filter(p=>opOf(p)===op && !published.has(p));
      if(!missing.length)continue;
      r.locations++;
      for(const p of missing)r.missingPdcs.add(p);
      const unresolved=[];
      for(const e of row.tariff?.evses||[]){
        const raw=txt(e?.physicalReference); if(!raw)continue;
        const k=norm(raw);
        if(local.includes(k)||published.has(k))continue;
        unresolved.push({e,raw,k});r.unresolvedRefs++;
        const shape=/^\d+$/.test(raw)?'digits':/^[A-Za-z0-9]+$/.test(raw)?'alnum':raw.includes('*')?'asterisk':raw.includes('-')?'hyphenated':raw.includes('_')?'underscore':'other';
        r.shape[shape]=(r.shape[shape]||0)+1;
        r.refLength[k.length]=(r.refLength[k.length]||0)+1;
        r.localPdcCount[local.length]=(r.localPdcCount[local.length]||0)+1;
        const hs=missing.filter(p=>p.endsWith(k)); if(hs.length===1)r.uniqueMissingSuffixHitByLength[k.length]=(r.uniqueMissingSuffixHitByLength[k.length]||0)+1;
        const mm=raw.match(/^(.*?)[\s_\-\/]*([0-9]{1,2})$/);
        if(mm&&mm[1])r.ordinalStemCounts[norm(mm[1])]=(r.ordinalStemCounts[norm(mm[1])]||0)+1;
        if(r.samples.length<250)r.samples.push({locationPk:String(row.electroverseLocationPk),raw,k,missingPdcs:missing,localPdcs:local});
      }
      const key=`${unresolved.length}->${missing.length}`;
      r.unresolvedToMissingSetCardinality[key]=(r.unresolvedToMissingSetCardinality[key]||0)+1;
    }
  }
}

await fs.mkdir('reports',{recursive:true});
for(const op of OPS){
  const r=reports[op];
  const out={generatedAt:r.generatedAt,operator:op,locations:r.locations,unresolvedRefs:r.unresolvedRefs,uniqueMissingPdcs:r.missingPdcs.size,
    samples:r.samples,shape:top(r.shape),refLength:top(r.refLength),localPdcCount:top(r.localPdcCount),
    uniqueMissingSuffixHitByLength:top(r.uniqueMissingSuffixHitByLength),
    ordinalStemCounts:top(r.ordinalStemCounts).slice(0,100),
    unresolvedToMissingSetCardinality:top(r.unresolvedToMissingSetCardinality)};
  await fs.writeFile(`reports/electroverse-fr-${op.toLowerCase()}-unmatched.json`,JSON.stringify(out,null,2)+'\n');
  console.log(JSON.stringify(out,null,2));
}
