import test from 'node:test';
import assert from 'node:assert/strict';
import {createStatus429Recovery,Status429Exhausted,STATUS_429_PAUSES_SECONDS} from '../scripts/lib/electroverse_status_429_recovery.mjs';

const limited=(header=null)=>({status:429,
 responseHeaders:header==null?{}:{retryAfter:String(header)}});

function simulated(replies,{budget=480}={}){
 const sent=[],paused=[],events=[];
 const api=createStatus429Recovery({
  send:async(query,vars,options)=>{
   sent.push({query,vars,options});
   if(replies.length===0)throw Error('Unexpected request after scenario exhausted');
   return replies.shift();
  },
  pause:async ms=>paused.push(ms),
  onRateLimit:async event=>events.push(event),
  now:()=>Date.UTC(2026,10,22,17,0,0),
  maxSecondsPerStation:budget,
 });
 return {api,sent,paused,events};
}

for(const [n,replyCount,pauses] of [
 [1,1,[60000]],
 [2,2,[60000,120000]],
 [3,3,[60000,120000,300000]],
]){
 test('status 429 recovery succeeds after '+n+' consecutive refusal(s)',async()=>{
  const good={status:200,json:{data:{done:true}}};
  const t=simulated([...Array(replyCount)].map(()=>limited()).concat([good]));
  const result=await t.api.request('fixture-query',{pk:'300'},'status_single',['300']);
  assert.equal(result,good);
  assert.deepEqual(t.paused,pauses);
  assert.equal(t.sent.length,replyCount+1);
  assert.ok(t.sent.every(s=>s.query==='fixture-query'&&s.vars.pk==='300'&&s.options.attempts===1));
  assert.equal(t.api.stats().observed429,replyCount);
  assert.equal(t.api.stats().recoveredSeries,1);
  assert.equal(t.events.length,replyCount);
  assert.ok(t.events.every(e=>e.reason==='retry_scheduled'));
 });
}

test('fourth consecutive 429 stops, after exactly three waits totaling eight minutes',async()=>{
 const t=simulated([limited(),limited(),limited(),limited(),{status:200}]);
 await assert.rejects(()=>t.api.request('same-query',{pk:'p'},'status_batch',['p']),error=>{
  assert.ok(error instanceof Status429Exhausted);
  assert.equal(error.rateLimit.consecutive429,4);
  assert.equal(error.rateLimit.retriesUsed,3);
  assert.equal(error.rateLimit.stopReason,'fourth_consecutive_429');
  assert.equal(error.rateLimit.totalWaitSeconds,480);
  return true;
 });
 assert.deepEqual(t.paused,[60000,120000,300000]);
 assert.equal(t.sent.length,4);
 assert.equal(t.events.length,4);
 assert.equal(t.events.at(-1).reason,'fourth_consecutive_429');
 assert.equal(t.api.stats().totalWaitSeconds,480);
 assert.equal(t.api.stats().maxStationWaitSeconds,480);
 assert.equal(t.api.stats().budgetScope,'station_pk');
});

test('success resets the consecutive-429 sequence',async()=>{
 const t=simulated([limited(),{status:200},limited(),{status:200}]);
 assert.equal((await t.api.request('a',{},'status_batch',['A'])).status,200);
 assert.equal((await t.api.request('b',{},'status_single',['B'])).status,200);
 assert.deepEqual(t.paused,[60000,60000]);
 assert.equal(t.api.stats().recoveredSeries,2);
 assert.equal(t.api.stats().observed429,2);
});

test('explicit Retry-After longer than minute is respected within limit',async()=>{
 const t=simulated([limited('180'),{status:200}]);
 assert.equal((await t.api.request('q',{},'status_page',['Q'])).status,200);
 assert.deepEqual(t.paused,[180000]);
 assert.equal(t.events[0].retryAfterProvided,true);
});

test('large Retry-After refuses unsafe early retry and saves checkpoint event',async()=>{
 const t=simulated([limited('600'),{status:200}]);
 await assert.rejects(()=>t.api.request('q',{},'status_page',['Q']),error=>{
  assert.ok(error instanceof Status429Exhausted);
  assert.equal(error.rateLimit.stopReason,'retry_after_exceeds_single_wait_limit');
  return true;
 });
 assert.deepEqual(t.paused,[]);
 assert.equal(t.sent.length,1);
 assert.equal(t.events[0].reason,'retry_after_exceeds_single_wait_limit');
});

test('same station has cumulative wait limit across distinct calls',async()=>{
 const t=simulated([limited(),{status:200},limited(),{status:200}],{budget:60});
 assert.equal((await t.api.request('a',{},'status_batch',['A'])).status,200);
 await assert.rejects(()=>t.api.request('b',{},'status_batch',['A']),error=>{
  assert.equal(error.rateLimit.stopReason,'station_wait_budget_exhausted');
  return true;
 });
 assert.deepEqual(t.paused,[60000]);
 assert.equal(t.sent.length,3);
});

