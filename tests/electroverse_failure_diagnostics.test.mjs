import test from 'node:test';
import assert from 'node:assert/strict';
import {summarizeAttempt,boundedTrace} from '../scripts/lib/electroverse_failure_diagnostics.mjs';
test('rate limit metadata captured without response bodies or credentials',()=>{
 const r=summarizeAttempt({status:429,ms:123,bytes:87,text:'SECRET',error:'SECRET',
   json:{errors:[{message:'SECRET',extensions:{code:'RATE_LIMITED'}}]},
   responseHeaders:{retryAfter:'90',rateLimitRemaining:'0'}},
   {phase:'paged',attempt:2,page:1,complete:false});
 assert.equal(r.category,'rate_limited');assert.equal(r.responseHeaders.retryAfter,'90');
 assert.deepEqual(r.graphqlCodes,['RATE_LIMITED']);assert.ok(!JSON.stringify(r).includes('SECRET'));
});
test('200 partial GraphQL distinguished from invalid JSON',()=>{
 const base={status:200,json:{data:{chargingLocation:null},errors:[{message:'SECRET',extensions:{code:'INTERNAL'}}]}};
 const a=summarizeAttempt(base,{phase:'single',attempt:1,page:1,complete:false});
 const b=summarizeAttempt({status:200,json:null},{phase:'single',attempt:1,page:1,complete:false});
 assert.equal(a.category,'graphql_error_or_partial_data');assert.equal(b.category,'invalid_json');
 assert.ok(!JSON.stringify(a).includes('SECRET'));
});
test('network timeout scrubbed',()=>{
 const a=summarizeAttempt({status:0,error:'AbortError secret',ms:45000},{phase:'paged',attempt:1,page:1,complete:false});
 assert.equal(a.category,'timeout_or_abort');assert.ok(!JSON.stringify(a).includes('secret'));
});
test('trace truncation keeps first and final attempts',()=>{
 const r=boundedTrace(Array.from({length:90},(_,i)=>i+1),10);
 assert.equal(r.omitted,80);assert.deepEqual(r.attempts,[1,2,3,4,5,86,87,88,89,90]);
});
