import fs from 'node:fs/promises';
import zlib from 'node:zlib';

const OVERLAY='data/platforms/electroverse/france-evse';
const PLAN='data/platforms/electroverse/validated-mappings/final-residual-recovery-plan.json';
const man=JSON.parse(await fs.readFile(OVERLAY+'/manifest.json','utf8'));
const plan=JSON.parse(await fs.readFile(PLAN,'utf8'));

const wanted=new Map();
for(const x of plan.individualMappings||[]){
  const k=String(x.electroverseLocationPk)+':'+String(x.electroverseEvsePk);
  wanted.set(k,{mode:String(x.mode||''),target:String(x.targetPdc||'')});
}
const seen=new Map();
let connectorPower=0,exactEvse=0,totalOffers=0;
for(const t of man.tiles||[]){
  const tile=JSON.parse(zlib.gunzipSync(await fs.readFile(OVERLAY+'/'+t.file)).toString('utf8'));
  for(const o of tile.emspOffers||[]){
    totalOffers++;
    const mode=o?.metadata?.identityMode;
    if(!['validated_final_residual_unique_suffix_bijection','validated_final_residual_common_tail_bijection'].includes(mode))continue;
    const pk=o?.metadata?.electroverseEvsePk;
    const loc=o?.metadata?.electroverseLocationPk;
    const k=String(loc)+':'+String(pk);
    const a=seen.get(k)||[];
    a.push({offerId:o.id,target:o.evseIds?.[0]??null,granularity:o?.metadata?.offerGranularity??'exact_evse',powerKw:o?.metadata?.powerKw??null});
    seen.set(k,a);
    if(o?.metadata?.offerGranularity==='connector_power')connectorPower++;else exactEvse++;
  }
}
const missing=[...wanted.entries()].filter(([k])=>!seen.has(k)).map(([k,v])=>({key:k,...v}));
const wrongTarget=[];
for(const [k,v] of wanted){
  const rows=seen.get(k)||[];
  if(rows.length && rows.some(r=>String(r.target).toUpperCase().replace(/[^A-Z0-9]/g,'')!==String(v.target).toUpperCase().replace(/[^A-Z0-9]/g,''))){
    wrongTarget.push({key:k,expected:v.target,seen:rows});
  }
}
const byMode={};
for(const [k,v] of wanted){
  const n=(seen.get(k)||[]).length;
  byMode[v.mode]??={planned:0,sourcesPublished:0,offers:0};
  byMode[v.mode].planned++;
  if(n)byMode[v.mode].sourcesPublished++;
  byMode[v.mode].offers+=n;
}
const out={
  generatedAt:new Date().toISOString(),
  overlayPublishedEvses:man.stats?.publishedEvses??null,
  plannedIndividuals:wanted.size,
  publishedPlannedSources:seen.size,
  missingPlannedSources:missing.length,
  connectorPowerOffers:connectorPower,
  exactEvseOffers:exactEvse,
  byMode,
  wrongTargetCount:wrongTarget.length,
  missing:missing.slice(0,100),
  wrongTarget:wrongTarget.slice(0,50)
};
await fs.mkdir('reports/electroverse',{recursive:true});
await fs.writeFile('reports/electroverse/final-residual-published-kpi-audit.json',JSON.stringify(out,null,2)+'\n');
console.log(JSON.stringify(out,null,2));
