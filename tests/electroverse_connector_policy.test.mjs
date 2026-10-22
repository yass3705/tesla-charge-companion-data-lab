import test from 'node:test';
import assert from 'node:assert/strict';
import {
  electroverseConnectorStandard,
  isSupportedElectroverseConnector,
  filterSupportedElectroverseConnectors,
} from '../scripts/lib/electroverse_connector_policy.mjs';

test('accept E/F, Type 2 and CCS Combo 2 from GraphQL standard objects', () => {
  const accepted=['DOMESTIC_E','DOMESTIC_F','SCHUKO','IEC_62196_T2','IEC_62196_T2_COMBO'];
  for (const name of accepted)
    assert.equal(isSupportedElectroverseConnector({standard:{name}}),true,name);
});

test('reject CHAdeMO, Type 1, CCS Combo 1, proprietary, and missing types', () => {
  const rejected=['CHADEMO','IEC_62196_T1','IEC_62196_T1_COMBO','TESLA','NACS',null,undefined,''];
  for (const name of rejected)
    assert.equal(isSupportedElectroverseConnector({standard:{name}}),false,String(name));
});

test('mixed-connector EVSE preserves supported plugs only and does not merge prices', () => {
  const t2={pk:'t2',standard:{name:'IEC_62196_T2'},kilowatts:22,priceComponents:[{formattedValue:'€0.39 kWh'}]};
  const chademo={pk:'cha',standard:{name:'CHADEMO'},kilowatts:50,priceComponents:[{formattedValue:'€0.59 kWh'}]};
  const ccs={pk:'ccs',standard:{name:'IEC_62196_T2_COMBO'},kilowatts:50,priceComponents:[{formattedValue:'€0.69 kWh'}]};
  assert.deepEqual(filterSupportedElectroverseConnectors([t2,chademo,ccs]),[t2,ccs]);
  assert.equal(filterSupportedElectroverseConnectors([chademo]).length,0);
});

test('normalize safe aliases without accepting other connector families', () => {
  assert.equal(electroverseConnectorStandard({standard:{name:'Type-2'}}),'TYPE_2');
  assert.equal(isSupportedElectroverseConnector({standard:'CCS2'}),true);
  assert.equal(isSupportedElectroverseConnector({standard:'CCS1'}),false);
});
