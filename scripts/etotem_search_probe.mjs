import fs from 'fs';
import zlib from 'zlib';
import { chromium } from 'playwright-core';

const inv=JSON.parse(zlib.gunzipSync(fs.readFileSync('data/national/etotem_direct_stations_france.json.gz')).toString('utf8'));
const normId=v=>String(v||'').toUpperCase().replace(/[^A-Z0-9]/g,'');
const family=id=>['FRETI','FRESE','FRG10','FRCAR','FRSUA'].find(p=>normId(id).startsWith(p))||'OTHER';
const samples={};for(const fam of ['FRG10','FRCAR','FRSUA'])samples[fam]=inv.stations.filter(s=>family(s.stationId)===fam).slice(0,2);
const browser=await chromium.launch({headless:true,executablePath:'/usr/bin/google-chrome',args:['--no-sandbox']});
const page=await browser.newPage({locale:'fr-FR'});await page.goto('https://www.e-totem.fr/',{waitUntil:'domcontentloaded',timeout:60000});
async function search(q){return await page.evaluate(async q=>{const ctl=new AbortController(),timer=setTimeout(()=>ctl.abort(),25000);try{const u='/api/Stations?sLibelleBorne='+encodeURIComponent(q)+'&bUniquementBornesDisponibles=false&bNePasClusteriser=1&nBornesPrivees=0';const r=await fetch(u,{credentials:'include',cache:'no-store',signal:ctl.signal});const j=await r.json();return Array.isArray(j?.aElements)?j.aElements:[];}finally{clearTimeout(timer);}},q);}
function summarize(e){const coordinateLike={};for(const [k,v] of Object.entries(e||{}))if(/lat|lon|coord|position|gps/i.test(k))coordinateLike[k]=v;return {sIdPool:e?.sIdPool,sLibelle:e?.sLibelle,sOrigine:e?.sOrigine,nIdPool:e?.nIdPool,bOcpi:e?.bOcpi,bGireve:e?.bGireve,bItinerance:e?.bItinerance,coordinateLike,keys:Object.keys(e||{})};}
const direct=a=>a.filter(e=>String(e?.bOcpi??0)==='0'&&String(e?.bGireve??0)==='0'&&String(e?.bItinerance??0)==='0');
const broad={};for(const q of ['e-Totem','SEMOB','Carrefour','Super U'])broad[q]=direct(await search(q)).slice(0,5).map(summarize);
const out={broad,samples:{}};
for(const [fam,items] of Object.entries(samples)){out.samples[fam]=[];for(const s of items){const q=String(s.name||'').trim();out.samples[fam].push({inventory:{stationId:s.stationId,name:s.name,latitude:s.latitude,longitude:s.longitude},query:q,results:direct(await search(q)).slice(0,5).map(summarize)});}}
console.log(JSON.stringify(out,null,2));await browser.close();
