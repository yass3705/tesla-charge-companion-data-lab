import test from 'node:test';
import assert from 'node:assert/strict';
import {connectorKind,homogeneousGpsGroups} from '../scripts/electroverse_uk_cpo_pilot.mjs';

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
