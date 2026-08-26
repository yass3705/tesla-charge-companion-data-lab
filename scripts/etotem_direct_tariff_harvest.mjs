import fs from 'fs';
import zlib from 'zlib';

const INVENTORY='data/national/etotem_direct_stations_france.json.gz';
const OUTPUT='data/national/etotem_direct_tariffs_france.json.gz';
const API='https://www.e-totem.fr/api';
const CONCURRENCY=16;
const REQUEST_TIMEOUT_MS=4500;

function normId(v){return String(v||'').toUpperCase().replace(/[^A-Z0-9]/g,'');}
function htmlToText(v){
  let s=String(v||'');
  const entities={'&euro;':'€','&amp;':'&','&nbsp;':' ','&apos;':"'",'&quot;':'"','&agrave;':'à','&Agrave;':'À','&eacute;':'é','&Eacute;':'É','&ecirc;':'ê','&acirc;':'â','&ocirc;':'ô','&ucirc;':'û','&icirc;':'î','&ccedil;':'ç','&ugrave;':'ù','&rsquo;':"'"};
  for(let round=0;round<3;round++) s=s.replace(/&(euro|amp|nbsp|apos|quot|agrave|Agrave|eacute|Eacute|ecirc|acirc|ocirc|ucirc|icirc|ccedil|ugrave|rsquo);/g,m=>entities[m]||m).replace(/&#0*39;/g,"'").replace(/&#0*34;/g,'"').replace(/&#0*160;/g,' ').replace(/&#x0*27;/gi,"'").replace(/&#x0*a0;/gi,' ');
  return s.replace(/<br\s*\/?\s*>/gi,'\n').replace(/<\/p\s*>/gi,'\n').replace(/<[^>]+>/g,' ').replace(/\r/g,'').replace(/[ \t]+/g,' ').replace(/ *\n+ */g,'\n').trim();
}
function tariffSignature(text){return String(text||'').toLowerCase().replace(/\s+/g,' ').trim();}
function num(v){const n=Number(String(v).replace(',','.'));return Number.isFinite(n)?n:null;}
function parseHints(text){
  const t=String(text||''); const kwh=[],timeFees=[],grace=[],powerThresholds=[];
  for(const m of t.matchAll(/(\d+(?:[.,]\d+)?)\s*€\s*(?:\/|par)?\s*kwh/gi)){const n=num(m[1]);if(n!==null&&!kwh.includes(n))kwh.push(n);}
  for(const m of t.matchAll(/(\d+(?:[.,]\d+)?)\s*€\s*(?:\/|par\s+tranche(?:\s+entam[eé]e)?\s+de)?\s*(\d+)\s*min/gi)){const item={eur:num(m[1]),minutes:Number(m[2]),raw:m[0]};if(!timeFees.some(x=>x.eur===item.eur&&x.minutes===item.minutes))timeFees.push(item);}
  for(const m of t.matchAll(/(\d+)\s*(min|h(?:eure)?s?)\s+gratuite?s?/gi)){let minutes=Number(m[1]);if(/^h/i.test(m[2]))minutes*=60;if(!grace.includes(minutes))grace.push(minutes);}
  for(const m of t.matchAll(/(?:jusqu(?:'|’|\s)?(?:a|à)|au[- ]del[aà]|de|point de charge)\s*([^\n]{0,50}?)(\d+(?:[.,]\d+)?)\s*kw/gi)){const n=num(m[2]);if(n!==null&&!powerThresholds.includes(n))powerThresholds.push(n);}
  return {pricePerKwhCandidatesEur:kwh,timeFeeCandidates:timeFees,freeGraceMinutesCandidates:grace,powerThresholdCandidatesKw:powerThresholds};
}
function direct(e){return String(e?.bOcpi??0)==='0'&&String(e?.bGireve??0)==='0'&&String(e?.bItinerance??0)==='0';}
function distanceM(a,b){const R=6371000,r=Math.PI/180,dLat=(b.latitude-a.latitude)*r,dLon=(b.longitude-a.longitude)*r,la1=a.latitude*r,la2=b.latitude*r;const h=Math.sin(dLat/2)**2+Math.cos(la1)*Math.cos(la2)*Math.sin(dLon/2)**2;return 2*R*Math.asin(Math.sqrt(h));}
function findToken(v,depth=0){
  if(depth>5||v==null)return null;
  if(typeof v==='object'){
    for(const [k,x] of Object.entries(v))if(/token/i.test(k)&&typeof x==='string'&&x.length>=16)return x;
    for(const x of Object.values(v)){const t=findToken(x,depth+1);if(t)return t;}
  }
  return null;
}
async function fetchJson(url,options={},timeout=REQUEST_TIMEOUT_MS){
  const ctl=new AbortController();
  const timer=setTimeout(()=>ctl.abort(new Error('timeout')),timeout);
  try{
    const r=await fetch(url,{...options,signal:ctl.signal,headers:{Accept:'application/json','User-Agent':'Tesla-Charge-Companion/8 e-Totem direct tariff sync',...(options.headers||{})}});
    const text=await r.text();
    let json=null;try{json=JSON.parse(text);}catch{}
    return {ok:r.ok,status:r.status,json,text:text.slice(0,500)};
  }finally{clearTimeout(timer);}
}

if(!fs.existsSync(INVENTORY))throw new Error(`Missing ${INVENTORY}`);
const inv=JSON.parse(zlib.gunzipSync(fs.readFileSync(INVENTORY)).toString('utf8'));
const targets=(inv.stations||[]).map((s,i)=>({index:i,stationId:s.stationId,name:s.name,latitude:Number(s.latitude),longitude:Number(s.longitude),maxPowerKw:s.maxPowerKw,pdcCount:s.pdcCount,dataset:s.dataset?.title||null}));
console.log(`[e-Totem] inventory=${targets.length}`);

let token=null,bootstrapCount=0,requestCount=0,errorCount=0;
async function bootstrap(){
  const r=await fetchJson(`${API}/ConnexionAnonyme`,{method:'POST'},10000);
  bootstrapCount++;
  token=findToken(r.json);
  if(!r.ok||!token)throw new Error(`ConnexionAnonyme failed status=${r.status} token=${Boolean(token)} body=${r.text}`);
  console.log(`[e-Totem] ConnexionAnonyme OK status=${r.status}; token kept in memory only`);
}
await bootstrap();

async function stationQuery(t,delta,allowRefresh=true){
  const p=new URLSearchParams({fLatSudOuest:String(t.latitude-delta),fLongSudOuest:String(t.longitude-delta),fLatNordEst:String(t.latitude+delta),fLongNordEst:String(t.longitude+delta),bUniquementBornesDisponibles:'false',bCompatibleAutocharge:'0',nZoom:'18',bNePasClusteriser:'1',nBornesPrivees:'0',bRecupererBorneLaPlusProche:'0'});
  try{
    requestCount++;
    let r=await fetchJson(`${API}/Stations?${p}`,{headers:{Authorization:`Bearer ${token}`}});
    if(r.status===401&&allowRefresh){await bootstrap();requestCount++;r=await fetchJson(`${API}/Stations?${p}`,{headers:{Authorization:`Bearer ${token}`}});}
    if(!r.ok){errorCount++;return {elements:[],error:`http_${r.status}`};}
    return {elements:(Array.isArray(r.json?.aElements)?r.json.aElements:[]).filter(direct)};
  }catch(e){errorCount++;return {elements:[],error:String(e?.message||e)};}
}
async function resolveTarget(t){
  if(!Number.isFinite(t.latitude)||!Number.isFinite(t.longitude))return {index:t.index,resolved:false,error:'missing_coordinates'};
  const wanted=normId(t.stationId);
  for(const delta of [0.010,0.030]){
    const q=await stationQuery(t,delta);
    const exact=q.elements.find(e=>normId(e.sIdPool)===wanted);
    if(exact)return {index:t.index,resolved:true,matchMethod:'id',distanceM:0,element:exact};
    let nearest=null;
    for(const e of q.elements){const latitude=Number(e.fLatitude),longitude=Number(e.fLongitude);if(!Number.isFinite(latitude)||!Number.isFinite(longitude))continue;const d=distanceM(t,{latitude,longitude});if(!nearest||d<nearest.d)nearest={d,e};}
    if(nearest&&nearest.d<=120)return {index:t.index,resolved:true,matchMethod:'coordinates',distanceM:Math.round(nearest.d),element:nearest.e};
  }
  return {index:t.index,resolved:false};
}

const rawResults=new Array(targets.length);let next=0,done=0,resolvedLive=0;
async function worker(){
  while(true){
    const i=next++;if(i>=targets.length)return;
    const r=await resolveTarget(targets[i]);rawResults[i]=r;done++;if(r.resolved)resolvedLive++;
    if(done%50===0||done===targets.length)console.log(`[e-Totem] progress ${done}/${targets.length}; resolved=${resolvedLive}; requests=${requestCount}; errors=${errorCount}`);
  }
}
await Promise.all(Array.from({length:CONCURRENCY},()=>worker()));
token=null;

const stations=[];let exact=0,coordFallback=0,unresolved=0,withTariff=0;
for(const target of targets){
  const r=rawResults[target.index];
  if(!r?.resolved||!r.element||!direct(r.element)){unresolved++;stations.push({...target,resolved:false});continue;}
  if(r.matchMethod==='id')exact++;else coordFallback++;
  const match=r.element;
  const tariffHtml=String(match.sWebTexte||match.aBornes?.[0]?.sWebTextePool||match.aBornes?.[0]?.szWebTexte||'');
  const tariffText=htmlToText(tariffHtml),signature=tariffSignature(tariffText);if(tariffText)withTariff++;
  stations.push({...target,resolved:true,matchMethod:r.matchMethod,distanceM:r.distanceM??null,api:{sIdPool:match.sIdPool,sIdPoolUnique:match.sIdPoolUnique,sOrigine:match.sOrigine,sLibelle:match.sLibelle,sNomReseau:match.sNomReseau,sTypeBorne:match.sTypeBorne,bOcpi:match.bOcpi,bGireve:match.bGireve,bItinerance:match.bItinerance,nIdPool:match.nIdPool},tariffHtml,tariffText,tariffSignature:signature,tariffHints:parseHints(tariffText),apiPdc:(match.aBornes||[]).flatMap(b=>(b.aPdc||[]).map(p=>({nIdPdc:p.nIdPdc,nIdBorne:p.nIdBorne,nConnectorId:p.nConnectorId,status:p.szStatus,types:p.szTypePrises||[]})))});
}
const profileMap=new Map();
for(const s of stations.filter(s=>s.resolved&&s.tariffText)){if(!profileMap.has(s.tariffSignature))profileMap.set(s.tariffSignature,{count:0,text:s.tariffText,hints:s.tariffHints,exampleStations:[]});const p=profileMap.get(s.tariffSignature);p.count++;if(p.exampleStations.length<8)p.exampleStations.push({stationId:s.stationId,name:s.name,network:s.api?.sNomReseau,maxPowerKw:s.maxPowerKw});}
const profiles=[...profileMap.values()].sort((a,b)=>b.count-a.count);
const output={schemaVersion:'1.4.0',generatedAt:new Date().toISOString(),operator:'e-Totem',country:'FR',scope:{physicalCpoDirectOnly:true,roamingIncluded:false,source:'public anonymous e-Totem API: ConnexionAnonyme + authenticated /api/Stations joined to strict e-Totem IRVE inventory',nativeFilter:'bOcpi=0 AND bGireve=0 AND bItinerance=0',noGuessedFallback:true},harvest:{strategy:'direct Node API bootstrap + station-by-station bounded bbox',concurrency:CONCURRENCY,requestTimeoutMs:REQUEST_TIMEOUT_MS,bootstrapCount,requestCount,errorCount},counts:{inventoryStations:targets.length,resolvedStations:exact+coordFallback,exactIdMatches:exact,coordinateFallbackMatches:coordFallback,unresolvedStations:unresolved,resolvedWithTariffText:withTariff,uniqueTariffProfiles:profiles.length},tariffProfiles:profiles,stations};
fs.mkdirSync('data/national',{recursive:true});
fs.writeFileSync(OUTPUT,zlib.gzipSync(Buffer.from(JSON.stringify(output),'utf8'),{level:9}));
console.log(JSON.stringify({harvest:output.harvest,counts:output.counts},null,2));
console.log(JSON.stringify(profiles.slice(0,20).map((p,i)=>({rank:i+1,count:p.count,text:p.text.slice(0,700),hints:p.hints,examples:p.exampleStations.slice(0,3)})),null,2));