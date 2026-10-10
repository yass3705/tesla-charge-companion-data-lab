import assert from 'node:assert/strict';
import fs from 'node:fs';
const src=fs.readFileSync('scripts/electra_france_platform_snapshot.mjs','utf8');
const first=src.indexOf('function powerScope(t){'),last=src.indexOf('const first=await page(0)',first);
assert.ok(first>0&&last>first,'power-scoped assignment helper exists');
const powerScope=new Function(src.slice(first,last)+';return powerScope;')();
const p=(min,max)=>({elements:[{restrictions:{minPower:min,maxPower:max},priceComponents:[{type:'ENERGY',price:0.4}]}]});
assert.deepEqual(powerScope(p(0,22)),{min:0,max:22});
assert.deepEqual(powerScope(p(50,150)),{min:50,max:150});
assert.equal(powerScope({elements:[{restrictions:{},priceComponents:[{type:'ENERGY',price:.5}]}]}),null,'no tariff-to-EVSE attribution from location price alone');
assert.equal(powerScope({elements:[{restrictions:{minPower:20,maxPower:30}},{restrictions:{minPower:50,maxPower:100}}]}),null,'incompatible restrictions never guessed');
assert.ok(src.includes("evseIds:[pdc]")&&src.includes("verifiedScope:'exact_evse'"),'one offer per EVSE, never station-level tariff');
assert.ok(src.includes("reject('same_power_tariff_assignment_ambiguous')"),'same-power ambiguity fails closed');
assert.ok(src.includes("reject('no_tariff')"),'missing tariff is not invented');

const verified=JSON.parse(fs.readFileSync('data/platforms/electra/verified-app-evse-tariff-map.json','utf8'));
assert.equal(verified.schemaVersion,1,'evidence ledger validated');
assert.equal(verified.verifiedLinks.length,2,'Jarville and Saint-Arnoult are the only manual screenshot sites');
const jarville=verified.verifiedLinks[0];
assert.equal(jarville.cpo,'Powerdot');
assert.equal(jarville.mappings.length,2,'only 22 and 60 kW EVSEs proven');
assert.deepEqual(jarville.mappings.map(x=>x.powerKw).sort((a,b)=>a-b),[22,60]);
assert.ok(!jarville.mappings.some(x=>x.evseId.endsWith('*1')),'unverified 50kW CHAdeMO excluded');
assert.ok(jarville.mappings.every(x=>x.components.length===1&&x.components[0]==='ENERGY'),'no uncertain session fee');
const saint=verified.verifiedLinks.find(x=>x.locationId==='a15ba9c9-aeca-41c3-8825-43a71a53ddd2');
assert.ok(saint&&saint.cpo==='Powerdot','Saint-Arnoult verified independently of Jarville');
assert.equal(saint.mappings.length,3,'two 50kW and one 22kW EVSE proven');
assert.deepEqual(saint.mappings.map(x=>x.powerKw).sort((a,b)=>a-b),[22,50,50]);
assert.ok(saint.mappings.every(x=>x.rateEurPerKwh===(x.powerKw===22?.49:.62)));
assert.ok(saint.mappings.every(x=>x.components.length===1&&x.components[0]==='ENERGY'),'Saint-Arnoult has no time or parking fee in source');
assert.ok(saint.screenshotSha256&&saint.manualEvidenceFile,'price proof traceable to uploaded screenshot');

assert.ok(src.includes("verified_app_tariff_link_invalid"),'mismatched source tariff ID must fail closed');
assert.ok(src.includes("verified_app_partial_attribution_pending"),'unverified sibling EVSE remains pending');
assert.ok(src.includes("if(!pricing)continue;"),'partially attributed locations only publish proven EVSEs');
assert.ok(src.includes("stats.publishedEvseIds+=assigned.size"),'no false count for unmatched EVSEs');
assert.ok(src.includes("tariffAttributionEvidence:manual?'user_electra_app_verified_per_power'"),'provenance for source-station pricing links is kept');

console.log('PASS: Electra power-disjoint EVSE tariffs, screenshot-backed partial attribution and fail-closed ambiguities');