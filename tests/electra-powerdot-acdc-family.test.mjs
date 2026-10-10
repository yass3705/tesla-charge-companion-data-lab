import assert from 'node:assert/strict';
import fs from 'node:fs';
const src=fs.readFileSync('scripts/electra_france_platform_snapshot.mjs','utf8');
const a=src.indexOf('const PD_AC_DC_TARIFF_IDS=new Map('),b=src.indexOf('const first=await page(0)',a);
assert.ok(a>0&&b>a,'Powerdot AC/DC matching helper defined in snapshot builder');
const norm=x=>String(x||'').toUpperCase().replace(/[^A-Z0-9]/g,'');
const signature=p=>JSON.stringify(p);
const nationalKindsByEvse=new Map([['FRPDAC',new Set(['AC'])],['FRPDDC50',new Set(['DC'])],['FRPDDC200',new Set(['DC'])]]);
const nationalPowerByEvse=new Map([['FRPDAC',22],['FRPDDC50',50],['FRPDDC200',200]]);
const fn=new Function('norm','signature','nationalKindsByEvse','nationalPowerByEvse',
 src.slice(a,b)+';return matchPowerdotAcDcFamily;')(norm,signature,nationalKindsByEvse,nationalPowerByEvse);
const prices=[
 ['9d3380b6-bfef-4f52-a50e-11f72cff552c',0.49],
 ['6f46ce9f-5f71-4266-a07e-0e07231670d9',0.62],
 ['deb8f441-4306-4735-9990-3165dbeefffc',0.62]
];
const tariffs=prices.map(([chargeTariffId,price])=>({chargeTariffId,elements:[{restrictions:{},priceComponents:[{type:'ENERGY',price}]}]}));
const compiled=prices.map(([id,price])=>({type:'rules',rules:[{scope:'allDay',pricePerKwh:price,currency:'EUR'}]}));
const source={id:'test-powerdot',name:'Action - Test',evses:[
 {evseId:'FR*PD*AC',status:'AVAILABLE'},
 {evseId:'FR*PD*DC50',status:'OCCUPIED'},
 {evseId:'FR*PD*DC200',status:'AVAILABLE'}]};
const ids=source.evses.map(x=>x.evseId);
let result=fn(source,tariffs,compiled,ids,'exact_national_irve_evse');
assert.equal(result.assignments.size,3,'all exact EVSEs assigned, per connector kind');
assert.equal(result.assignments.get(norm(ids[0])).rules[0].pricePerKwh,0.49);
assert.equal(result.assignments.get(norm(ids[1])).rules[0].pricePerKwh,0.62);
assert.equal(result.assignments.get(norm(ids[2])).rules[0].pricePerKwh,0.62);
assert.equal(result.statusExcluded,0);
assert.equal(fn({...source,name:'Garage AUTO - Test'},tariffs,compiled,ids,'exact_national_irve_evse'),null,'garages not approved');
assert.equal(fn(source,tariffs,compiled,ids,'curated_irve_location'),null,'only exact EVSE matching');
assert.equal(fn(source,tariffs.map((t,i)=>i===1?{...t,elements:[{restrictions:{},priceComponents:[{type:'ENERGY',price:.61}]}]}:t),compiled,ids,'exact_national_irve_evse'),null,'changed tariff rate must fail closed');
assert.equal(fn(source,tariffs.map((t,i)=>i===1?{...t,elements:[{restrictions:{},priceComponents:[{type:'ENERGY',price:.62},{type:'TIME',price:1}]}]}:t),compiled,ids,'exact_national_irve_evse'),null,'unknown TIME/parking fee not ignored');
assert.equal(fn(source,tariffs.map((t,i)=>i===1?{...t,elements:[{restrictions:{minPower:100},priceComponents:[{type:'ENERGY',price:.62}]}]}:t),compiled,ids,'exact_national_irve_evse'),null,'no power restriction bypass');
assert.equal(fn(source,tariffs,[compiled[0],{type:'rules',rules:[{pricePerKwh:.62,connectionFee:2}]},compiled[2]],ids,'exact_national_irve_evse'),null,'two same-price tariffs with different fees are ambiguous');
nationalKindsByEvse.set('FRPDDC200',new Set(['AC','DC']));
assert.equal(fn(source,tariffs,compiled,ids,'exact_national_irve_evse'),null,'mixed-kind same EVSE is not assumed DC');
nationalKindsByEvse.set('FRPDDC200',new Set(['DC']));
result=fn({...source,evses:[source.evses[0],{...source.evses[1],status:'OUTOFORDER'},source.evses[2]]},tariffs,compiled,ids,'exact_national_irve_evse');
assert.equal(result.assignments.size,2,'out-of-order EVSE excluded from published tariff');
assert.equal(result.statusExcluded,1);
const fullClosed={...source,evses:source.evses.map(e=>({...e,status:'UNKNOWN'}))};
assert.equal(fn(fullClosed,tariffs,compiled,ids,'exact_national_irve_evse'),null,'all-unknown status location withheld');
console.log('PASS: Powerdot AC/DC exact EVSE mapping, 200 kW, tariff equivalence, restrictions, status and garage guards');
