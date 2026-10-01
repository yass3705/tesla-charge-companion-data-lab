import fs from 'node:fs/promises';
import zlib from 'node:zlib';

const OPS=new Set(['P01','H01','SIP']);
const CACHE='data/electroverse/tariff_cache';
const MAP='data/electroverse/irve_location_mapping.json';
const OVERLAY='data/platforms/electroverse/france-evse';

const norm=x=>String(x??'').trim().toUpperCase().replace(/[^A-Z0-9]/g,'');
const txt=x=>String(x??'').trim();
const opFromRef=raw=>{
  const s=txt(raw), star=s.split('*').map(x=>x.trim()).filter(Boolean);
  if(star.length>=2&&/^FR$/i.test(star[0]))return star[1].toUpperCase();
  const n=norm(s),m=n.match(/^FR([A-Z0-9]{1,8})E/);if(m)return m[1];
  return null;
};
const top=o=>Object.entries(o).sort((a,b)=>b[1]-a[1]||a[0].localeCompare(b[0])).map(([key,count])=>({key,count}));

const mapping=JSON.parse(await fs.readFile(MAP,'utf8'));
const byPk=new Map((mapping.mappings||[]).map(m=>[String(m.electroverseLocationPk),m]));
const owners=new Map();
for(const m of mapping.mappings||[])for(const p of m.irvePdcIds||[]){
  const k=norm(p);if(!k)continue;
  const s=owners.get(k)||new Set();s.add(String(m.irveStationId??''));owners.set(k,s);
}
const oman=JSON.parse(await fs.readFile(OVERLAY+'/manifest.json','utf8'));
const publishedSourcePks=new Set(),publishedTargets=new Set();
for(const t of oman.tiles||[]){
  const tile=JSON.parse(zlib.gunzipSync(await fs.readFile(OVERLAY+'/'+t.file)));
  for(const o of tile.emspOffers||[]){
    for(const pk of o?.metadata?.electroverseEvsePks||[])if(pk!=null)publishedSourcePks.add(String(pk));
    if(o?.metadata?.electroverseEvsePk!=null)publishedSourcePks.add(String(o.metadata.electroverseEvsePk));
    for(const id of o.evseIds||[])publishedTargets.add(norm(id));
  }
}
const cman=JSON.parse(await fs.readFile(CACHE+'/manifest.json','utf8'));
const reports={};
for(const op of OPS)reports[op]={operator:op,residual:0,locations:0,modes:{},samples:[],candidateTargets:0};

