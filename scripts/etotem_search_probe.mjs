import fs from 'fs';
import zlib from 'zlib';
import { chromium } from 'playwright-core';

const inv=JSON.parse(zlib.gunzipSync(fs.readFileSync('data/national/etotem_direct_stations_france.json.gz')).toString('utf8'));
const normId=v=>String(v||'').toUpperCase().replace(/[^A-Z0-9]/g,'');
const normText=v=>String(v||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9]+/g,' ').replace(/\s+/g,' ').trim();
const boxes=[[41,52,-6.5,11],[15.5,16.7,-62,-60.8],[14.2,15.1,-61.5,-60.6],[2,6,-55.5,-51],[-22,-20,54.5,56],[-13.2,-12.4,44.8,45.5],[46.6,47.2,-56.7,-56.0]];
const inFrance=(lat,lon)=>boxes.some(([a,b,c,d])=>lat>=a&&lat<=b&&lon>=c&&lon<=d);
function invCoords(s){let lat=Number(s.latitude),lon=Number(s.longitude);if(!Number.isFinite(lat)||!Number.isFinite(lon))return null;if(!inFrance(lat,lon)&&inFrance(lon,lat))[lat,lon]=[lon,lat];return {lat,lon};}
function apiCoords(e){const lat=Number(e?.fLatitude),lon=Number(e?.fLongitude);return Number.isFinite(lat)&&Number.isFinite(lon)?{lat,lon}:null;}
function distanceM(a,b){const R=6371000,r=Math.PI/180,dLat=(b.lat-a.lat)*r,dLon=(b.lon-a.lon)*r,la1=a.lat*r,la2=b.lat*r;const h=Math.sin(dLat/2)**2+Math.cos(la1)*Math.cos(la2)*Math.sin(dLon/2)**2;return 2*R*Math.asin(Math.sqrt(h));}
const direct=e=>String(e?.bOcpi??0)==='0'&&String(e?.bGireve??0)==='0'&&String(e?.bItinerance??0)==='0'&&normId(e?.sIdPool).startsWith('FR');
function safeCoordinateCandidate(t,elements){const c=invCoords(t);if(!c)return null;const near=[];for(const e of elements){const ec=apiCoords(e);if(!ec)continue;const d=distanceM(c,ec);if(d<=120)near.push({e,d});}near.sort((a,b)=>a.d-b.d);if(!near.length)return null;if(near.length===1)return near[0];if(near[0].d<=35&&near[1].d-near[0].d>=25)return near[0];const tn=normText(t.name),scored=near.map(x=>{const en=normText(x.e?.sLibelle),tokens=tn.split(' ').filter(w=>w.length>=4),hit=tokens.filter(w=>en.includes(w)).length;return {...x,hit};}).sort((a,b)=>b.hit-a.hit||a.d-b.d);return scored[0].hit>=2&&scored[0].hit>scored[1].hit?scored[0]:null;}

const browser=await chromium.launch({headless:true,executablePath:'/usr/bin/google-chrome',args:['--no-sandbox']});
const page=await browser.newPage({locale:'fr-FR'});await page.goto('https://www.e-totem.fr/',{waitUntil:'domcontentloaded',timeout:60000});
async function search(q){return await page.evaluate(async q=>{const ctl=new AbortController(),timer=setTimeout(()=>ctl.abort(),25000);try{const u='/api/Stations?sLibelleBorne='+encodeURIComponent(q)+'&bUniquementBornesDisponibles=false&bNePasClusteriser=1&nBornesPrivees=0';const r=await fetch(u,{credentials:'include',cache:'no-store',signal:ctl.signal});const j=await r.json();return Array.isArray(j?.aElements)?j.aElements:[];}finally{clearTimeout(timer);}},q);}
const queries=['e-Totem','SEMOB','INTERMARCHE','Carrefour','Super U','Hyper U','U Express','Utile','Cooperative U','Saint Etienne','Saint-Étienne','G10'];
const map=new Map();for(const q of queries){for(const e of await search(q))if(direct(e))map.set(normId(e.sIdPool),e);}
const elements=[...map.values()],byId=new Map(elements.map(e=>[normId(e.sIdPool),e])),matches=[];
for(const s of inv.stations||[]){if(byId.has(normId(s.stationId)))continue;const m=safeCoordinateCandidate(s,elements);if(!m)continue;const c=invCoords(s),ec=apiCoords(m.e);const a=normText(s.name),b=normText(m.e.sLibelle),tokens=a.split(' ').filter(w=>w.length>=4),common=tokens.filter(w=>b.includes(w));matches.push({inventory:{id:s.stationId,name:s.name,address:s.address,lat:c?.lat,lon:c?.lon},api:{id:m.e.sIdPool,name:m.e.sLibelle,lat:ec?.lat,lon:ec?.lon,network:m.e.sNomReseau,hasTariff:!!String(m.e.sWebTexte||'').trim()},distanceM:Math.round(m.d),commonNameTokens:common});}
console.log(JSON.stringify({count:matches.length,matches},null,2));await browser.close();
