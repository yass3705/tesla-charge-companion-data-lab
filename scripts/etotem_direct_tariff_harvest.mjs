import fs from 'fs';
import zlib from 'zlib';
import { chromium } from 'playwright-core';

const INVENTORY='data/national/etotem_direct_stations_france.json.gz';
const OUTPUT='data/national/etotem_direct_tariffs_france.json.gz';
const ORIGIN='https://www.e-totem.fr/';
const CONCURRENCY=8;
const BATCH=80;

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

if(!fs.existsSync(INVENTORY)) throw new Error(`Missing ${INVENTORY}`);
const inv=JSON.parse(zlib.gunzipSync(fs.readFileSync(INVENTORY)).toString('utf8'));
const targets=inv.stations.map((s,i)=>({index:i,stationId:s.stationId,name:s.name,latitude:Number(s.latitude),longitude:Number(s.longitude),maxPowerKw:s.maxPowerKw,pdcCount:s.pdcCount,dataset:s.dataset?.title||null}));
console.log(`[e-Totem] inventory=${targets.length}`);

const browser=await chromium.launch({headless:true,executablePath:'/usr/bin/google-chrome',args:['--no-sandbox']});
const page=await browser.newPage({locale:'fr-FR',viewport:{width:1440,height:1000}});
await page.goto(ORIGIN,{waitUntil:'domcontentloaded',timeout:60000});
const bootstrap=await page.evaluate(async()=>{
  const ctl=new AbortController(),timer=setTimeout(()=>ctl.abort(),10000);
  try{
    const r=await fetch('/api/ConnexionAnonyme',{method:'POST',headers:{Accept:'application/json'},signal:ctl.signal});
    const text=await r.text();
    if(!r.ok)throw new Error(`ConnexionAnonyme HTTP ${r.status}`);
    const j=JSON.parse(text);
    if(j?.bSucces!==true||!j?.szToken)throw new Error('ConnexionAnonyme returned no usable anonymous token');
    window.__ETOTEM_HARVEST_TOKEN=j.szToken;
    return {status:r.status,userType:j.szTypeUtilisateur||null,success:true};
  }finally{clearTimeout(timer);}
});
if(!bootstrap?.success){await browser.close();throw new Error('Anonymous bootstrap failed');}
console.log(`[e-Totem] ConnexionAnonyme OK status=${bootstrap.status} type=${bootstrap.userType||'unknown'}; starting station-by-station harvest`);

const rawResults=[];
for(let start=0;start<targets.length;start+=BATCH){
  const chunk=targets.slice(start,start+BATCH);
  const part=await page.evaluate(async ({targets,concurrency})=>{
    const token=window.__ETOTEM_HARVEST_TOKEN;
    if(!token)throw new Error('Anonymous token missing from browser memory');
    const headers={Accept:'application/json',Authorization:'Bearer '+token};
    const norm=v=>String(v||'').toUpperCase().replace(/[^A-Z0-9]/g,'');
    const isDirect=e=>String(e?.bOcpi??0)==='0'&&String(e?.bGireve??0)==='0'&&String(e?.bItinerance??0)==='0';
    const dist=(a,b)=>{const R=6371000,r=Math.PI/180,dLat=(b.lat-a.lat)*r,dLon=(b.lon-a.lon)*r,la1=a.lat*r,la2=b.lat*r;const h=Math.sin(dLat/2)**2+Math.cos(la1)*Math.cos(la2)*Math.sin(dLon/2)**2;return 2*R*Math.asin(Math.sqrt(h));};
    const sleep=ms=>new Promise(r=>setTimeout(r,ms));
    async function query(t,delta,attempt=0){
      const p=new URLSearchParams({fLatSudOuest:String(t.latitude-delta),fLongSudOuest:String(t.longitude-delta),fLatNordEst:String(t.latitude+delta),fLongNordEst:String(t.longitude+delta),bUniquementBornesDisponibles:'false',bCompatibleAutocharge:'0',nZoom:'18',bNePasClusteriser:'1',nBornesPrivees:'0',bRecupererBorneLaPlusProche:'0'});
      const ctl=new AbortController(),timer=setTimeout(()=>ctl.abort(),6500);
      try{
        const r=await fetch('/api/Stations?'+p.toString(),{headers,signal:ctl.signal});
        const text=await r.text();
        if(r.status===401&&attempt<1){
          const ar=await fetch('/api/ConnexionAnonyme',{method:'POST',headers:{Accept:'application/json'}});const aj=await ar.json();
          if(ar.ok&&aj?.bSucces===true&&aj?.szToken){window.__ETOTEM_HARVEST_TOKEN=aj.szToken;headers.Authorization='Bearer '+aj.szToken;return query(t,delta,attempt+1);}
        }
        if(!r.ok)throw new Error('http_'+r.status);
        const j=JSON.parse(text),elements=(Array.isArray(j?.aElements)?j.aElements:[]).filter(isDirect);
        return {elements,status:r.status};
      }catch(e){if(attempt<1){await sleep(180);return query(t,delta,attempt+1);}return {elements:[],error:String(e)};}finally{clearTimeout(timer);}
    }
    async function one(t){
      if(!Number.isFinite(t.latitude)||!Number.isFinite(t.longitude))return {index:t.index,resolved:false,error:'missing_coordinates'};
      const wanted=norm(t.stationId);
      for(const delta of [0.010,0.030]){
        const q=await query(t,delta);const exact=q.elements.find(e=>norm(e.sIdPool)===wanted);
        if(exact)return {index:t.index,resolved:true,matchMethod:'id',distanceM:0,element:exact};
        let nearest=null;
        for(const e of q.elements){const lat=Number(e.fLatitude),lon=Number(e.fLongitude);if(!Number.isFinite(lat)||!Number.isFinite(lon))continue;const d=dist({lat:t.latitude,lon:t.longitude},{lat,lon});if(!nearest||d<nearest.d)nearest={d,e};}
        if(nearest&&nearest.d<=120)return {index:t.index,resolved:true,matchMethod:'coordinates',distanceM:Math.round(nearest.d),element:nearest.e};
      }
      return {index:t.index,resolved:false};
    }
    const out=new Array(targets.length);let next=0;
    async function worker(){while(true){const i=next++;if(i>=targets.length)return;out[i]=await one(targets[i]);await sleep(20);}}
    await Promise.all(Array.from({length:concurrency},()=>worker()));return out;
  },{targets:chunk,concurrency:CONCURRENCY});
  rawResults.push(...part);
  console.log(`[e-Totem] progress ${Math.min(start+BATCH,targets.length)}/${targets.length}; resolved=${rawResults.filter(x=>x?.resolved).length}`);
}
await page.evaluate(()=>{delete window.__ETOTEM_HARVEST_TOKEN;});
await browser.close();

