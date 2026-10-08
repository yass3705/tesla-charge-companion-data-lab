/**
 * Second-pass evidence for two strict EVSE matches and collisions found in the
 * first-pass alphanumeric audit. Read-only.
 */
import fs from 'node:fs/promises';
import zlib from 'node:zlib';
const norm=x=>String(x??'').toUpperCase().replace(/[^A-Z0-9]/g,'');
const gunzip=async p=>JSON.parse(zlib.gunzipSync(await fs.readFile(p)).toString('utf8'));
const cases=await gunzip('reports/france/irve/alphanumeric-residual-cases-2026-10-08.json.gz');
const targets=cases.electroverse.filter(c=>c.reason==='review_ready_strict_unpublished_evse'||c.reason==='multiple_source_evse_claims_same_target');
const desiredPks=new Set(targets.map(t=>t.locationPk));
const cman=JSON.parse(await fs.readFile('data/electroverse/tariff_cache/manifest.json','utf8'));
const sourceLocations=new Map();
for(const shard of cman.shards||[]){
  const payload=JSON.parse(await fs.readFile('data/electroverse/tariff_cache/'+shard.file,'utf8'));
  for(const row of Object.values(payload.stations||{})){
    const pk=String(row.electroverseLocationPk);if(desiredPks.has(pk))sourceLocations.set(pk,row);
  }
}
const national=await gunzip('data/national/france-irve-static-v9/all.json.gz');
const nationalById=new Map();
for(const row of national)for(const cfg of row?.[8]||[])for(const pdc of cfg?.[6]||[]){
  const k=norm(pdc);if(!k)continue;
  if(!nationalById.has(k))nationalById.set(k,[]);
  const target={stationId:row[0],stationName:row[1],address:row[2],lat:row[3],lon:row[4],operator:row[5],connector:cfg[1],powerKw:cfg[3],pdc};
  if(!nationalById.get(k).some(x=>x.stationId===target.stationId&&x.pdc===target.pdc))nationalById.get(k).push(target);
}
const group=new Map();
for(const candidate of targets){
 const k=norm(candidate.candidateIrvePdc),list=group.get(k)||[];
 list.push(candidate);group.set(k,list);
}
const inspected=[];
for(const [k,targets] of group){
  const members=targets.map(t=>{
    const row=sourceLocations.get(t.locationPk),e=(row?.tariff?.evses||[]).find(e=>String(e.pk)===String(t.sourceEvsePk));
    const cs=(e?.connectors||[]).map(c=>({
      pk:c.pk||null,standard:c.standard||c.connectorType||null,
      kilowatts:c.kilowatts||c.powerKw||null,
      isChargingFree:c.isChargingFree??null,
      priceComponents:c.priceComponents||[],
      complexPricingDetail:c.complexPricingDetail||null
    }));
    return{locationPk:t.locationPk,evsePk:t.sourceEvsePk,physicalReference:t.physicalReference,
      locationName:row?.name||row?.location?.name||null,
      connectorCount:cs.length,connectors:cs,
      pricesSignature:JSON.stringify(cs.map(c=>({priceComponents:c.priceComponents,complexPricingDetail:c.complexPricingDetail})))
    };
  });
  const profiles=[...new Set(members.map(m=>m.pricesSignature))];
  const result={normalizedIrve:k,nationalPdc:nationalById.get(k)||[],
    sourceEvseCount:members.length,distinctTariffProfiles:profiles.length,
    verdict:members.length===1?'one_to_one_identity_tariff_requires_validation':
      profiles.length===1?'duplicate_evse_aliases_same_tariff_review_connector_profiles':
      'genuine_source_tariff_conflict_do_not_publish',
    members:members.map(({pricesSignature,...m})=>m)};
  inspected.push(result);
}
const out={
  schemaVersion:1,generatedAt:new Date().toISOString(),
  policy:'Evidence only; matching identifiers alone do not establish pricing validity or replace immutable EVSE power granularity.',
  stats:{normalizedIrveTargets:inspected.length,oneToOne:inspected.filter(x=>x.sourceEvseCount===1).length,
    multiSourceSameTariff:inspected.filter(x=>x.sourceEvseCount>1&&x.distinctTariffProfiles===1).length,
    multiSourceConflictingTariff:inspected.filter(x=>x.sourceEvseCount>1&&x.distinctTariffProfiles>1).length,
    missingSourceEvse:inspected.flatMap(x=>x.members).filter(x=>x.connectorCount===0).length},
  candidates:inspected
};
await fs.writeFile('reports/france/irve/electroverse-alnum-candidate-evidence-2026-10-08.json',JSON.stringify(out,null,2)+'\n');
console.log(JSON.stringify({stats:out.stats,first:inspected.slice(0,7).map(x=>({pdc:x.normalizedIrve,verdict:x.verdict,sourceEvseCount:x.sourceEvseCount,profiles:x.distinctTariffProfiles,members:x.members.map(m=>({evsePk:m.evsePk,connectors:m.connectors?.map(c=>({kw:c.kilowatts,components:c.priceComponents}))}))}))}));
