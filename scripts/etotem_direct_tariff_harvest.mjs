import fs from 'fs';
import zlib from 'zlib';
import { chromium } from 'playwright-core';

const INVENTORY='data/national/etotem_direct_stations_france.json.gz';
const OUTPUT='data/national/etotem_direct_tariffs_france.json.gz';
const HOME='https://www.e-totem.fr/';
const CONCURRENCY=3;
const MATCH_RADIUS_M=120;
const BROAD_QUERIES=[
  'e-Totem','SEMOB','INTERMARCHE','Carrefour','Super U','Hyper U','U Express','Utile',
  'Cooperative U','Saint Etienne','Saint-Étienne','G10'
];

const sleep=ms=>new Promise(r=>setTimeout(r,ms));
function normId(v){return String(v||'').toUpperCase().replace(/[^A-Z0-9]/g,'');}
function normText(v){return String(v||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9]+/g,' ').replace(/\s+/g,' ').trim();}
function direct(e){return String(e?.bOcpi??0)==='0'&&String(e?.bGireve??0)==='0'&&String(e?.bItinerance??0)==='0';}
function frApiId(e){return normId(e?.sIdPool).startsWith('FR');}
function distanceM(a,b){const R=6371000,r=Math.PI/180,dLat=(b.lat-a.lat)*r,dLon=(b.lon-a.lon)*r,la1=a.lat*r,la2=b.lat*r;const h=Math.sin(dLat/2)**2+Math.cos(la1)*Math.cos(la2)*Math.sin(dLon/2)**2;return 2*R*Math.asin(Math.sqrt(h));}
function decodeEntities(s){
  const named={euro:'€',amp:'&',nbsp:' ',apos:"'",quot:'"',agrave:'à',Agrave:'À',eacute:'é',Eacute:'É',ecirc:'ê',acirc:'â',ocirc:'ô',ucirc:'û',icirc:'î',ccedil:'ç',ugrave:'ù',rsquo:"'",laquo:'«',raquo:'»'};
  return String(s||'').replace(/&([A-Za-z]+);/g,(m,k)=>Object.hasOwn(named,k)?named[k]:m).replace(/&#(\d+);/g,(m,n)=>String.fromCodePoint(Number(n))).replace(/&#x([0-9a-f]+);/gi,(m,n)=>String.fromCodePoint(parseInt(n,16)));
}
function htmlToText(v){let s=String(v||'');for(let i=0;i<3;i++)s=decodeEntities(s);return s.replace(/<br\s*\/?\s*>/gi,'\n').replace(/<\/p\s*>/gi,'\n').replace(/<[^>]+>/g,' ').replace(/\\'/g,"'").replace(/\r/g,'').replace(/[ \t]+/g,' ').replace(/ *\n+ */g,'\n').trim();}
function num(v){const n=Number(String(v).replace(',','.'));return Number.isFinite(n)?n:null;}
function parseHints(text){
  const t=String(text||''),kwh=[],timeFees=[],grace=[],caps=[];
  for(const m of t.matchAll(/(\d+(?:[.,]\d+)?)\s*€\s*(?:\/|par)?\s*kwh/gi)){const n=num(m[1]);if(n!==null&&!kwh.includes(n))kwh.push(n);}
  for(const m of t.matchAll(/(\d+(?:[.,]\d+)?)\s*€\s*\/?\s*(\d+)\s*min/gi)){const item={eur:num(m[1]),minutes:Number(m[2]),raw:m[0]};if(!timeFees.some(x=>x.eur===item.eur&&x.minutes===item.minutes))timeFees.push(item);}
  for(const m of t.matchAll(/(\d+)\s*min(?:ute)?s?\s+gratuite?s?/gi)){const n=Number(m[1]);if(!grace.includes(n))grace.push(n);}
  for(const m of t.matchAll(/plafonn?[eé]\s+[àa]\s*(\d+(?:[.,]\d+)?)\s*€(?:\s+entre\s+(\d{1,2})h(?:\d{2})?\s+et\s+(\d{1,2})h(?:\d{2})?)?/gi))caps.push({eur:num(m[1]),start:m[2]?`${m[2].padStart(2,'0')}:00`:null,end:m[3]?`${m[3].padStart(2,'0')}:00`:null,raw:m[0]});
  const eco=/\bmode\s+eco\b/i.test(t);
  const postCharge=/une fois le v[eé]hicule recharg[eé]|apr[eè]s (?:la )?recharge|post[- ]charge/i.test(t);
  const noPost=/sans (?:forfait (?:de )?)?post[- ]charge/i.test(t);
  return {pricePerKwhCandidatesEur:kwh,timeFeeCandidates:timeFees,freeGraceMinutesCandidates:grace,capCandidates:caps,mentionsEcoMode:eco,postChargeSemantics:postCharge,noPostChargeFee:noPost};
}
function familyOf(id){const n=normId(id);for(const p of ['FRETI','FRESE','FRG10','FRCAR','FRSUA'])if(n.startsWith(p))return p;return n.slice(0,5)||'UNKNOWN';}
function apiTariffRaw(e){return String(e?.sWebTexte||e?.sWebTextePool||e?.aBornes?.[0]?.sWebTextePool||e?.aBornes?.[0]?.szWebTexte||'').trim();}
function apiCoords(e){const lat=Number(e?.fLatitude??e?.latitude),lon=Number(e?.fLongitude??e?.longitude);return Number.isFinite(lat)&&Number.isFinite(lon)?{lat,lon}:null;}
function elementKey(e){return normId(e?.sIdPool)||normId(e?.sIdPoolUnique)||`${e?.sOrigine||''}|${e?.nIdPool||''}|${e?.fLatitude||''}|${e?.fLongitude||''}`;}
function targetNameVariants(t){
  const out=[],add=v=>{v=String(v||'').trim();if(v.length>=3&&!out.some(x=>normText(x)===normText(v)))out.push(v.slice(0,100));};
  add(t.name);add(String(t.name||'').replace(/^\s*e[ -]?totem\s*[-–—:]?\s*/i,''));add(t.brandName);add(t.stationIdLocal);
  const n=String(t.name||'').replace(/^\s*(?:e[ -]?totem|semob)\s*[-–—:]?\s*/i,'').trim();
  const words=n.split(/\s+/).filter(x=>x.length>=4);if(words.length>=2)add(words.slice(-3).join(' '));if(words.length)add(words.at(-1));
  return out.slice(0,4);
}
function safeCoordinateCandidate(t,elements){
  if(!Number.isFinite(t.latitude)||!Number.isFinite(t.longitude))return null;
  const near=[];
  for(const e of elements){const c=apiCoords(e);if(!c)continue;const d=distanceM({lat:t.latitude,lon:t.longitude},c);if(d<=MATCH_RADIUS_M)near.push({e,d});}
  near.sort((a,b)=>a.d-b.d);if(!near.length)return null;
  if(near.length===1)return near[0];
  if(near[0].d<=35&&near[1].d-near[0].d>=25)return near[0];
  const tn=normText(t.name),scored=near.map(x=>{const en=normText(x.e?.sLibelle),tokens=tn.split(' ').filter(w=>w.length>=4),hit=tokens.filter(w=>en.includes(w)).length;return {...x,hit};}).sort((a,b)=>b.hit-a.hit||a.d-b.d);
  return scored[0].hit>=2&&scored[0].hit>scored[1].hit?scored[0]:null;
}

if(!fs.existsSync(INVENTORY))throw new Error(`Missing ${INVENTORY}`);
const inv=JSON.parse(zlib.gunzipSync(fs.readFileSync(INVENTORY)).toString('utf8'));
const targets=(inv.stations||[]).map((s,index)=>({index,stationId:s.stationId,stationIdLocal:s.stationIdLocal||'',name:s.name||'',brandName:s.brandName||'',address:s.address||'',latitude:Number(s.latitude),longitude:Number(s.longitude),maxPowerKw:Number(s.maxPowerKw||0),pdcCount:Number(s.pdcCount||0),pdcs:s.pdcs||[],dataset:s.dataset?.title||'',family:familyOf(s.stationId)}));
console.log(`[e-Totem] inventory=${targets.length}; strategy=hybrid broad index + targeted fallback`);

const browser=await chromium.launch({headless:true,executablePath:'/usr/bin/google-chrome',args:['--no-sandbox']});
const page=await browser.newPage({locale:'fr-FR',viewport:{width:1280,height:900}});
await page.goto(HOME,{waitUntil:'domcontentloaded',timeout:60000});

const allElements=new Map();let requestCount=0,errorCount=0,retryCount=0,detailCount=0,broadCalls=0,targetedCalls=0;
async function search(query,attempt=0){
  requestCount++;
  try{
    const result=await page.evaluate(async q=>{const ctl=new AbortController(),timer=setTimeout(()=>ctl.abort(),25000);try{const u='/api/Stations?sLibelleBorne='+encodeURIComponent(q)+'&bUniquementBornesDisponibles=false&bNePasClusteriser=1&nBornesPrivees=0';const r=await fetch(u,{credentials:'include',cache:'no-store',signal:ctl.signal});const text=await r.text();if(!r.ok)throw new Error(`http_${r.status}`);const j=JSON.parse(text);return Array.isArray(j?.aElements)?j.aElements:[];}finally{clearTimeout(timer);}},query);
    return result;
  }catch(err){if(attempt<2){retryCount++;await sleep(500*(attempt+1));return search(query,attempt+1);}errorCount++;return [];}
}
async function addSearch(query,kind){const elements=await search(query);if(kind==='broad')broadCalls++;else targetedCalls++;for(const e of elements)if(direct(e)&&frApiId(e))allElements.set(elementKey(e),e);return elements.length;}

for(const q of BROAD_QUERIES){const n=await addSearch(q,'broad');console.log(`[e-Totem] broad ${JSON.stringify(q)} -> ${n} API elements; native FR pool=${allElements.size}`);await sleep(180);}

const matched=new Map();let exact=0,coordinate=0,targetedResolved=0;
function reindexAndMatch(unresolvedOnly=false){
  const elements=[...allElements.values()];const byId=new Map();for(const e of elements){const id=normId(e?.sIdPool);if(id)byId.set(id,e);}
  for(const t of targets){if(matched.has(t.index))continue;const e=byId.get(normId(t.stationId));if(e){matched.set(t.index,{element:e,method:'id',distanceM:0});exact++;continue;}const c=safeCoordinateCandidate(t,elements);if(c){matched.set(t.index,{element:c.e,method:'coordinates',distanceM:Math.round(c.d)});coordinate++;}}
}
reindexAndMatch();
console.log(`[e-Totem] after broad preload resolved=${matched.size}/${targets.length}; exact=${exact}; coordinate=${coordinate}`);

const pending=()=>targets.filter(t=>!matched.has(t.index));
let queue=pending(),next=0;
async function targetedWorker(){
  while(true){const pos=next++;if(pos>=queue.length)return;const t=queue[pos];let found=false;
    for(const q of targetNameVariants(t)){
      const before=allElements.size;await addSearch(q,'targeted');
      const fresh=[...allElements.values()];const id=fresh.find(e=>normId(e?.sIdPool)===normId(t.stationId));
      if(id){matched.set(t.index,{element:id,method:'id',distanceM:0});exact++;targetedResolved++;found=true;break;}
      const c=safeCoordinateCandidate(t,fresh);if(c){matched.set(t.index,{element:c.e,method:'coordinates',distanceM:Math.round(c.d)});coordinate++;targetedResolved++;found=true;break;}
      if(allElements.size===before)await sleep(80);
    }
    if(!found&&pos%25===0)console.log(`[e-Totem] targeted progress ${pos}/${queue.length}; resolved=${matched.size}`);
    await sleep(120);
  }
}
await Promise.all(Array.from({length:CONCURRENCY},()=>targetedWorker()));
reindexAndMatch(true);
console.log(`[e-Totem] final matching resolved=${matched.size}/${targets.length}; exact=${exact}; coordinate=${coordinate}; targetedResolved=${targetedResolved}`);

async function detail(e){
  const origin=String(e?.sOrigine||''),id=String(e?.nIdPool||'');if(!origin||!id)return e;detailCount++;requestCount++;
  try{return await page.evaluate(async ({origin,id})=>{const ctl=new AbortController(),timer=setTimeout(()=>ctl.abort(),20000);try{const r=await fetch('/api/Stations/'+encodeURIComponent(origin)+'/'+encodeURIComponent(id),{credentials:'include',cache:'no-store',signal:ctl.signal});if(!r.ok)throw new Error(`http_${r.status}`);const j=await r.json();return Array.isArray(j?.aElements)&&j.aElements[0]?j.aElements[0]:j;}finally{clearTimeout(timer);}},{origin,id});}catch{errorCount++;return e;}
}

const records=[];const profiles=new Map();
for(const t of targets){
  const m=matched.get(t.index);if(!m){records.push({...t,resolved:false,reason:'not_found_in_public_native_index'});continue;}
  let e=m.element;let raw=apiTariffRaw(e);if(!raw||!(e?.aBornes?.length)){e=await detail(e);raw=apiTariffRaw(e);}
  const clean=htmlToText(raw),hints=parseHints(clean),sig=normText(clean);
  if(clean){if(!profiles.has(sig))profiles.set(sig,{text:clean,rawHtml:raw,count:0,hints,examples:[]});const p=profiles.get(sig);p.count++;if(p.examples.length<5)p.examples.push({stationId:t.stationId,name:t.name,network:e?.sNomReseau||'',maxPowerKw:t.maxPowerKw});}
  records.push({...t,resolved:true,matchMethod:m.method,matchDistanceM:m.distanceM,tariffRawHtml:raw,tariffText:clean,tariffHints:hints,api:{sIdPool:e?.sIdPool||'',sIdPoolUnique:e?.sIdPoolUnique||'',sOrigine:e?.sOrigine||'',nIdPool:e?.nIdPool??null,sLibelle:e?.sLibelle||'',sNomReseau:e?.sNomReseau||'',fLatitude:Number(e?.fLatitude),fLongitude:Number(e?.fLongitude),bOcpi:e?.bOcpi??0,bGireve:e?.bGireve??0,bItinerance:e?.bItinerance??0,aBornes:Array.isArray(e?.aBornes)?e.aBornes:[]}});
}
await browser.close();

const coverage={};for(const fam of ['FRETI','FRESE','FRG10','FRCAR','FRSUA']){const subset=records.filter(r=>r.family===fam),resolved=subset.filter(r=>r.resolved),withTariff=resolved.filter(r=>r.tariffText);coverage[fam]={inventory:subset.length,resolved:resolved.length,withTariff:withTariff.length,unresolved:subset.length-resolved.length};}
const resolvedRecords=records.filter(r=>r.resolved),withTariff=resolvedRecords.filter(r=>r.tariffText);
const tariffProfiles=[...profiles.values()].sort((a,b)=>b.count-a.count).map((p,i)=>({rank:i+1,...p}));
const out={schemaVersion:'2.0.0',generatedAt:new Date().toISOString(),operator:'e-Totem',country:'FR',scope:{physicalCpoDirectOnly:true,roamingIncluded:false,noGuessedFallback:true,source:'public e-Totem station search index joined to strict IRVE physical-CPO inventory',nativeFilter:'bOcpi=0 AND bGireve=0 AND bItinerance=0',tariffPolicy:'station-specific public tariff text; ECO/member alternatives retained as text but never selected as default automatically'},harvest:{strategy:'broad public index preload + exact EMI3 join + safe coordinate fallback + targeted station-label searches',concurrency:CONCURRENCY,broadQueries:BROAD_QUERIES,broadCalls,targetedCalls,requestCount,errorCount,retryCount,detailCount,targetedResolved,nativeFrElementsSeen:allElements.size},counts:{inventoryStations:targets.length,resolvedStations:resolvedRecords.length,exactIdMatches:exact,coordinateFallbackMatches:coordinate,unresolvedStations:targets.length-resolvedRecords.length,resolvedWithTariffText:withTariff.length,uniqueTariffProfiles:tariffProfiles.length},coverageByFamily:coverage,tariffProfiles,stations:records};
fs.mkdirSync('data/national',{recursive:true});fs.writeFileSync(OUTPUT,zlib.gzipSync(Buffer.from(JSON.stringify(out))));
console.log(JSON.stringify({harvest:out.harvest,counts:out.counts,coverageByFamily:coverage},null,2));
console.log(JSON.stringify(tariffProfiles.slice(0,20).map(p=>({rank:p.rank,count:p.count,text:p.text.slice(0,400),hints:p.hints,examples:p.examples.slice(0,3)})),null,2));
