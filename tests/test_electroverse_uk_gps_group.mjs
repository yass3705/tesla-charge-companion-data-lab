import test from 'node:test';
import assert from 'node:assert/strict';
import {connectorKind,homogeneousGpsGroups,tileHits} from '../scripts/electroverse_uk_cpo_pilot.mjs';

const vi=n=>{const out=[];do{let b=n&127;n=Math.floor(n/128);if(n)b|=128;out.push(b);}while(n);return out;};
const bytes=(key,payload)=>[...vi((key<<3)|2),...vi(payload.length),...payload];
const str=s=>[...new TextEncoder().encode(s)];

test('MVT point coordinates are discovery hints tied to their PK',()=>{
  const feature=[...bytes(2,[0,0]),...vi((3<<3)|0),1,...bytes(4,[9,...vi(4096),...vi(4096)])];
  const layer=[...bytes(1,str('hits')),...bytes(2,feature),...bytes(3,str('_id')),
    ...bytes(4,bytes(1,str('site-1'))),...vi((5<<3)|0),...vi(4096)];
  const hits=tileHits(new Uint8Array(bytes(3,layer)),10,512,512);
  assert.equal(hits.length,1);assert.equal(hits[0].pk,'site-1');
  assert.ok(Number.isFinite(hits[0].latitude));assert.ok(Number.isFinite(hits[0].longitude));
  assert.ok(Math.abs(hits[0].latitude)<0.3&&Math.abs(hits[0].longitude)<0.3);
});

const rate=value=>({__typename:'ConsumptionRate',formattedValue:`Consumption rate: £${value} kWh`});
function fixture(general='0.69',detail='0.69'){
  const cpo=new Map([['A',{evse_id:'GB*MFL*E1',status:'AVAILABLE',connectors:[
    {standard:'IEC_62196_T2_COMBO',max_electric_power:400000,tariff_ids:['21']}]}]]);
  const connector={pk:1,kilowatts:400,standard:{name:'IEC_62196_T2_COMBO'},
    priceComponents:[rate(general)],complexPricingDetail:{currency:'GBP',restrictions:[
      {restrictionTypes:[],priceComponents:[rate(detail)]}]}};
  const nearby=[{candidate:{pk:'site',distanceM:0},detail:{evses:{edges:[{node:{pk:2,
    physicalReference:'MFG-other-id',status:'AVAILABLE',connectors:{edges:[{node:connector}]}}}]}}}];
  return {cpo,nearby};
}

test('same GPS, power, count and consistent eMSP price yields only a group candidate',()=>{
  const {cpo,nearby}=fixture();const groups=homogeneousGpsGroups(cpo,nearby);
  assert.equal(groups.length,1);assert.equal(groups[0].exactIds,0);
  assert.equal(groups[0].candidateUniformPrice,true);
});

test('conflicting general and detailed prices block Source EV style group',()=>{
  const {cpo,nearby}=fixture('0.89','0.71');const group=homogeneousGpsGroups(cpo,nearby)[0];
  assert.equal(group.identicalElectroversePricing,true);
  assert.equal(group.priceLayersAgree,false);
  assert.equal(group.candidateUniformPrice,false);
});

test('two nearby eMSP sites at same power are ambiguous',()=>{
  const {cpo,nearby}=fixture();nearby.push(structuredClone(nearby[0]));
  nearby[1].candidate.pk='other-site';
  assert.deepEqual(homogeneousGpsGroups(cpo,nearby).map(x=>x.candidateUniformPrice),[false,false]);
});

test('only normal, Type 2 and CCS connectors enter the group',()=>{
  assert.equal(connectorKind('DOMESTIC_F'),'NORMAL');
  assert.equal(connectorKind('IEC_62196_T2'),'TYPE2');
  assert.equal(connectorKind('IEC_62196_T2_COMBO'),'CCS');
  for(const rejected of ['CHADEMO','IEC_62196_T1','IEC_62196_T1_COMBO','IEC_60309_2_THREE_32','TESLA_S'])
    assert.equal(connectorKind(rejected),null,rejected);
  const {cpo,nearby}=fixture();
  cpo.get('A').connectors.push({standard:'CHADEMO',max_electric_power:400000,tariff_ids:['other']});
  nearby[0].detail.evses.edges[0].node.connectors.edges.push({node:{pk:3,kilowatts:400,
    standard:{name:'CHADEMO'},priceComponents:[rate('0.01')]}});
  const groups=homogeneousGpsGroups(cpo,nearby);
  assert.equal(groups.length,1);
  assert.equal(groups[0].kind,'CCS');
  assert.equal(groups[0].candidateUniformPrice,true);
});
