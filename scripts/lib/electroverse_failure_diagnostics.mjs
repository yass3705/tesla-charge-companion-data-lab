// Electroverse failure-only telemetry. Never persist raw provider bodies, URLs, GraphQL messages or credentials.
const safeHeader = v => typeof v === 'string' && /^[a-zA-Z0-9.,:; \-]{1,80}$/.test(v) ? v : null;
const safeCode = v => typeof v === 'string' && /^[A-Z_][A-Z_0-9]{0,47}$/.test(v) ? v : null;
function classifyError(e) {
  const text=typeof e==='string'?e.toLowerCase():'';
  if (/abort|timeout|timed out/.test(text)) return 'timeout_or_abort';
  if (/dns|enotfound|eai_again/.test(text)) return 'dns';
  return text ? 'network_or_client_error' : null;
}
export function summarizeAttempt(r,{phase,attempt,page,complete}) {
  const status=Number.isInteger(r?.status)?r.status:null;
  const errors=Array.isArray(r?.json?.errors)?r.json.errors:[];
  let category=complete?'complete':'incomplete_location';
  if(!complete) {
    if(status===0)category=classifyError(r?.error)||'transport_unknown';
    else if(status===401||status===403)category='authentication_or_access';
    else if(status===429)category='rate_limited';
    else if(status>=500)category='provider_server_error';
    else if(status<200||status>=300)category='http_error';
    else if(!r?.json)category='invalid_json';
    else if(errors.length)category='graphql_error_or_partial_data';
  }
  const h=r?.responseHeaders||{};
  return {phase,attempt,page,category,httpStatus:status,
    elapsedMs:Number.isFinite(r?.ms)?r.ms:null,responseBytes:Number.isFinite(r?.bytes)?r.bytes:null,
    jsonParsed:!!r?.json,hasData:!!r?.json?.data,graphqlErrorCount:errors.length,
    graphqlCodes:[...new Set(errors.map(e=>safeCode(e?.extensions?.code)).filter(Boolean))].slice(0,12),
    responseHeaders:{retryAfter:safeHeader(h.retryAfter),rateLimitLimit:safeHeader(h.rateLimitLimit),
      rateLimitRemaining:safeHeader(h.rateLimitRemaining),rateLimitReset:safeHeader(h.rateLimitReset)},
    networkErrorClass:status===0?classifyError(r?.error):null};
}
export function boundedTrace(attempts,limit=40) {
  if(!Array.isArray(attempts)||!Number.isInteger(limit)||limit<4)throw Error('Invalid trace');
  if(attempts.length<=limit)return {attemptCount:attempts.length,attempts,omitted:0};
  const first=Math.min(5,Math.floor(limit/2));
  return {attemptCount:attempts.length,attempts:[...attempts.slice(0,first),...attempts.slice(-(limit-first))],omitted:attempts.length-limit};
}