const resultByIndex=new Map(rawResults.map(r=>[r.index,r]));
const stations=[];let exact=0,coordFallback=0,unresolved=0,withTariff=0;
for(const target of targets){
  const r=resultByIndex.get(target.index);
  if(!r?.resolved||!r.element||!direct(r.element)){unresolved++;stations.push({...target,resolved:false});continue;}
  if(r.matchMethod==='id')exact++;else coordFallback++;
  const match=r.element,tariffHtml=String(match.sWebTexte||match.aBornes?.[0]?.sWebTextePool||match.aBornes?.[0]?.szWebTexte||''),tariffText=htmlToText(tariffHtml),signature=tariffSignature(tariffText);if(tariffText)withTariff++;
  stations.push({...target,resolved:true,matchMethod:r.matchMethod,distanceM:r.distanceM??null,api:{sIdPool:match.sIdPool,sIdPoolUnique:match.sIdPoolUnique,sOrigine:match.sOrigine,sLibelle:match.sLibelle,sNomReseau:match.sNomReseau,sTypeBorne:match.sTypeBorne,bOcpi:match.bOcpi,bGireve:match.bGireve,bItinerance:match.bItinerance,nIdPool:match.nIdPool},tariffHtml,tariffText,tariffSignature:signature,tariffHints:parseHints(tariffText),apiPdc:(match.aBornes||[]).flatMap(b=>(b.aPdc||[]).map(p=>({nIdPdc:p.nIdPdc,nIdBorne:p.nIdBorne,nConnectorId:p.nConnectorId,status:p.szStatus,types:p.szTypePrises||[]})))});
}
const profileMap=new Map();
for(const s of stations.filter(s=>s.resolved&&s.tariffText)){if(!profileMap.has(s.tariffSignature))profileMap.set(s.tariffSignature,{count:0,text:s.tariffText,hints:s.tariffHints,exampleStations:[]});const p=profileMap.get(s.tariffSignature);p.count++;if(p.exampleStations.length<8)p.exampleStations.push({stationId:s.stationId,name:s.name,network:s.api?.sNomReseau,maxPowerKw:s.maxPowerKw});}
const profiles=[...profileMap.values()].sort((a,b)=>b.count-a.count);
const output={schemaVersion:'1.3.1',generatedAt:new Date().toISOString(),operator:'e-Totem',country:'FR',scope:{physicalCpoDirectOnly:true,roamingIncluded:false,source:'public anonymous e-Totem API through browser network path: ConnexionAnonyme + authenticated /api/Stations joined to strict e-Totem IRVE inventory',nativeFilter:'bOcpi=0 AND bGireve=0 AND bItinerance=0',noGuessedFallback:true},harvest:{strategy:'explicit anonymous bootstrap in browser + station-by-station tight bbox + bounded wider fallback',concurrency:CONCURRENCY,batchSize:BATCH},counts:{inventoryStations:targets.length,resolvedStations:exact+coordFallback,exactIdMatches:exact,coordinateFallbackMatches:coordFallback,unresolvedStations:unresolved,resolvedWithTariffText:withTariff,uniqueTariffProfiles:profiles.length},tariffProfiles:profiles,stations};
fs.mkdirSync('data/national',{recursive:true});fs.writeFileSync(OUTPUT,zlib.gzipSync(Buffer.from(JSON.stringify(output),'utf8'),{level:9}));
console.log(JSON.stringify({harvest:output.harvest,counts:output.counts},null,2));
console.log(JSON.stringify(profiles.slice(0,30).map((p,i)=>({rank:i+1,count:p.count,text:p.text.slice(0,900),hints:p.hints,examples:p.exampleStations.slice(0,3)})),null,2));