import fs from 'node:fs/promises';
import zlib from 'node:zlib';
const PLAN='data/platforms/electroverse/validated-mappings/final-residual-recovery-plan.json';
const OUTDIR='data/platforms/electroverse/france-evse';
const OUT='reports/electroverse-final-residual-supersession.json';
const norm=x=>String(x??'').trim().toUpperCase().replace(/[^A-Z0-9]/g,'');
const plan=JSON.parse(await fs.readFile(PLAN,'utf8'));
const man=JSON.parse(await fs.readFile(OUTDIR+'/manifest.json','utf8'));
const targetModes=new Map();
for(const t of man.tiles||[]){
  const gz=await fs.readFile(OUTDIR+'/'+t.file);
  const p=JSON.parse(zlib.gunzipSync(gz).toString('utf8'));
  for(const o of p.emspOffers||[]){
    for(const id of o.evseIds||[]){
      const k=norm(id);
      const a=targetModes.get(k)||[];
      a.push(o.metadata?.identityMode||'UNKNOWN');
      targetModes.set(k,a);
    }
  }
}
const summary={unique_suffix_bijection:{total:0,alreadyPublished:0,notPublished:0,existingModes:{}},common_tail_bijection:{total:0,alreadyPublished:0,notPublished:0,existingModes:{}}};
const samples=[];
for(const x of plan.individualMappings||[]){
  const mode=String(x.mode||'');
  if(!summary[mode])continue;
  const s=summary[mode];s.total++;
  const k=norm(x.targetPdc);
  const modes=targetModes.get(k)||[];
  if(modes.length){
    s.alreadyPublished++;
    for(const m of modes)s.existingModes[m]=(s.existingModes[m]||0)+1;
  }else{
    s.notPublished++;
    if(samples.length<100)samples.push({mode,operator:x.operator,locationPk:x.electroverseLocationPk,evsePk:x.electroverseEvsePk,physicalReference:x.physicalReference,targetPdc:x.targetPdc});
  }
}
const out={generatedAt:new Date().toISOString(),publishedEvses:man.stats?.publishedEvses||null,summary,samples};
await fs.mkdir('reports',{recursive:true});
await fs.writeFile(OUT,JSON.stringify(out,null,2)+'\n');
console.log(JSON.stringify(out,null,2));