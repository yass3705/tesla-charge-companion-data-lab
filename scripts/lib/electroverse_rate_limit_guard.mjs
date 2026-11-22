// Fail closed immediately at HTTP or GraphQL throttling; never expose response bodies.
const RATE_CODES=new Set(['RATE_LIMITED','TOO_MANY_REQUESTS','THROTTLED','RESOURCE_EXHAUSTED']);
export function isRateLimited(r){
  return r?.status===429||(Array.isArray(r?.json?.errors)&&
    r.json.errors.some(e=>RATE_CODES.has(String(e?.extensions?.code||'').toUpperCase())));
}
export function rateLimitPlan(r,phase,now=Date.now()){
  if(!isRateLimited(r))throw Error('Rate-limit plan requires a throttled response');
  const raw=r?.responseHeaders?.retryAfter;
  let seconds=null;
  if(typeof raw==='string'&&/^\d{1,8}$/.test(raw))seconds=Number(raw);
  else if(typeof raw==='string'){
    const timestamp=Date.parse(raw);
    if(Number.isFinite(timestamp))seconds=Math.ceil((timestamp-now)/1000);
  }
  const headerPresent=seconds!=null&&Number.isFinite(seconds)&&seconds>0;
  // Unknown provider budget: 15 minute minimum without an explicit usable header.
  const backoffSeconds=headerPresent?Math.max(60,Math.min(3600,Math.ceil(seconds))):900;
  return {phase,detectedAtUtc:new Date(now).toISOString(),httpStatus:r?.status??null,
    retryAfterProvided:headerPresent,backoffSeconds,resumeNotBeforeUtc:new Date(now+backoffSeconds*1000).toISOString()};
}
export function deferUnresolved(selected,successful,failures){
  const uniq=new Set(selected),seen=new Set();
  if(uniq.size!==selected.length)throw Error('Duplicate selected PK');
  if(!(successful instanceof Set))throw Error('Missing success identities');
  for(const pk of successful)if(!uniq.has(pk))throw Error('Success outside selection');
  for(const row of failures){
    if(!row||!uniq.has(row.pk)||seen.has(row.pk)||successful.has(row.pk))throw Error('Duplicate or invalid pending PK');
    seen.add(row.pk);
  }
  return selected.filter(pk=>!successful.has(pk)&&!seen.has(pk));
}
