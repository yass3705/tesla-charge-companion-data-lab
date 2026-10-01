#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import zlib from 'node:zlib';

const args = Object.fromEntries(process.argv.slice(2).map((v,i,a)=>v.startsWith('--')?[v.slice(2), a[i+1] && !a[i+1].startsWith('--') ? a[i+1] : true]:null).filter(Boolean));
const tenant = String(args.tenant || process.env.LOADMOTION_TENANT || '').trim().toLowerCase();
const token = String(process.env.LOADMOTION_TOKEN || '').trim();
const out = String(args.out || `data/loadmotion/france/current/${tenant}.json.gz`);
const concurrency = Math.max(1, Math.min(6, Number(args.concurrency || 4)));
if (!tenant || !token) throw new Error('Usage: LOADMOTION_TOKEN=... node extract_loadmotion_france.mjs --tenant <yes55|loadstations|reveo|mobisdec> [--out path]');

const CONFIG = {
  yes55: {host:'yes55.load-motion.com', inventory:'search', search:'Y55', accept:s=>String(s?.id||'').toUpperCase().startsWith('FR*Y55*')},
  loadstations: {host:'loadstations.load-motion.com', inventory:'search', search:'LST', accept:s=>String(s?.id||'').toUpperCase().startsWith('FR*LST*')},
  reveo: {host:'app.reveocharge.com', inventory:'issuer', accept:()=>true},
  mobisdec: {host:'mobisdec.load-motion.com', inventory:'issuer', accept:()=>true},
};
const cfg = CONFIG[tenant];
if (!cfg) throw new Error(`Unsupported tenant: ${tenant}`);
const base = `https://${cfg.host}`;

function decodeJwtPayload(jwt){
  const parts=jwt.split('.');
  if(parts.length!==3) throw new Error('LOADMOTION_TOKEN is not a JWT');
  const b64=parts[1].replace(/-/g,'+').replace(/_/g,'/').padEnd(Math.ceil(parts[1].length/4)*4,'=');
  return JSON.parse(Buffer.from(b64,'base64').toString('utf8'));
}
const payload=decodeJwtPayload(token);
const userId=payload.id;
if(!userId) throw new Error('JWT payload does not contain id');

const sleep=ms=>new Promise(r=>setTimeout(r,ms));
async function api(urlPath,retry=0){
  try{
    const response=await fetch(base+urlPath,{headers:{Authorization:`Bearer ${token}`,Accept:'application/json'}});
    if((response.status===429||response.status>=500)&&retry<4){
      await sleep(1000*Math.pow(2,retry));
      return api(urlPath,retry+1);
    }
    const txt=await response.text();
    let body; try{body=JSON.parse(txt);}catch{body=txt;}
    return {ok:response.ok,status:response.status,body};
  }catch(error){
    if(retry<4){
      await sleep(1000*Math.pow(2,retry));
      return api(urlPath,retry+1);
    }
    return {ok:false,status:0,body:{networkError:String(error?.message||error)}};
  }
}
function connectorId(c){return c?.connectorId??c?.connectorID??c?.id??c?.number??1;}
function defs(body){return Array.isArray(body)?body:(Array.isArray(body?.pricingDefinitions)?body.pricingDefinitions:[]);}
function noTariff(d){return String(d?.name||'').trim().toLowerCase()==='no tariff';}
async function classifyEmptyMatching(stationId,cid){
  const q=new URLSearchParams({ChargingStationID:stationId,ConnectorID:String(cid),UserID:userId});
  const model=await api(`/v1/api/pricing-model/resolve?${q}`);
  const modelDefs=defs(model.body);
  const explicitNoTariff=modelDefs.filter(noTariff);
  if(model.ok&&explicitNoTariff.length)return {kind:'fallback',http:model.status,definitions:explicitNoTariff.map(sanitizeDefinition),modelStatus:model.status};
  if(model.status===404)return {kind:'pricing404',http:model.status,definitions:[],modelStatus:model.status};
  if(model.ok)return {kind:'empty',http:model.status,definitions:[],modelStatus:model.status};
  return {kind:'error',http:model.status,definitions:[],modelStatus:model.status};
}
function sanitizeDefinition(d){
  return {
    id:d?.id??null, issuer:d?.issuer??null, entityType:d?.entityType??null, name:d?.name??null, description:d?.description??null,
    staticRestrictions:d?.staticRestrictions??null, restrictions:d?.restrictions??null, dimensions:d?.dimensions??null,
    ocpiData:d?.ocpiData?{id:d.ocpiData.id??null,tariff_alt_text:d.ocpiData.tariff_alt_text??null,currency:d.ocpiData.currency??null,elements:d.ocpiData.elements??null,last_updated:d.ocpiData.last_updated??null}:null,
    numberOfSubscriptions:d?.numberOfSubscriptions??null
  };
}
function stationMeta(s,cid){return {station:s.id,alias:s.alias??null,site:s.site?.name??s.siteName??s.siteID??null,siteArea:s.siteArea?.name??s.siteAreaName??s.siteAreaID??null,connector:cid};}

