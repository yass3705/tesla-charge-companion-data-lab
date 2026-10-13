import test from 'node:test';
import assert from 'node:assert/strict';
import {retainAllowed,boundedRequest} from '../scripts/electroverse_uk_national_details.mjs';

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

test('transient GraphQL failure gets one bounded retry',async()=>{
  let calls=0;
  const client={request:async()=>++calls===1
    ?{status:200,json:{errors:[{message:'An error occurred.'}]}}
    :{status:200,json:{data:{s0:{chargingLocationPk:'42'}}}}};
  const state={requests:0};
  const result=await boundedRequest(client,'query',{},state,0);
  assert.equal(result.s0.chargingLocationPk,'42');
  assert.equal(state.requests,2);
});

test('request cap fails closed',async()=>{
  const state={requests:30};
  await assert.rejects(boundedRequest({request:()=>{throw Error('unexpected network call');}},
    'query',{},state,0),/request cap exceeded/);
});
