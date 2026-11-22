/**
 * Electroverse STATUS ONLY: per-station bounded HTTP / GraphQL 429 recovery.
 * Three waits on consecutive refusals: 60, 120, 300 seconds; fourth stops.
 *
 * Wait allowances belong to charging-location PKs (station identities), NOT
 * the workflow, partition, or collector subprocess. A batch 429 applies to
 * both station PKs in that request. Pagination and individual fallback reuse
 * the station budget until a verified station is committed.
 *
 * Retry-After is respected; if too long for any involved station, fail closed.
 * Never record credentials or response bodies.
 */
import {isRateLimited,rateLimitPlan} from './electroverse_rate_limit_guard.mjs';

export const STATUS_429_PAUSES_SECONDS=Object.freeze([60,120,300]);
export const STATUS_429_MAX_SECONDS_PER_STATION=480;

export class Status429Exhausted extends Error {
 constructor(detail){
  super('electroverse_status_rate_limit');
  this.name='Status429Exhausted';
  this.rateLimit=detail;
 }
}

export function createStatus429Recovery({
 send,
 pause,
 onRateLimit=async()=>{},
 now=()=>Date.now(),
 maxSecondsPerStation=STATUS_429_MAX_SECONDS_PER_STATION,
}){
 if(typeof send!=='function'||typeof pause!=='function'||typeof onRateLimit!=='function'||
    typeof now!=='function'||!Number.isFinite(maxSecondsPerStation)||maxSecondsPerStation<0)
  throw Error('Invalid Electroverse station 429 recovery configuration');

 const waitsByStation=new Map();
 let observed429=0,retriedRequests=0,recoveredSeries=0,totalWaitSeconds=0;
 let maxStationWaitSeconds=0;
 const recentEvents=[];
 const stats=()=>({
  policy:'60s_120s_300s_then_stop',
  budgetScope:'station_pk',
  observed429,retriedRequests,recoveredSeries,
  totalWaitSeconds, // diagnostic only: no global budget / stop check
  maxSecondsPerStation,maxStationWaitSeconds,
  trackedStationCount:waitsByStation.size,
  recentEvents:[...recentEvents],
 });
 function stationKeys(stationIds){
  if(!Array.isArray(stationIds)||!stationIds.length||
     stationIds.some(pk=>typeof pk!=='string'||!pk.trim())||
     new Set(stationIds).size!==stationIds.length)
   throw Error('Each status request must declare unique station PKs');
  return stationIds;
 }
 function stationWaitSeconds(pk){return waitsByStation.get(pk)||0;}
 // Keep budgets across sweep -> deferred recovery within the SAME GitHub run.
 // The pilot explicitly clears these ephemeral counters when starting a NEW run.
 function snapshotStationBudgets(){
  return Object.fromEntries([...waitsByStation.entries()].sort(([a],[b])=>a.localeCompare(b)));
 }
 function restoreStationBudgets(saved,allowedStationIds){
  if(saved==null)return;
  if(!saved||typeof saved!=='object'||Array.isArray(saved)||
     !Array.isArray(allowedStationIds))throw Error('Invalid saved station 429 budget');
  const allowed=new Set(allowedStationIds);
  for(const [pk,seconds] of Object.entries(saved)){
   if(!allowed.has(pk)||typeof seconds!=='number'||!Number.isInteger(seconds)||
      seconds<0||seconds>maxSecondsPerStation)throw Error('Untrusted station budget checkpoint');
   waitsByStation.set(pk,seconds);
   maxStationWaitSeconds=Math.max(maxStationWaitSeconds,seconds);
  }
 }
 // Only erase budgets after a verified station has been stored in the checkpoint.
 function completeStations(stationIds){
  for(const pk of stationKeys(stationIds))waitsByStation.delete(pk);
 }
 async function request(query,variables,phase,stationIds){
  const keys=stationKeys(stationIds);
  let consecutive429=0;
  while(true){
   const response=await send(query,variables,{attempts:1});
   if(!isRateLimited(response)){
    if(consecutive429)recoveredSeries++;
    return response;
   }
   observed429++;
   consecutive429++;
   const plan=rateLimitPlan(response,phase,now());
   const baseSeconds=STATUS_429_PAUSES_SECONDS[consecutive429-1];
   const explicitSeconds=plan.retryAfterProvided?plan.backoffSeconds:0;
   const seconds=baseSeconds==null?null:Math.max(baseSeconds,explicitSeconds);
   const priorStationWait=Math.max(...keys.map(stationWaitSeconds));
   const reason=baseSeconds==null?'fourth_consecutive_429':
    seconds>STATUS_429_PAUSES_SECONDS.at(-1)?'retry_after_exceeds_single_wait_limit':
    keys.some(pk=>stationWaitSeconds(pk)+seconds>maxSecondsPerStation)?
      'station_wait_budget_exhausted':null;
   const event={
    event:'STATUS_429',phase,consecutive429,
    stationCount:keys.length,
    retryAfterProvided:plan.retryAfterProvided,
    nextWaitSeconds:reason?null:seconds,
    reason:reason||'retry_scheduled',
    maxPriorStationWaitSeconds:priorStationWait,
    maxSecondsPerStation,
    totalWaitSeconds, // only metrics; never gates another station
    retryAtUtc:reason?null:new Date(now()+seconds*1000).toISOString(),
    providerResumeNotBeforeUtc:plan.retryAfterProvided?plan.resumeNotBeforeUtc:null,
   };
   recentEvents.push(event);
   if(recentEvents.length>16)recentEvents.shift();
   // Preserve all verified rows BEFORE every wait and terminal refusal.
   await onRateLimit(event);
   if(reason){
    throw new Status429Exhausted({
     ...plan,policy:'60s_120s_300s_then_stop',budgetScope:'station_pk',
     stopReason:reason,consecutive429,retriesUsed:consecutive429-1,
     maxSecondsPerStation,maxPriorStationWaitSeconds:priorStationWait,
     totalWaitSeconds,retryAfterProvided:plan.retryAfterProvided,
    });
   }
   await pause(seconds*1000);
   totalWaitSeconds+=seconds;
   for(const pk of keys){
    const used=stationWaitSeconds(pk)+seconds;
    waitsByStation.set(pk,used);
    maxStationWaitSeconds=Math.max(maxStationWaitSeconds,used);
   }
   retriedRequests++;
  }
 }
 return {request,completeStations,stationWaitSeconds,snapshotStationBudgets,restoreStationBudgets,stats};
}
