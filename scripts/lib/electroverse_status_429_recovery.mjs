/**
 * Electroverse STATUS ONLY: bounded in-process recovery from HTTP / GraphQL 429.
 * Not used by tariff collection. No provider request bodies or secrets logged.
 *
 * A series permits exactly three delayed retries: 60s, 120s, 300s.
 * The fourth consecutive 429 stops immediately and leaves a checkpoint.
 * Respect a longer explicit Retry-After only within a bounded wait budget;
 * otherwise stop safely instead of issuing an early retry.
 */
import {isRateLimited, rateLimitPlan} from './electroverse_rate_limit_guard.mjs';

export const STATUS_429_PAUSES_SECONDS=Object.freeze([60,120,300]);
export const STATUS_429_MAX_TOTAL_WAIT_SECONDS=480;

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
 maxTotalWaitSeconds=STATUS_429_MAX_TOTAL_WAIT_SECONDS,
}){
 if(typeof send!=='function'||typeof pause!=='function'||typeof onRateLimit!=='function'||
    typeof now!=='function'||!Number.isFinite(maxTotalWaitSeconds)||maxTotalWaitSeconds<0)
  throw Error('Invalid Electroverse status 429 recovery configuration');
 let observed429=0, retriedRequests=0, recoveredSeries=0, totalWaitSeconds=0;
 const stats=()=>({policy:'60s_120s_300s_then_stop',
  observed429,retriedRequests,recoveredSeries,totalWaitSeconds,
  maxTotalWaitSeconds});
 async function request(query,variables,phase){
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
   const pauseIndex=consecutive429-1;
   const baseSeconds=STATUS_429_PAUSES_SECONDS[pauseIndex];
   const explicitSeconds=plan.retryAfterProvided?plan.backoffSeconds:0;
   const seconds=baseSeconds==null?null:Math.max(baseSeconds,explicitSeconds);
   const reason=baseSeconds==null?'fourth_consecutive_429':
    seconds>STATUS_429_PAUSES_SECONDS.at(-1)?'retry_after_exceeds_single_wait_limit':
    totalWaitSeconds+seconds>maxTotalWaitSeconds?'run_wait_budget_exhausted':null;
   const event={event:'STATUS_429',phase,consecutive429,
    retryAfterProvided:plan.retryAfterProvided,
    nextWaitSeconds:reason?null:seconds,
    reason:reason||'retry_scheduled',
    totalWaitSeconds, // elapsed waiting during this execution, not earlier runs
    resumeNotBeforeUtc:plan.resumeNotBeforeUtc};
   // Flush valid partition rows BEFORE any delay or terminal 429 decision.
   await onRateLimit(event);
   if(reason){
    throw new Status429Exhausted({...plan,
     policy:'60s_120s_300s_then_stop',stopReason:reason,
     consecutive429,retriesUsed:consecutive429-1,
     totalWaitSeconds,retryAfterProvided:plan.retryAfterProvided});
   }
   await pause(seconds*1000);
   totalWaitSeconds+=seconds;
   retriedRequests++;
  }
 }
 return {request,stats};
}
