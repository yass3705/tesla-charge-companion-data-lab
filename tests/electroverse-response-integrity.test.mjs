import assert from 'node:assert/strict';
import {completeLocation} from '../scripts/lib/electroverse_response_integrity.mjs';
const location={chargingLocationPk:'1',evses:{edges:[{node:{pk:'e',connectors:{edges:[{node:{pk:'c',priceComponents:null}}]}}}],pageInfo:{hasNextPage:false,endCursor:null}}};
const response={status:200,json:{data:{s0:location,s1:{...location,chargingLocationPk:'2'}}}};
assert.equal(completeLocation(response,'s0','1'),location);
assert.equal(completeLocation(response,'s0','1',{paged:true}),location);
assert.equal(completeLocation({...response,status:503},'s0','1'),null,'HTTP failure with data is never promoted');
assert.equal(completeLocation(response,'s0','other'),null,'no wrong-location tariff');
for(const errors of [[{message:'unscoped'}],[{path:['s0','evses'],message:'partial'}]])
  assert.equal(completeLocation({...response,json:{...response.json,errors}},'s0','1'),null);
assert.equal(completeLocation({...response,json:{...response.json,errors:[{path:['s1'],message:'other alias'}]}},'s0','1'),location,'good batch alias retained independently');
for(const mutate of [l=>l.evses.edges=null,l=>l.evses.edges[0].node.connectors.edges=null,
  l=>l.evses.edges.push(l.evses.edges[0]),l=>l.evses.edges[0].node.connectors.edges.push(l.evses.edges[0].node.connectors.edges[0]),
  l=>l.evses.pageInfo={},l=>l.evses.pageInfo={hasNextPage:true,endCursor:null}]){
  const bad=structuredClone(response);mutate(bad.json.data.s0);
  assert.equal(completeLocation(bad,'s0','1',{paged:true}),null);
}
const empty={status:200,json:{data:{s0:{chargingLocationPk:'1',evses:{edges:[]}}}}};
assert.ok(completeLocation(empty,'s0','1'),'technically complete zero EVSE response allowed');
console.log('Electroverse HTTP, partial GraphQL, exact source ID, nested shape and page contracts PASS');