for(const sh of cman.shards||[]){
  const data=JSON.parse(await fs.readFile(CACHE+'/'+sh.file,'utf8'));
  for(const row of Object.values(data.stations||{})){
    const m=byPk.get(String(row.electroverseLocationPk));
    const local=[...new Set((m?.irvePdcIds||row.irvePdcIds||[]).map(norm).filter(Boolean))];
    for(const op of OPS){
      const es=(row?.tariff?.evses||[]).filter(e=>e?.pk!=null&&!publishedSourcePks.has(String(e.pk))&&opFromRef(e?.physicalReference)===op);
      if(!es.length)continue;
      const r=reports[op];r.residual+=es.length;r.locations++;
      const available=local.filter(p=>!publishedTargets.has(p));
      const refs=es.map(e=>({e,raw:txt(e.physicalReference),k:norm(e.physicalReference)}));

      const exactSuffix=[];
      for(const x of refs){
        const matches=available.filter(p=>x.k.length>=4&&p.endsWith(x.k)&&(owners.get(p)?.size||0)===1);
        if(matches.length===1)exactSuffix.push({e:x.e,target:matches[0],raw:x.raw});
      }
      const suffixSafe=exactSuffix.length===es.length&&new Set(exactSuffix.map(x=>x.target)).size===exactSuffix.length;

      let commonPrefix=available[0]||'';
      for(const p of available.slice(1)){
        let i=0;while(i<commonPrefix.length&&i<p.length&&commonPrefix[i]===p[i])i++;
        commonPrefix=commonPrefix.slice(0,i);
      }
      const tailMap=new Map();let tailsUnique=true;
      for(const p of available){
        const tail=p.slice(commonPrefix.length);
        if(!tail||tailMap.has(tail)){tailsUnique=false;break;}
        tailMap.set(tail,p);
      }
      const tailMatches=refs.map(x=>({e:x.e,target:tailMap.get(x.k)||null,raw:x.raw}));
      const commonTailSafe=commonPrefix.length>=4&&tailsUnique&&tailMatches.every(x=>x.target&&(owners.get(x.target)?.size||0)===1)&&new Set(tailMatches.map(x=>x.target)).size===tailMatches.length;

      const parentOrdinal=[];
      for(const x of refs){
        const mm=x.raw.match(/^FR\*([A-Z0-9]+)\*E(.+?)\*(\d+)\*(\d+)$/i);
        if(!mm)continue;
        const parent=norm('FR'+mm[1]+'E'+mm[2]),a=Number(mm[3]),b=Number(mm[4]);
        for(const cand of [
          parent+String(a)+String(b),
          parent+String(a).padStart(2,'0')+String(b),
          parent+String(a).padStart(2,'0')+String(b).padStart(2,'0'),
          parent+String(a)
        ]){
          if(available.includes(cand)&&(owners.get(cand)?.size||0)===1){parentOrdinal.push({e:x.e,target:cand,raw:x.raw});break;}
        }
      }
      const parentOrdinalSafe=parentOrdinal.length===es.length&&new Set(parentOrdinal.map(x=>x.target)).size===parentOrdinal.length;

      const pricingSig=e=>JSON.stringify((e.connectors||[]).map(c=>({free:c?.isChargingFree??null,pc:c?.priceComponents??null,cp:c?.complexPricingDetail??null})));
      const homogeneousPricing=new Set(es.map(pricingSig)).size===1;
      const connectorCounts=new Set(es.map(e=>(e.connectors||[]).length));
      const exactSetSafe=es.length===available.length&&available.length>0&&available.every(p=>(owners.get(p)?.size||0)===1)&&homogeneousPricing;

      let mode='none',targets=0;
      if(suffixSafe){mode='unique_suffix_bijection';targets=exactSuffix.length;}
      else if(commonTailSafe){mode='common_tail_bijection';targets=tailMatches.length;}
      else if(parentOrdinalSafe){mode='parent_ordinal_bijection';targets=parentOrdinal.length;}
      else if(exactSetSafe){mode=connectorCounts.size===1?'homogeneous_exact_set':'price_only_exact_set';targets=available.length;}
      r.modes[mode]=(r.modes[mode]||0)+es.length;
      if(mode!=='none')r.candidateTargets+=targets;
      if(r.samples.length<30)r.samples.push({
        locationPk:String(row.electroverseLocationPk),irveStationId:m?.irveStationId??row.irveStationId??null,
        residualCount:es.length,availablePdcCount:available.length,mode,homogeneousPricing,uniformConnectorCount:connectorCounts.size===1,
        refs:refs.slice(0,20).map(x=>x.raw),available:available.slice(0,20),
        mappings:(suffixSafe?exactSuffix:commonTailSafe?tailMatches:parentOrdinalSafe?parentOrdinal:[]).slice(0,20).map(x=>({raw:x.raw,target:x.target}))
      });
    }
  }
}
await fs.mkdir('reports/electroverse',{recursive:true});
for(const op of OPS){
  const r=reports[op];
  const out={schemaVersion:1,generatedAt:new Date().toISOString(),...r,modeRanking:top(r.modes),
    safeRecoverable:Object.entries(r.modes).filter(([k])=>k!=='none').reduce((n,[,v])=>n+v,0)};
  await fs.writeFile(`reports/electroverse/${op.toLowerCase()}-residual-analysis.json`,JSON.stringify(out,null,2)+'\n');
  console.log(JSON.stringify(out,null,2));
}
