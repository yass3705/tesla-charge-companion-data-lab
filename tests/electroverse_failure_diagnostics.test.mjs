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

import {isRateLimited,rateLimitPlan,deferUnresolved} from '../scripts/lib/electroverse_rate_limit_guard.mjs';
test('HTTP 429 opens breaker and uses bounded Retry-After seconds',()=>{
 const r={status:429,responseHeaders:{retryAfter:'120'}};
 assert.equal(isRateLimited(r),true);
 const plan=rateLimitPlan(r,'batch',1000000000000);
 assert.equal(plan.backoffSeconds,120);
 assert.equal(Date.parse(plan.resumeNotBeforeUtc)-Date.parse(plan.detectedAtUtc),120000);
});
test('missing Retry-After enforces 15 minute cooldown and GraphQL throttling trips breaker',()=>{
 const r={status:200,json:{errors:[{extensions:{code:'RATE_LIMITED'},message:'PRIVATE'}]}};
 assert.equal(isRateLimited(r),true);
 const p=rateLimitPlan(r,'fallback',1000000000000);
 assert.equal(p.backoffSeconds,900);
 assert.ok(!JSON.stringify(p).includes('PRIVATE'));
});
test('unresolved preservation never skips or repeats a PK',()=>{
 const selected=['a','b','c','d'];
 assert.deepEqual(deferUnresolved(selected,new Set(['a']),[{pk:'c',error:'rate_limited'}]),['b','d']);
 assert.throws(()=>deferUnresolved(selected,new Set(['a']),[{pk:'a'}]),/invalid/);
 assert.throws(()=>deferUnresolved(selected,new Set(['a']),[{pk:'c'},{pk:'c'}]),/Duplicate/);
});
