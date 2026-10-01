import fs from 'node:fs/promises';
import zlib from 'node:zlib';

const CACHE='data/electroverse/tariff_cache';
const MAP='data/electroverse/irve_location_mapping.json';
const OVERLAY='data/platforms/electroverse/france-evse';
const OUT='reports/electroverse/numeric-residual-analysis.json';
const norm=x=>String(x??'').trim().toUpperCase().replace(/[^A-Z0-9]/g,'');

const mapping=JSON.parse(await fs.readFile(MAP,'utf8'));
const byPk=new Map((mapping.mappings||[]).map(m=>[String(m.electroverseLocationPk),m]));

const oman=JSON.parse(await fs.readFile(OVERLAY+'/manifest.json','utf8'));
const publishedSourcePks=new Set(),publishedTargets=new Set();
for(const t of oman.tiles||[]){
  const gz=await fs.readFile(OVERLAY+'/'+t.file);
  const tile=JSON.parse(zlib.gunzipSync(gz));
  for(const o of tile.emspOffers||[]){
    for(const pk of o?.metadata?.electroverseEvsePks||[]) if(pk!=null) publishedSourcePks.add(String(pk));
    if(o?.metadata?.electroverseEvsePk!=null) publishedSourcePks.add(String(o.metadata.electroverseEvsePk));
    for(const id of o.evseIds||[]) publishedTargets.add(norm(id));
  }
}

const currentOwners=new Map();
for(const m of mapping.mappings||[]) for(const p of m.irvePdcIds||[]){
  const k=norm(p); if(!k)continue;
  const s=currentOwners.get(k)||new Set(); s.add(String(m.irveStationId??'')); currentOwners.set(k,s);
}

const cman=JSON.parse(await fs.readFile(CACHE+'/manifest.json','utf8'));
const groups=[];
let numericResidual=0,locations=0;
for(const sh of cman.shards||[]){
  const data=JSON.parse(await fs.readFile(CACHE+'/'+sh.file,'utf8'));
  for(const row of Object.values(data.stations||{})){
    const all=(row?.tariff?.evses||[]);
    const numeric=all.filter(e=>e?.pk!=null && !publishedSourcePks.has(String(e.pk)) && /^\d{1,3}$/.test(String(e?.physicalReference??'').trim()));
    if(!numeric.length)continue;
    numericResidual+=numeric.length; locations++;
    const m=byPk.get(String(row.electroverseLocationPk));
    const local=[...new Set((m?.irvePdcIds||row.irvePdcIds||[]).map(norm).filter(Boolean))];
    const available=local.filter(p=>!publishedTargets.has(p));
    const nums=[...new Set(numeric.map(e=>Number(String(e.physicalReference).trim())))].sort((a,b)=>a-b);
    const duplicateSourceOrdinals=nums.length!==numeric.length;
    const candidates=[];
    if(!duplicateSourceOrdinals && available.length){
      for(const width of [1,2,3]){
        const byPrefix=new Map();
        for(const p of available){
          if(p.length<=width)continue;
          const tail=p.slice(-width); if(!/^\d+$/.test(tail))continue;
          const prefix=p.slice(0,-width),n=Number(tail);
          const arr=byPrefix.get(prefix)||[]; arr.push({p,n}); byPrefix.set(prefix,arr);
        }
        for(const [prefix,rows] of byPrefix){
          const wanted=new Set(nums);
          const hits=rows.filter(r=>wanted.has(r.n));
          if(hits.length!==numeric.length)continue;
          if(new Set(hits.map(r=>r.n)).size!==numeric.length)continue;
          if(hits.some(r=>(currentOwners.get(r.p)?.size||0)!==1))continue;
          candidates.push({width,prefix,targets:hits.sort((a,b)=>a.n-b.n)});
        }
      }
    }
    const exactCandidates=[];
    const seen=new Set();
    for(const c of candidates){
      const sig=c.targets.map(x=>x.n+':'+x.p).join('|');
      if(seen.has(sig))continue; seen.add(sig); exactCandidates.push(c);
    }
    groups.push({
      electroverseLocationPk:String(row.electroverseLocationPk),
      irveStationId:m?.irveStationId??row.irveStationId??null,
      numericResidualCount:numeric.length,
      ordinals:numeric.map(e=>({evsePk:e.pk,physicalReference:String(e.physicalReference),n:Number(e.physicalReference),connectorCount:(e.connectors||[]).length})),
      localPdcCount:local.length,
      availablePdcCount:available.length,
      duplicateSourceOrdinals,
      exactCandidateCount:exactCandidates.length,
      exactCandidates:exactCandidates.slice(0,3)
    });
  }
}
const buckets={};
for(const g of groups){
  const k=g.duplicateSourceOrdinals?'duplicate_source_ordinals':g.exactCandidateCount===1?'unique_bijection':g.exactCandidateCount>1?'multiple_bijections':'no_bijection';
  buckets[k]=(buckets[k]||0)+g.numericResidualCount;
}
const solvable=groups.filter(g=>!g.duplicateSourceOrdinals&&g.exactCandidateCount===1);
const validatedMappings=[];
for(const g of solvable){
  const cand=g.exactCandidates[0];
  const byOrd=new Map(cand.targets.map(x=>[x.n,x.p]));
  for(const x of g.ordinals){
    const target=byOrd.get(x.n);
    if(!target)continue;
    validatedMappings.push({
      electroverseLocationPk:g.electroverseLocationPk,
      electroverseEvsePk:x.evsePk,
      physicalReference:x.physicalReference,
      targetPdc:target,
      evidence:{
        mode:'strict_post_overlay_numeric_suffix_bijection',
        width:cand.width,
        prefix:cand.prefix,
        sourceResidualCount:g.numericResidualCount,
        availablePdcCount:g.availablePdcCount
      }
    });
  }
}
const validatedOut={
  schemaVersion:1,
  generatedAt:new Date().toISOString(),
  dataset:'electroverse-france-validated-numeric-residual-mappings',
  count:validatedMappings.length,
  policy:'Generated only from unique post-overlay suffix-ordinal bijections with globally unique national PDC targets; no proximity inference.',
  mappings:validatedMappings
};
await fs.mkdir('data/platforms/electroverse/validated-mappings',{recursive:true});
await fs.writeFile('data/platforms/electroverse/validated-mappings/numeric-residual.json',JSON.stringify(validatedOut,null,2)+'\n');

const out={
  schemaVersion:1,
  generatedAt:new Date().toISOString(),
  numericResidualSourceEvses:numericResidual,
  affectedLocations:locations,
  buckets,
  uniquelySolvableSourceEvses:solvable.reduce((n,g)=>n+g.numericResidualCount,0),
  uniquelySolvableLocations:solvable.length,
  topSolvableGroups:solvable.sort((a,b)=>b.numericResidualCount-a.numericResidualCount).slice(0,100),
  ambiguousSamples:groups.filter(g=>g.duplicateSourceOrdinals||g.exactCandidateCount!==1).slice(0,100),
  policy:'Diagnostic only. Uses currently unpublished numeric source EVSEs and currently unpublished national targets. Unique suffix-ordinal bijection only; globally unique PDCs required; no proximity inference.'
};
await fs.mkdir('reports/electroverse',{recursive:true});
await fs.writeFile(OUT,JSON.stringify(out,null,2)+'\n');
console.log(JSON.stringify(out,null,2));