test('different stations keep independent 480s caps even across partitions',async()=>{
 const t=simulated([
  limited(),limited(),limited(),{status:200},
  limited(),{status:200},
 ]);
 assert.equal((await t.api.request('station-a',{},'status_single',['A'])).status,200);
 assert.equal(t.api.stationWaitSeconds('A'),480);
 assert.equal((await t.api.request('station-b',{},'status_single',['B'])).status,200);
 assert.equal(t.api.stationWaitSeconds('B'),60);
 assert.deepEqual(t.paused,[60000,120000,300000,60000]);
 assert.equal(t.api.stats().totalWaitSeconds,540,'Physical wait is only diagnostic; can exceed 480 across different PKs');
 assert.equal(t.api.stats().maxStationWaitSeconds,480);
});

test('paged requests consume the same station budget as a previously throttled batch',async()=>{
 const t=simulated([limited(),{status:200},limited(),{status:200},limited(),{status:200}]);
 await t.api.request('batch',{},'status_batch',['A','B']);
 await t.api.request('page',{},'status_page',['B']);
 await t.api.request('single',{},'status_single',['B']);
 assert.equal(t.api.stationWaitSeconds('A'),60);
 assert.equal(t.api.stationWaitSeconds('B'),180);
 assert.deepEqual(t.paused,[60000,60000,60000]);
 t.api.completeStations(['A']);
 assert.equal(t.api.stationWaitSeconds('A'),0);
 assert.equal(t.api.stationWaitSeconds('B'),180,'Clearing one PK must not reset another');
});

test('batch stops if any involved PK has already exhausted its own allowance',async()=>{
 const t=simulated([limited(),limited(),limited(),{status:200},limited(),{status:200}]);
 await t.api.request('a',{},'status_single',['A']);
 assert.equal(t.api.stationWaitSeconds('A'),480);
 await assert.rejects(()=>t.api.request('batch',{},'status_batch',['A','B']),error=>{
  assert.equal(error.rateLimit.stopReason,'station_wait_budget_exhausted');
  assert.equal(error.rateLimit.budgetScope,'station_pk');
  return true;
 });
 assert.deepEqual(t.paused,[60000,120000,300000]);
 assert.equal(t.api.stationWaitSeconds('B'),0);
});

test('station wait budget survives sweep-to-recovery subprocess handoff',async()=>{
 const initial=simulated([limited(),{status:200}]);
 await initial.api.request('a',{},'status_batch',['A','B']);
 assert.deepEqual(initial.api.snapshotStationBudgets(),{A:60,B:60});
 const next=simulated([limited(),{status:200}],{budget:60});
 next.api.restoreStationBudgets(initial.api.snapshotStationBudgets(),['A','B']);
 assert.equal(next.api.stationWaitSeconds('A'),60);
 await assert.rejects(()=>next.api.request('page',{},'status_page',['A']),error=>{
  assert.equal(error.rateLimit.stopReason,'station_wait_budget_exhausted');
  return true;
 });
 assert.deepEqual(next.paused,[]);
 next.api.completeStations(['B']);
 assert.deepEqual(next.api.snapshotStationBudgets(),{A:60});
});

test('tampered per-station checkpoint wait is refused',()=>{
 const next=simulated([{status:200}]);
 assert.throws(()=>next.api.restoreStationBudgets({'A':481},['A']),/Untrusted station budget/);
 assert.throws(()=>next.api.restoreStationBudgets({'other':60},['A']),/Untrusted station budget/);
 assert.throws(()=>next.api.restoreStationBudgets({'A':-1},['A']),/Untrusted station budget/);
});

test('GraphQL throttling on HTTP 200 uses the same safe retry sequence',async()=>{
 const graphite={status:200,json:{errors:[{extensions:{code:'THROTTLED'}}]}};
 const t=simulated([graphite,{status:200,json:{data:{ok:true}}}]);
 const result=await t.api.request('q',{},'status_batch',['Q']);
 assert.equal(result.json.data.ok,true);
 assert.deepEqual(t.paused,[60000]);
});

test('ordinary provider errors are not mistaken for a 429',async()=>{
 const r={status:500,json:null};
 const t=simulated([r]);
 assert.equal(await t.api.request('q',{},'status_batch',['Q']),r);
 assert.equal(t.sent.length,1);
 assert.deepEqual(t.paused,[]);
});

test('429 policy constants remain exact and immutable',()=>{
 assert.deepEqual(STATUS_429_PAUSES_SECONDS,[60,120,300]);
 assert.ok(Object.isFrozen(STATUS_429_PAUSES_SECONDS));
});
