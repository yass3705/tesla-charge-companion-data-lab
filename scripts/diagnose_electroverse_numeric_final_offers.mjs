import fs from 'node:fs/promises';
import zlib from 'node:zlib';

const MAPFILE='data/platforms/electroverse/validated-mappings/numeric-residual.json';
const OVERLAY='data/platforms/electroverse/france-evse';
const OUT='reports/electroverse/numeric-final-offer-diagnostic.json';
const norm=x=>String(x??'').trim().toUpperCase().replace(/[^A-Z0-9]/g,'');

const vm=JSON.parse(await fs.readFile(MAPFILE,'utf8'));
const man=JSON.parse(await fs.readFile(OVERLAY+'/manifest.json','utf8'));
const byPk=new Map(),byTarget=new Map();
for(const t of man.tiles||[]){
  const gz=await fs.readFile(OVERLAY+'/'+t.file);
  const tile=JSON.parse(zlib.gunzipSync(gz).toString('utf8'));
  for(const o of tile.emspOffers||[]){
    const pks=[];
    if(o?.metadata?.electroverseEvsePk!=null)pks.push(String(o.metadata.electroverseEvsePk));
    for(const pk of o?.metadata?.electroverseEvsePks||[])if(pk!=null)pks.push(String(pk));
    for(const pk of pks){
      const arr=byPk.get(pk)||[];
      arr.push({id:o.id,target:o.evseIds?.[0]||null,identityMode:o.metadata?.identityMode||null,pricing:o.pricing});
      byPk.set(pk,arr);
    }
    for(const target of o.evseIds||[]){
      const k=norm(target),arr=byTarget.get(k)||[];
      arr.push({id:o.id,identityMode:o.metadata?.identityMode||null,
        electroverseEvsePk:o.metadata?.electroverseEvsePk??null,
        electroverseEvsePks:o.metadata?.electroverseEvsePks??null,
        physicalReference:o.metadata?.physicalReference??null,
        physicalReferences:o.metadata?.physicalReferences??null});
      byTarget.set(k,arr);
    }
  }
}
const rows=[];const summary={directValidated:0,publishedSameTargetOtherMode:0,publishedDifferentTarget:0,sourceAbsentButTargetPublished:0,fullyAbsent:0};
const modes={};
for(const m of vm.mappings||[]){
  const pk=String(m.electroverseEvsePk),target=norm(m.targetPdc);
  const offers=byPk.get(pk)||[];
  const targetOffers=byTarget.get(target)||[];
  let category;
  if(offers.some(o=>o.identityMode==='validated_numeric_residual_unique_bijection'&&norm(o.target)===target)){
    category='directValidated';summary.directValidated++;
  }else if(offers.some(o=>norm(o.target)===target)){
    category='publishedSameTargetOtherMode';summary.publishedSameTargetOtherMode++;
  }else if(offers.length){
    category='publishedDifferentTarget';summary.publishedDifferentTarget++;
  }else if(targetOffers.length){
    category='sourceAbsentButTargetPublished';summary.sourceAbsentButTargetPublished++;
  }else{
    category='fullyAbsent';summary.fullyAbsent++;
  }
  for(const o of offers)modes[o.identityMode]=(modes[o.identityMode]||0)+1;
  rows.push({locationPk:String(m.electroverseLocationPk),evsePk:m.electroverseEvsePk,physicalReference:m.physicalReference,
    mappedTarget:m.targetPdc,category,sourceOffers:offers,targetOffers});
}
const out={generatedAt:new Date().toISOString(),mappingCount:(vm.mappings||[]).length,summary,modes,rows};
await fs.mkdir('reports/electroverse',{recursive:true});
await fs.writeFile(OUT,JSON.stringify(out,null,2)+'\n');
console.log(JSON.stringify({generatedAt:out.generatedAt,mappingCount:out.mappingCount,summary,modes,samples:rows.slice(0,30)},null,2));