async function inventory(){
  const rows=[], seen=new Set(), limit=100;
  for(let page=0;page<200;page++){
    const skip=page*limit;
    const q=cfg.inventory==='issuer'
      ? `Issuer=true&WithSite=true&WithSiteArea=true&Limit=${limit}&Skip=${skip}`
      : `Search=${encodeURIComponent(cfg.search)}&WithSite=true&WithSiteArea=true&Limit=${limit}&Skip=${skip}`;
    const r=await api(`/v1/api/charging-stations?${q}`);
    if(!r.ok) throw new Error(`inventory HTTP ${r.status} tenant=${tenant} page=${page+1}`);
    const batch=r.body?.result||[];
    let added=0;
    for(const s of batch){if(cfg.accept(s)&&!seen.has(s.id)){seen.add(s.id);rows.push(s);added++;}}
    console.log(`inventory ${tenant} page=${page+1} received=${batch.length} acceptedTotal=${rows.length} new=${added}`);
    if(!batch.length||batch.length<limit) break;
    if(added===0&&cfg.inventory==='issuer') break;
  }
  return rows;
}

const stations=await inventory();
const tasks=[];
for(const station of stations){
  const cs=station.connectors?.length?station.connectors:[{connectorId:1}];
  const ids=[...new Set(cs.map(connectorId))];
  for(const cid of ids) tasks.push({station,cid});
}
const priced=[],fallback=[],empty=[],errors=[];
let cursor=0,done=0;
async function work(){
  while(true){
    const i=cursor++; if(i>=tasks.length)return;
    const {station,cid}=tasks[i];
    const q=new URLSearchParams({ChargingStationID:station.id,ConnectorID:String(cid),UserID:userId});
    const r=await api(`/v1/api/matching-pricing-definitions/resolve?${q}`);
    const all=defs(r.body), real=all.filter(d=>!noTariff(d));
    const meta=stationMeta(station,cid);
    if(!r.ok) errors.push({...meta,http:r.status});
    else if(real.length) priced.push({...meta,http:r.status,definitions:real.map(sanitizeDefinition)});
    else if(all.length) fallback.push({...meta,http:r.status,definitions:all.map(sanitizeDefinition)});
    else empty.push({...meta,http:r.status});
    done++; if(done%100===0||done===tasks.length)console.log(`pass1 ${tenant} ${done}/${tasks.length} priced=${priced.length} fallback=${fallback.length} empty=${empty.length} errors=${errors.length}`);
    await sleep(100);
  }
}
await Promise.all(Array.from({length:concurrency},()=>work()));

const recovered=[],persistent=[];
for(let i=0;i<errors.length;i++){
  const e=errors[i]; await sleep(350);
  const stationCheck=await api(`/v1/api/charging-stations/${encodeURIComponent(e.station)}`);
  if(stationCheck.status===404){
    persistent.push({...e,classification:'station404',stationHttp:404});
    continue;
  }
  const q=new URLSearchParams({ChargingStationID:e.station,ConnectorID:String(e.connector),UserID:userId});
  const r=await api(`/v1/api/matching-pricing-definitions/resolve?${q}`);
  const all=defs(r.body), real=all.filter(d=>!noTariff(d));
  if(r.ok&&real.length) recovered.push({...e,http:r.status,definitions:real.map(sanitizeDefinition)});
  else if(r.ok&&all.length) fallback.push({...e,http:r.status,definitions:all.map(sanitizeDefinition),recoveredClassification:true});
  else if(r.ok){
    const classified=await classifyEmptyMatching(e.station,e.connector);
    if(classified.kind==='fallback') fallback.push({...e,http:r.status,definitions:classified.definitions,modelStatus:classified.modelStatus,recoveredClassification:true});
    else if(classified.kind==='empty') empty.push({...e,http:r.status,modelStatus:classified.modelStatus,recoveredClassification:true});
    else persistent.push({...e,secondHttp:r.status,modelStatus:classified.modelStatus,classification:classified.kind});
  } else {
    persistent.push({...e,secondHttp:r.status,secondDefinitions:all.map(sanitizeDefinition)});
  }
  if((i+1)%50===0||i+1===errors.length)console.log(`pass2 ${tenant} ${i+1}/${errors.length} recovered=${recovered.length} fallback=${fallback.length} empty=${empty.length} persistent=${persistent.length}`);
}
const output={
  schemaVersion:1, generatedAt:new Date().toISOString(), network:tenant, tenant, host:cfg.host,
  inventoryMethod:cfg.inventory==='issuer'?'Issuer=true':`Search=${cfg.search} + strict prefix filter`,
  summary:{stations:stations.length,connecteursTestes:tasks.length,tarifs:priced.length+recovered.length,recoveredPass2:recovered.length,noTariff:fallback.length,empty:empty.length,erreursPersistantes:persistent.length},
  tarifs:[...priced,...recovered], noTariff:fallback, empty, erreursPersistantes:persistent
};
fs.mkdirSync(path.dirname(out),{recursive:true});
const buf=Buffer.from(JSON.stringify(output));
if(out.endsWith('.gz')) fs.writeFileSync(out,zlib.gzipSync(buf,{level:9})); else fs.writeFileSync(out,buf);
console.log(JSON.stringify(output.summary,null,2));
console.log(`wrote ${out}`);