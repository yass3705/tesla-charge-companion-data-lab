import fs from 'node:fs/promises';
import zlib from 'node:zlib';

const CACHE='data/electroverse/tariff_cache';
const MAP='data/electroverse/irve_location_mapping.json';
const OVERLAY='data/platforms/electroverse/france-evse';
const OUT='reports/electroverse/actionable-gaps-analysis.json';
const VALIDATED='data/platforms/electroverse/validated-mappings/actionable-gaps.json';
const norm=x=>String(x??'').trim().toUpperCase().replace(/[^A-Z0-9]/g,'');
const opFromRef=raw=>{
  const s=String(raw??'').trim();
  const star=s.split('*').map(x=>x.trim()).filter(Boolean);
  if(star.length>=2 && /^FR$/i.test(star[0])) return star[1].toUpperCase();
  const n=norm(s);
  const m=n.match(/^FR([A-Z0-9]{1,8})E/);
  if(m)return m[1];
  if(/^MAT\d+/i.test(s))return 'MAT';
  if(/^B\d+/i.test(s))return 'B';
  if(/^\d+$/.test(s))return 'NUMERIC';
  return n.slice(0,12)||'MISSING';
};
const mapping=JSON.parse(await fs.readFile(MAP,'utf8'));
const byPk=new Map((mapping.mappings||[]).map(m=>[String(m.electroverseLocationPk),m]));
const oman=JSON.parse(await fs.readFile(OVERLAY+'/manifest.json','utf8'));
const publishedSourcePks=new Set(),publishedTargets=new Set();
for(const t of oman.tiles||[]){
  const tile=JSON.parse(zlib.gunzipSync(await fs.readFile(OVERLAY+'/'+t.file)));
  for(const o of tile.emspOffers||[]){
    for(const pk of o?.metadata?.electroverseEvsePks||[]) if(pk!=null)publishedSourcePks.add(String(pk));
    if(o?.metadata?.electroverseEvsePk!=null)publishedSourcePks.add(String(o.metadata.electroverseEvsePk));
    for(const id of o.evseIds||[])publishedTargets.add(norm(id));
  }
}
const owners=new Map();
for(const m of mapping.mappings||[]) for(const p of m.irvePdcIds||[]){
  const k=norm(p);if(!k)continue;
  const s=owners.get(k)||new Set();s.add(String(m.irveStationId??''));owners.set(k,s);
}
const cman=JSON.parse(await fs.readFile(CACHE+'/manifest.json','utf8'));
const buckets=new Map();
const validated=[];
for(const sh of cman.shards||[]){
  const data=JSON.parse(await fs.readFile(CACHE+'/'+sh.file,'utf8'));
  for(const row of Object.values(data.stations||{})){
    const candidates=(row?.tariff?.evses||[]).filter(e=>e?.pk!=null&&!publishedSourcePks.has(String(e.pk)));
    if(!candidates.length)continue;
    const byBucket=new Map();
    for(const e of candidates){
      const b=opFromRef(e.physicalReference);const a=byBucket.get(b)||[];a.push(e);byBucket.set(b,a);
    }
    const m=byPk.get(String(row.electroverseLocationPk));
    const local=[...new Set((m?.irvePdcIds||row.irvePdcIds||[]).map(norm).filter(Boolean))];
    const available=local.filter(p=>!publishedTargets.has(p));
    for(const [bucket,es] of byBucket){
      const refs=es.map(e=>({e,k:norm(e.physicalReference),raw:String(e.physicalReference)}));
      const exact=[];
      for(const x of refs){
        const matches=available.filter(p=>x.k.length>=4&&p.endsWith(x.k)&&(owners.get(p)?.size||0)===1);
        if(matches.length===1)exact.push({evsePk:x.e.pk,target:matches[0],raw:x.raw});
      }
      let mode='none',maps=[];
      if(exact.length===es.length&&new Set(exact.map(x=>x.target)).size===exact.length){
        mode='unique_suffix_bijection';maps=exact;
      }else{
        let commonPrefix='';
        if(available.length){
          commonPrefix=available[0];
          for(const p of available.slice(1)){let i=0;while(i<commonPrefix.length&&i<p.length&&commonPrefix[i]===p[i])i++;commonPrefix=commonPrefix.slice(0,i);if(!commonPrefix)break;}
        }
        const tailMap=new Map();let tailsUnique=true;
        for(const p of available){const tail=p.slice(commonPrefix.length);if(!tail||tailMap.has(tail)){tailsUnique=false;break;}tailMap.set(tail,p);}
        const tails=refs.map(x=>({evsePk:x.e.pk,target:tailMap.get(x.k)||null,raw:x.raw}));
        if(commonPrefix.length>=4&&tailsUnique&&tails.every(x=>x.target&&(owners.get(x.target)?.size||0)===1)&&new Set(tails.map(x=>x.target)).size===tails.length){
          mode='common_tail_bijection';maps=tails;
        }
      }
      const rec=buckets.get(bucket)||{bucket,residualSourceEvses:0,affectedLocations:0,safelyRecoverableSourceEvses:0,groups:[]};
      rec.residualSourceEvses+=es.length;rec.affectedLocations++;
      if(mode!=='none')rec.safelyRecoverableSourceEvses+=es.length;
      rec.groups.push({electroverseLocationPk:String(row.electroverseLocationPk),irveStationId:m?.irveStationId??row.irveStationId??null,residualCount:es.length,availablePdcCount:available.length,mode,refs:refs.map(x=>({evsePk:x.e.pk,physicalReference:x.raw,connectorCount:(x.e.connectors||[]).length})).slice(0,30),mappings:maps.slice(0,30)});
      buckets.set(bucket,rec);
      if(mode!=='none') for(const x of maps) validated.push({
        bucket,electroverseLocationPk:String(row.electroverseLocationPk),irveStationId:m?.irveStationId??row.irveStationId??null,
        electroverseEvsePk:x.evsePk,targetPdc:x.target,physicalReference:x.raw,recoveryMode:'validated_generic_'+mode,
        evidence:'strict local unpublished globally-unique target; full bucket-location bijection; no proximity'
      });
    }
  }
}
const rows=[...buckets.values()].sort((a,b)=>b.residualSourceEvses-a.residualSourceEvses);
const generatedAt=new Date().toISOString();
await fs.mkdir('reports/electroverse',{recursive:true});
await fs.mkdir('data/platforms/electroverse/validated-mappings',{recursive:true});
await fs.writeFile(OUT,JSON.stringify({schemaVersion:1,generatedAt,buckets:rows,totalResidual:rows.reduce((n,x)=>n+x.residualSourceEvses,0),totalSafelyRecoverable:validated.length},null,2)+'\n');
await fs.writeFile(VALIDATED,JSON.stringify({schemaVersion:1,generatedAt,count:validated.length,policy:'Only full unique suffix or full common-tail bijections against local unpublished globally unique targets; no proximity.',mappings:validated},null,2)+'\n');
console.log(JSON.stringify({generatedAt,buckets:rows.map(x=>({bucket:x.bucket,residual:x.residualSourceEvses,locations:x.affectedLocations,safe:x.safelyRecoverableSourceEvses})),validated:validated.length},null,2));
