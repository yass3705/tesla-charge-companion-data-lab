import fs from 'fs';
import zlib from 'zlib';
import { chromium } from 'playwright-core';

const inv=JSON.parse(zlib.gunzipSync(fs.readFileSync('data/national/etotem_direct_stations_france.json.gz')).toString('utf8'));
const normId=v=>String(v||'').toUpperCase().replace(/[^A-Z0-9]/g,'');
const family=id=>['FRETI','FRESE','FRG10','FRCAR','FRSUA'].find(p=>normId(id).startsWith(p))||'OTHER';
const boxes=[[41,52,-6.5,11],[15.5,16.7,-62,-60.8],[14.2,15.1,-61.5,-60.6],[2,6,-55.5,-51],[-22,-20,54.5,56],[-13.2,-12.4,44.8,45.5],[46.6,47.2,-56.7,-56.0]];
const inFrance=(lat,lon)=>boxes.some(([a,b,c,d])=>lat>=a&&lat<=b&&lon>=c&&lon<=d);
function coords(s){let lat=Number(s?.latitude),lon=Number(s?.longitude);if(!Number.isFinite(lat)||!Number.isFinite(lon))return null;if(!inFrance(lat,lon)&&inFrance(lon,lat))[lat,lon]=[lon,lat];return {lat,lon};}
function apiCoords(e){const lat=Number(e?.fLatitude),lon=Number(e?.fLongitude);return Number.isFinite(lat)&&Number.isFinite(lon)?{lat,lon}:null;}
function distanceM(a,b){const R=6371000,r=Math.PI/180,dLat=(b.lat-a.lat)*r,dLon=(b.lon-a.lon)*r,la1=a.lat*r,la2=b.lat*r;const h=Math.sin(dLat/2)**2+Math.cos(la1)*Math.cos(la2)*Math.sin(dLon/2)**2;return 2*R*Math.asin(Math.sqrt(h));}
const direct=e=>String(e?.bOcpi??0)==='0'&&String(e?.bGireve??0)==='0'&&String(e?.bItinerance??0)==='0'&&normId(e?.sIdPool).startsWith('FR');

const browser=await chromium.launch({headless:true,executablePath:'/usr/bin/google-chrome',args:['--no-sandbox']});
const page=await browser.newPage({locale:'fr-FR'});await page.goto('https://www.e-totem.fr/',{waitUntil:'domcontentloaded',timeout:60000});
async function search(q){return await page.evaluate(async q=>{const ctl=new AbortController(),timer=setTimeout(()=>ctl.abort(),25000);try{const u='/api/Stations?sLibelleBorne='+encodeURIComponent(q)+'&bUniquementBornesDisponibles=false&bNePasClusteriser=1&nBornesPrivees=0';const r=await fetch(u,{credentials:'include',cache:'no-store',signal:ctl.signal});const j=await r.json();return Array.isArray(j?.aElements)?j.aElements:[];}finally{clearTimeout(timer);}},q);}
const queries=['e-Totem','SEMOB','INTERMARCHE','Carrefour','Super U','Hyper U','U Express','Utile','Cooperative U','Saint Etienne','Saint-Étienne','G10'];
const map=new Map(),queryCounts={};
for(const q of queries){const a=await search(q);queryCounts[q]=a.length;for(const e of a)if(direct(e))map.set(normId(e.sIdPool),e);}
const elements=[...map.values()],byId=new Map(elements.map(e=>[normId(e.sIdPool),e]));
const result={queryCounts,nativeElements:elements.length,correctedCoordinates:0,coverage:{},unresolvedExamples:{}};
for(const fam of ['FRETI','FRESE','FRG10','FRCAR','FRSUA']){
  const stations=inv.stations.filter(s=>family(s.stationId)===fam);let exact=0,coord=0;
  const unresolved=[];
  for(const s of stations){const raw={lat:Number(s.latitude),lon:Number(s.longitude)},c=coords(s);if(c&&(c.lat!==raw.lat||c.lon!==raw.lon))result.correctedCoordinates++;
    if(byId.has(normId(s.stationId))){exact++;continue;}
    if(!c){unresolved.push({id:s.stationId,name:s.name,reason:'no_coord'});continue;}
    const near=elements.map(e=>({e,c:apiCoords(e)})).filter(x=>x.c).map(x=>({...x,d:distanceM(c,x.c)})).sort((a,b)=>a.d-b.d);
    if(near[0]?.d<=120){coord++;continue;}
    unresolved.push({id:s.stationId,name:s.name,lat:c.lat,lon:c.lon,nearestM:near[0]?Math.round(near[0].d):null,nearestId:near[0]?.e?.sIdPool||'',nearestName:near[0]?.e?.sLibelle||''});
  }
  result.coverage[fam]={inventory:stations.length,exact,coordinate:coord,resolved:exact+coord,unresolved:stations.length-exact-coord};
  result.unresolvedExamples[fam]=unresolved.slice(0,5);
}
console.log(JSON.stringify(result,null,2));
await browser.close();
