import fs from 'fs';
import zlib from 'zlib';
import { chromium } from 'playwright-core';

const INVENTORY='data/national/etotem_direct_stations_france.json.gz';
const OUTPUT='data/national/etotem_direct_tariffs_france.json.gz';
const HOME='https://www.e-totem.fr/';
const CONCURRENCY=3;
const MATCH_RADIUS_M=150;

function normId(v){return String(v||'').toUpperCase().replace(/[^A-Z0-9]/g,'');}
function normText(v){return String(v||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9]+/g,' ').replace(/\s+/g,' ').trim();}
function direct(e){return String(e?.bOcpi??0)==='0'&&String(e?.bGireve??0)==='0'&&String(e?.bItinerance??0)==='0';}
function distanceM(a,b){const R=6371000,r=Math.PI/180,dLat=(b.lat-a.lat)*r,dLon=(b.lon-a.lon)*r,la1=a.lat*r,la2=b.lat*r;const h=Math.sin(dLat/2)**2+Math.cos(la1)*Math.cos(la2)*Math.sin(dLon/2)**2;return 2*R*Math.asin(Math.sqrt(h));}
function htmlToText(v){let s=String(v||'');const entities={'&euro;':'€','&amp;':'&','&nbsp;':' ','&apos;':"'",'&quot;':'"','&agrave;':'à','&Agrave;':'À','&eacute;':'é','&Eacute;':'É','&ecirc;':'ê','&acirc;':'â','&ocirc;':'ô','&ucirc;':'û','&icirc;':'î','&ccedil;':'ç','&ugrave;':'ù','&rsquo;':"'"};for(let round=0;round<3;round++)s=s.replace(/&(euro|amp|nbsp|apos|quot|agrave|Agrave|eacute|Eacute|ecirc|acirc|ocirc|ucirc|icirc|ccedil|ugrave|rsquo);/g,m=>entities[m]||m).replace(/&#0*39;/g,"'").replace(/&#0*34;/g,'"').replace(/&#0*160;/g,' ').replace(/&#x0*27;/gi,"'").replace(/&#x0*a0;/gi,' ');return s.replace(/<br\s*\/?\s*>/gi,'\n').replace(/<\/p\s*>/gi,'\n').replace(/<[^>]+>/g,' ').replace(/\r/g,'').replace(/[ \t]+/g,' ').replace(/ *\n+ */g,'\n').trim();}
function tariffSignature(text){return String(text||'').toLowerCase().replace(/\s+/g,' ').trim();}
function num(v){const n=Number(String(v).replace(',','.'));return Number.isFinite(n)?n:null;}
function parseHints(text){const t=String(text||''),kwh=[],timeFees=[],grace=[],powerThresholds=[];for(const m of t.matchAll(/(\d+(?:[.,]\d+)?)\s*€\s*(?:\/|par)?\s*kwh/gi)){const n=num(m[1]);if(n!==null&&!kwh.includes(n))kwh.push(n);}for(const m of t.matchAll(/(\d+(?:[.,]\d+)?)\s*€\s*(?:\/|par\s+tranche(?:\s+entam[eé]e)?\s+de)?\s*(\d+)\s*min/gi)){const item={eur:num(m[1]),minutes:Number(m[2]),raw:m[0]};if(!timeFees.some(x=>x.eur===item.eur&&x.minutes===item.minutes))timeFees.push(item);}for(const m of t.matchAll(/(\d+)\s*(min|h(?:eure)?s?)\s+gratuite?s?/gi)){let minutes=Number(m[1]);if(/^h/i.test(m[2]))minutes*=60;if(!grace.includes(minutes))grace.push(minutes);}for(const m of t.matchAll(/(?:jusqu(?:'|’|\s)?(?:a|à)|au[- ]del[aà]|de|point de charge)\s*([^\n]{0,50}?)(\d+(?:[.,]\d+)?)\s*kw/gi)){const n=num(m[2]);if(n!==null&&!powerThresholds.includes(n))powerThresholds.push(n);}return {pricePerKwhCandidatesEur:kwh,timeFeeCandidates:timeFees,freeGraceMinutesCandidates:grace,powerThresholdCandidatesKw:powerThresholds};}
function searchVariants(t){
  const values=[];
  const add=v=>{v=String(v||'').trim();if(v.length>=3&&!values.some(x=>normText(x)===normText(v)))values.push(v.slice(0,120));};
  add(t.name);
  add(String(t.name||'').replace(/^\s*e[ -]?totem\s*[-–—:]?\s*/i,''));
  const parts=String(t.name||'').split(/\s[-–—:]\s/).map(x=>x.trim()).filter(Boolean);if(parts.length>1)add(parts.at(-1));
  add(t.brandName);
  add(t.stationIdLocal);
  add(t.stationId);
  return values.slice(0,5);
}
function matchCandidate(target,elements){
  const native=(elements||[]).filter(direct),wanted=new Set([normId(target.stationId),normId(target.stationIdLocal)].filter(Boolean));
  for(const e of native){if(wanted.has(normId(e?.sIdPool))||wanted.has(normId(e?.sIdPoolUnique)))return {element:e,matchMethod:'id',distanceM:0};}
  if(Number.isFinite(target.latitude)&&Number.isFinite(target.longitude)){
    let nearest=null;
    for(const e of native){const lat=Number(e?.fLatitude),lon=Number(e?.fLongitude);if(!Number.isFinite(lat)||!Number.isFinite(lon))continue;const d=distanceM({lat:target.latitude,lon:target.longitude},{lat,lon});if(d<=MATCH_RADIUS_M&&(!nearest||d<nearest.distanceM))nearest={element:e,matchMethod:'coordinates',distanceM:Math.round(d)};}
    if(nearest)return nearest;
  }
  return null;
}

if(!fs.existsSync(INVENTORY))throw new Error(`Missing ${INVENTORY}`);
const inv=JSON.parse(zlib.gunzipSync(fs.readFileSync(INVENTORY)).toString('utf8'));
const targets=(inv.stations||[]).map((s,index)=>({index,stationId:s.stationId,stationIdLocal:s.stationIdLocal,name:s.name,brandName:s.brandName,developerName:s.developerName,address:s.address,latitude:Number(s.latitude),longitude:Number(s.longitude),maxPowerKw:s.maxPowerKw,pdcCount:s.pdcCount,dataset:s.dataset?.title||null}));
console.log(`[e-Totem] inventory=${targets.length}; strategy=public station search index; concurrency=${CONCURRENCY}`);

const browser=await chromium.launch({headless:true,executablePath:'/usr/bin/google-chrome',args:['--no-sandbox']});
const page=await browser.newPage({locale:'fr-FR',viewport:{width:1280,height:900}});
await page.goto(HOME,{waitUntil:'domcontentloaded',timeout:60000});

const sentry=await page.evaluate(async()=>{const ctl=new AbortController(),timer=setTimeout(()=>ctl.abort(),15000);try{const p=new URLSearchParams({sLibelleBorne:'INTERMARCHE MANE',bUniquementBornesDisponibles:'false',bNePasClusteriser:'1',nBornesPrivees:'0'});const r=await fetch('/api/Stations?'+p.toString(),{credentials:'include',cache:'no-store',signal:ctl.signal});const j=await r.json();const a=Array.isArray(j?.aElements)?j.aElements:[],m=a.find(e=>String(e?.sIdPool||'').toUpperCase().replace(/[^A-Z0-9]/g,'')==='FRETIP31315A');return {status:r.status,count:a.length,mane:!!m,direct:!!m&&String(m?.bOcpi??0)==='0'&&String(m?.bGireve??0)==='0'&&String(m?.bItinerance??0)==='0',tariff:!!String(m?.sWebTexte||'').trim()};}finally{clearTimeout(timer);}});
if(sentry.status!==200||!sentry.mane||!sentry.direct||!sentry.tariff){await browser.close();throw new Error(`Search-index Mane sentry failed: ${JSON.stringify(sentry)}`);}
console.log(`[e-Totem] search-index Mane sentry OK status=${sentry.status} count=${sentry.count} tariff=true`);

const payload=targets.map(t=>({...t,variants:searchVariants(t)}));
const harvest=await page.evaluate(async ({targets,concurrency,matchRadius})=>{
  const normId=v=>String(v||'').toUpperCase().replace(/[^A-Z0-9]/g,'');
  const direct=e=>String(e?.bOcpi??0)==='0'&&String(e?.bGireve??0)==='0'&&String(e?.bItinerance??0)==='0';
  const dist=(a,b)=>{const R=6371000,r=Math.PI/180,dLat=(b.lat-a.lat)*r,dLon=(b.lon-a.lon)*r,la1=a.lat*r,la2=b.lat*r;const h=Math.sin(dLat/2)**2+Math.cos(la1)*Math.cos(la2)*Math.sin(dLon/2)**2;return 2*R*Math.asin(Math.sqrt(h));};
  const sleep=ms=>new Promise(r=>setTimeout(r,ms));
  let requestCount=0,errorCount=0,retryCount=0,detailCount=0;
  async function getJson(url,attempt=0){const ctl=new AbortController(),timer=setTimeout(()=>ctl.abort(),12000);try{requestCount++;const r=await fetch(url,{credentials:'include',cache:'no-store',signal:ctl.signal});const text=await r.text();if(!r.ok)throw new Error(`http_${r.status}`);return JSON.parse(text);}catch(e){if(attempt<1){retryCount++;await sleep(500);return getJson(url,attempt+1);}errorCount++;return null;}finally{clearTimeout(timer);}}
  function match(t,elements){const native=(elements||[]).filter(direct),wanted=new Set([normId(t.stationId),normId(t.stationIdLocal)].filter(Boolean));for(const e of native){if(wanted.has(normId(e?.sIdPool))||wanted.has(normId(e?.sIdPoolUnique)))return {element:e,matchMethod:'id',distanceM:0};}if(Number.isFinite(t.latitude)&&Number.isFinite(t.longitude)){let nearest=null;for(const e of native){const lat=Number(e?.fLatitude),lon=Number(e?.fLongitude);if(!Number.isFinite(lat)||!Number.isFinite(lon))continue;const d=dist({lat:t.latitude,lon:t.longitude},{lat,lon});if(d<=matchRadius&&(!nearest||d<nearest.distanceM))nearest={element:e,matchMethod:'coordinates',distanceM:Math.round(d)};}if(nearest)return nearest;}return null;}
  async function one(t){
    const seen=new Set();
    for(const term of t.variants||[]){const key=String(term||'').trim().toLowerCase();if(!key||seen.has(key))continue;seen.add(key);const p=new URLSearchParams({sLibelleBorne:term,bUniquementBornesDisponibles:'false',bNePasClusteriser:'1',nBornesPrivees:'0'});const j=await getJson('/api/Stations?'+p.toString());const found=match(t,Array.isArray(j?.aElements)?j.aElements:[]);if(found){let e=found.element;const tariff=String(e?.sWebTexte||e?.aBornes?.[0]?.sWebTextePool||e?.aBornes?.[0]?.szWebTexte||'').trim();const bornes=Array.isArray(e?.aBornes)?e.aBornes:[];if((!tariff||bornes.length===0)&&e?.sOrigine&&e?.nIdPool!=null){const detail=await getJson('/api/Stations/'+encodeURIComponent(e.sOrigine)+'/'+encodeURIComponent(String(e.nIdPool)));detailCount++;const de=Array.isArray(detail?.aElements)?detail.aElements.find(direct):null;if(de)e=de;}return {...found,element:e,searchTerm:term};}}
    return {resolved:false};
  }
  const out=new Array(targets.length);let next=0,done=0;
  async function worker(){while(true){const i=next++;if(i>=targets.length)return;out[i]=await one(targets[i]);done++;if(done%50===0||done===targets.length)console.log(`[e-Totem/browser] progress ${done}/${targets.length}; resolved=${out.filter(x=>x?.element).length}; requests=${requestCount}; errors=${errorCount}`);await sleep(120);}}
  await Promise.all(Array.from({length:concurrency},()=>worker()));
  return {out,stats:{requestCount,errorCount,retryCount,detailCount,resolved:out.filter(x=>x?.element).length}};
},{targets:payload,concurrency:CONCURRENCY,matchRadius:MATCH_RADIUS_M});
await browser.close();
console.log('[e-Totem] search harvest',JSON.stringify(harvest.stats));

const stations=[];let exact=0,coordFallback=0,unresolved=0,withTariff=0;
for(const target of targets){const r=harvest.out?.[target.index];if(!r?.element||!direct(r.element)){unresolved++;stations.push({...target,resolved:false});continue;}if(r.matchMethod==='id')exact++;else coordFallback++;const match=r.element,tariffHtml=String(match.sWebTexte||match.aBornes?.[0]?.sWebTextePool||match.aBornes?.[0]?.szWebTexte||''),tariffText=htmlToText(tariffHtml),signature=tariffSignature(tariffText);if(tariffText)withTariff++;stations.push({...target,resolved:true,matchMethod:r.matchMethod,distanceM:r.distanceM??null,searchTerm:r.searchTerm||null,api:{sIdPool:match.sIdPool,sIdPoolUnique:match.sIdPoolUnique,sOrigine:match.sOrigine,sLibelle:match.sLibelle,sNomReseau:match.sNomReseau,sTypeBorne:match.sTypeBorne,bOcpi:match.bOcpi,bGireve:match.bGireve,bItinerance:match.bItinerance,nIdPool:match.nIdPool},tariffHtml,tariffText,tariffSignature:signature,tariffHints:parseHints(tariffText),apiPdc:(match.aBornes||[]).flatMap(b=>(b.aPdc||[]).map(p=>({nIdPdc:p.nIdPdc,nIdBorne:p.nIdBorne,nConnectorId:p.nConnectorId,status:p.szStatus,types:p.szTypePrises||[]})))});}
const profileMap=new Map();for(const s of stations.filter(s=>s.resolved&&s.tariffText)){if(!profileMap.has(s.tariffSignature))profileMap.set(s.tariffSignature,{count:0,text:s.tariffText,hints:s.tariffHints,exampleStations:[]});const p=profileMap.get(s.tariffSignature);p.count++;if(p.exampleStations.length<8)p.exampleStations.push({stationId:s.stationId,name:s.name,network:s.api?.sNomReseau,maxPowerKw:s.maxPowerKw});}
const profiles=[...profileMap.values()].sort((a,b)=>b.count-a.count);
const output={schemaVersion:'3.0.0',generatedAt:new Date().toISOString(),operator:'e-Totem',country:'FR',scope:{physicalCpoDirectOnly:true,roamingIncluded:false,source:'public anonymous e-Totem /api/Stations station-label search index joined to strict e-Totem IRVE inventory',nativeFilter:'bOcpi=0 AND bGireve=0 AND bItinerance=0',noGuessedFallback:true},harvest:{strategy:'anonymous station-label search + exact EMI3 join + <=150m coordinate fallback + detail endpoint only when needed',concurrency:CONCURRENCY,...harvest.stats},counts:{inventoryStations:targets.length,resolvedStations:exact+coordFallback,exactIdMatches:exact,coordinateFallbackMatches:coordFallback,unresolvedStations:unresolved,resolvedWithTariffText:withTariff,uniqueTariffProfiles:profiles.length},tariffProfiles:profiles,stations};
fs.mkdirSync('data/national',{recursive:true});fs.writeFileSync(OUTPUT,zlib.gzipSync(Buffer.from(JSON.stringify(output),'utf8'),{level:9}));
console.log(JSON.stringify({harvest:output.harvest,counts:output.counts},null,2));
console.log(JSON.stringify(profiles.slice(0,30).map((p,i)=>({rank:i+1,count:p.count,text:p.text.slice(0,900),hints:p.hints,examples:p.exampleStations.slice(0,3)})),null,2));
