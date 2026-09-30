import {execFileSync} from 'node:child_process';
import zlib from 'node:zlib';

const ROOT='data/platforms/electroverse/france-evse';
const MAIN_REF=process.env.MAIN_REF||'origin/main';

const stable=v=>{
  if(Array.isArray(v))return v.map(stable);
  if(v&&typeof v==='object')return Object.fromEntries(Object.keys(v).sort().map(k=>[k,stable(v[k])]));
  return v;
};
const sig=v=>JSON.stringify(stable(v));
const stripBands=pricing=>{
  const p=JSON.parse(JSON.stringify(pricing||{}));
  for(const r of p.rules||[])r.ocpiDurationBands=[];
  return p;
};
const readJsonFromRef=(ref,path)=>{
  const b=execFileSync('git',['show',`${ref}:${path}`],{maxBuffer:128*1024*1024});
  return JSON.parse(b.toString('utf8'));
};
const readGzFromRef=(ref,path)=>{
  const b=execFileSync('git',['show',`${ref}:${path}`],{encoding:null,maxBuffer:128*1024*1024});
  return JSON.parse(zlib.gunzipSync(b).toString('utf8'));
};
const load=ref=>{
  const m=readJsonFromRef(ref,`${ROOT}/manifest.json`);
  const byEvse=new Map();
  for(const t of m.tiles||[]){
    const p=readGzFromRef(ref,`${ROOT}/${t.file}`);
    for(const o of p.emspOffers||[]){
      const evse=String(o.evseIds?.[0]||'').trim();
      if(!evse)continue;
      if(byEvse.has(evse))throw new Error(`duplicate EVSE in ${ref}: ${evse}`);
      byEvse.set(evse,o);
    }
  }
  return{manifest:m,byEvse};
};

const main=load(MAIN_REF),lab=load('HEAD');
const common=[...main.byEvse.keys()].filter(k=>lab.byEvse.has(k));
const removed=[...main.byEvse.keys()].filter(k=>!lab.byEvse.has(k));
const added=[...lab.byEvse.keys()].filter(k=>!main.byEvse.has(k));

let exactUnchanged=0,durationMigrationChanged=0,unexpectedChanged=0;
const unexpectedSamples=[],durationMigrationSamples=[];
for(const k of common){
  const a=main.byEvse.get(k),b=lab.byEvse.get(k);
  if(sig(a.pricing)===sig(b.pricing)){exactUnchanged++;continue;}
  const labHasBands=(b.pricing?.rules||[]).some(r=>Array.isArray(r.ocpiDurationBands)&&r.ocpiDurationBands.length);
  if(labHasBands){
    durationMigrationChanged++;
    if(durationMigrationSamples.length<50)durationMigrationSamples.push({
      evseId:k,mainOfferId:a.id,labOfferId:b.id,
      mainIdentityMode:a.metadata?.identityMode||null,labIdentityMode:b.metadata?.identityMode||null,
      mainPricing:a.pricing,labPricing:b.pricing
    });
    continue;
  }
  unexpectedChanged++;
  if(unexpectedSamples.length<50)unexpectedSamples.push({
    evseId:k,mainOfferId:a.id,labOfferId:b.id,
    mainIdentityMode:a.metadata?.identityMode||null,labIdentityMode:b.metadata?.identityMode||null,
    mainPricing:a.pricing,labPricing:b.pricing
  });
}

const addedWithBands=added.filter(k=>(lab.byEvse.get(k)?.pricing?.rules||[]).some(r=>Array.isArray(r.ocpiDurationBands)&&r.ocpiDurationBands.length)).length;
const result={
  generatedAt:new Date().toISOString(),
  main:{publishedEvses:main.manifest.stats?.publishedEvses,tileCount:main.manifest.tileCount},
  lab:{publishedEvses:lab.manifest.stats?.publishedEvses,tileCount:lab.manifest.tileCount},
  common:common.length,
  added:added.length,
  removed:removed.length,
  addedWithDurationBands: addedWithBands,
  exactUnchanged,
  durationMigrationChanged,
  unexpectedChanged,
  verdict:removed.length===0&&unexpectedChanged===0?'PASS':'FAIL',
  removedSamples:removed.slice(0,50).map(k=>{
    const a=main.byEvse.get(k);
    return {evseId:k,offerId:a?.id||null,identityMode:a?.metadata?.identityMode||null,pricing:a?.pricing||null,metadata:a?.metadata||null};
  }),
  unexpectedSamples,
  durationMigrationSamples
};
console.log(JSON.stringify(result,null,2));
if(result.verdict!=='PASS')process.exitCode=1;
