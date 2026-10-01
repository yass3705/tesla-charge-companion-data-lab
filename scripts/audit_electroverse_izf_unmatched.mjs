import fs from 'node:fs/promises';
import zlib from 'node:zlib';

const CACHE='data/electroverse/tariff_cache';
const MANIFEST=CACHE+'/manifest.json';
const MAP='data/electroverse/irve_location_mapping.json';
const OVERLAY='data/platforms/electroverse/france-evse';
const OUT='reports/electroverse-fr-izf-unmatched.json';

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

const rows=[], shapes={}, refLens={}, localCounts={}, suffixHits={}, ordinalGroups={};
for(const sh of manifest.shards||[]){
  const data=JSON.parse(await fs.readFile(CACHE+'/'+sh.file,'utf8'));
  for(const row of Object.values(data.stations||{})){
    const m=byPk.get(String(row.electroverseLocationPk)); if(!m)continue;
    const local=[...new Set((m.irvePdcIds||row.irvePdcIds||[]).map(norm).filter(Boolean))];
    if(!local.length || !local.some(p=>opOf(p)==='IZF'))continue;
    const missing=local.filter(p=>!published.has(p));
    if(!missing.length)continue;
    for(const e of row.tariff?.evses||[]){
      const raw=txt(e?.physicalReference); if(!raw)continue;
      const k=norm(raw);
      if(local.includes(k))continue;
      if(published.has(k))continue;
      const rec={locationPk:String(row.electroverseLocationPk),raw,k,missingPdcs:missing,localPdcs:local};
      const shape=/^\d+$/.test(raw)?'digits':/^[A-Za-z0-9]+$/.test(raw)?'alnum':raw.includes('*')?'asterisk':raw.includes('-')?'hyphenated':'other';
      shapes[shape]=(shapes[shape]||0)+1; refLens[k.length]=(refLens[k.length]||0)+1; localCounts[local.length]=(localCounts[local.length]||0)+1;
      const hs=missing.filter(p=>p.endsWith(k)); if(hs.length===1)suffixHits[k.length]=(suffixHits[k.length]||0)+1;
      const mm=raw.match(/^(.*?)[\s_\-\/]*([0-9]{1,2})$/);
      if(mm&&mm[1]){const key=norm(mm[1]);ordinalGroups[key]=(ordinalGroups[key]||0)+1;}
      if(rows.length<250)rows.push(rec);
    }
  }
}
const report={generatedAt:new Date().toISOString(),operator:'IZF',samples:rows,shape:top(shapes),refLength:top(refLens),localPdcCount:top(localCounts),uniqueMissingSuffixHitByLength:top(suffixHits),ordinalStemCounts:top(ordinalGroups).slice(0,100)};
await fs.mkdir('reports',{recursive:true});
await fs.writeFile(OUT,JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify(report,null,2));
