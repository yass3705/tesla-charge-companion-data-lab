import test from 'node:test';
import assert from 'node:assert/strict';
import {retainAllowed} from '../scripts/electroverse_uk_national_details.mjs';

test('source detail retains only normal, Type 2 and CCS connectors',()=>{
  const loc={chargingLocationPk:'42',evses:{pageInfo:{hasNextPage:true,endCursor:'next-page'},edges:[
    {node:{pk:'evse',physicalReference:'GB*ABC*1',status:'AVAILABLE',
      connectors:{edges:[
        {node:{standard:{name:'IEC_62196_T2'},kilowatts:22}},
        {node:{standard:{name:'CHADEMO'},kilowatts:50}},
        {node:{standard:{name:'IEC_62196_T2_COMBO'},kilowatts:50}},
      ]}}}
  ]}};
  const result=retainAllowed(loc);
  assert.equal(result.evses.length,1);
  assert.deepEqual(result.evses[0].connectors.map(x=>x.standard.name),
    ['IEC_62196_T2','IEC_62196_T2_COMBO']);
  assert.equal(result.hasMoreEvses,true);
  assert.equal(result.endCursor,'next-page');
});
