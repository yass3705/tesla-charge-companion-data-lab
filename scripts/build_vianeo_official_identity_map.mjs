import fs from 'node:fs/promises';
import zlib from 'node:zlib';

const CANON='data/national/france_public_charging_canonical.json';
const CACHE='data/electroverse/tariff_cache';
const CACHE_MANIFEST=CACHE+'/manifest.json';
const MAP='data/electroverse/irve_location_mapping.json';
const OVERLAY='data/platforms/electroverse/france-evse';
const OUT='data/operator_direct/vianeo_official_identity_map.json';
const REPORT='reports/electroverse-fr-via-official-identity-audit.json';

const norm=x=>String(x??'').trim().toUpperCase().replace(/[^A-Z0-9]/g,'');
const text=x=>String(x??'').trim();

const canonical=JSON.parse(await fs.readFile(CANON,'utf8'));
const rows=[];
for(const src of canonical.operatorDirectSources||[]){
  for(const r of src?.payload?.exact||[]){
    const pdc=text(r?.id_pdc_itinerance);
    if(!norm(pdc).startsWith('FRVIAE'))continue;
    const stationName=text(r?.stationName);
    const evseId=text(r?.evseId);
    const token=stationName.split(/\s+/)[0]||'';
    const cm=evseId.match(/\*(\d+)$/);
    const connector=cm?Number(cm[1]):null;
    let sourceRef=null,mode=null;
    let m=token.match(/^(\d{5,8}-\d{2})-(\d+)$/);
    if(m&&Number.isFinite(connector)){
      sourceRef=`${m[1]}-${connector}`;
      mode='station_token_device_plus_evse_connector';
    }else{
      m=token.match(/^(\d{5,8})-(\d{2})$/);
      if(m&&Number.isFinite(connector)){
        sourceRef=`${m[1]}-${String(connector).padStart(2,'0')}`;
        mode='station_token_base_plus_evse_connector';
      }
    }
    if(!sourceRef)continue;
    rows.push({
      sourceRef,
      sourceNorm:norm(sourceRef),
      targetPdc:pdc,
      targetNorm:norm(pdc),
      evseId,
      stationName,
      stationToken:token,
      deviceId:r?.deviceId??null,
      stationId:r?.id_station_itinerance??null,
      hostName:r?.hostName??null,
      mode
    });
  }
}
const dedup=new Map();
for(const r of rows){
  const k=r.sourceNorm+'|'+r.targetNorm;
  if(!dedup.has(k))dedup.set(k,r);
}
const sourceTargets=new Map();
for(const r of dedup.values()){
  const s=sourceTargets.get(r.sourceNorm)||new Set();
  s.add(r.targetNorm);sourceTargets.set(r.sourceNorm,s);
}
const uniqueRows=[...dedup.values()].filter(r=>(sourceTargets.get(r.sourceNorm)?.size||0)===1);

const mapping=JSON.parse(await fs.readFile(MAP,'utf8'));
const byPk=new Map((mapping.mappings||[]).map(m=>[String(m.electroverseLocationPk),m]));
const globalPdcOwners=new Map();
for(const m of mapping.mappings||[])for(const p of m.irvePdcIds||[]){
  const k=norm(p);if(!k)continue;
  const s=globalPdcOwners.get(k)||new Set();s.add(m.irveStationId);globalPdcOwners.set(k,s);
}
const overlayManifest=JSON.parse(await fs.readFile(OVERLAY+'/manifest.json','utf8'));
const published=new Set();
for(const t of overlayManifest.tiles||[]){
  const gz=await fs.readFile(OVERLAY+'/'+t.file);
  const p=JSON.parse(zlib.gunzipSync(gz).toString('utf8'));
  for(const o of p.emspOffers||[])for(const id of o.evseIds||[])published.add(norm(id));
}
const directBySource=new Map(uniqueRows.map(r=>[r.sourceNorm,r]));
const cacheManifest=JSON.parse(await fs.readFile(CACHE_MANIFEST,'utf8'));
let residualRefs=0,candidates=0,alreadyPublished=0,notLocal=0,notGlobalUnique=0;
const samples=[];
const candidateKeys=new Set();
for(const sh of cacheManifest.shards||[]){
  const data=JSON.parse(await fs.readFile(CACHE+'/'+sh.file,'utf8'));
  for(const row of Object.values(data.stations||{})){
    const m=byPk.get(String(row.electroverseLocationPk));if(!m)continue;
    const local=new Set((m.irvePdcIds||row.irvePdcIds||[]).map(norm).filter(Boolean));
    if(![...local].some(p=>p.startsWith('FRVIAE')))continue;
    for(const e of row.tariff?.evses||[]){
      const raw=text(e?.physicalReference);if(!raw)continue;
      const k=norm(raw);
      if(local.has(k)||published.has(k))continue;
      residualRefs++;
      const d=directBySource.get(k);if(!d)continue;
      if(published.has(d.targetNorm)){alreadyPublished++;continue;}
      if(!local.has(d.targetNorm)){notLocal++;continue;}
      if((globalPdcOwners.get(d.targetNorm)?.size||0)!==1){notGlobalUnique++;continue;}
      const ck=String(row.electroverseLocationPk)+'|'+String(e.pk??'')+'|'+d.targetNorm;
      if(candidateKeys.has(ck))continue;candidateKeys.add(ck);
      candidates++;
      if(samples.length<80)samples.push({
        locationPk:String(row.electroverseLocationPk),
        evsePk:e.pk??null,
        physicalReference:raw,
        targetPdc:d.targetPdc,
        stationName:d.stationName,
        evseId:d.evseId,
        mode:d.mode
      });
    }
  }
}
const output={
  schemaVersion:1,
  generatedAt:new Date().toISOString(),
  source:'France canonical operatorDirectSources Vianeo exact inventory',
  rows:uniqueRows
};
const report={
  generatedAt:new Date().toISOString(),
  extractedPairs:rows.length,
  dedupPairs:dedup.size,
  uniqueSourceRows:uniqueRows.length,
  ambiguousSourceRefs:[...sourceTargets.entries()].filter(([,s])=>s.size!==1).length,
  residualRefs,
  candidates,
  alreadyPublished,
  notLocal,
  notGlobalUnique,
  samples
};
await fs.mkdir('data/operator_direct',{recursive:true});
await fs.mkdir('reports',{recursive:true});
await fs.writeFile(OUT,JSON.stringify(output,null,2)+'\n');
await fs.writeFile(REPORT,JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify(report,null,2));
