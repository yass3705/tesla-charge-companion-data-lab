import { chromium } from 'playwright-core';
const browser=await chromium.launch({headless:true,executablePath:'/usr/bin/google-chrome',args:['--no-sandbox']});
const page=await browser.newPage({locale:'fr-FR'});await page.goto('https://www.e-totem.fr/',{waitUntil:'domcontentloaded',timeout:60000});
const normId=v=>String(v||'').toUpperCase().replace(/[^A-Z0-9]/g,'');
async function search(q,privateFlag){return await page.evaluate(async ({q,privateFlag})=>{const ctl=new AbortController(),timer=setTimeout(()=>ctl.abort(),25000);try{const u='/api/Stations?sLibelleBorne='+encodeURIComponent(q)+'&bUniquementBornesDisponibles=false&bNePasClusteriser=1&nBornesPrivees='+privateFlag;const r=await fetch(u,{credentials:'include',cache:'no-store',signal:ctl.signal});const text=await r.text();let j={};try{j=JSON.parse(text)}catch{};return {status:r.status,elements:Array.isArray(j?.aElements)?j.aElements:[]};}finally{clearTimeout(timer);}},{q,privateFlag});}
function direct(e){return String(e?.bOcpi??0)==='0'&&String(e?.bGireve??0)==='0'&&String(e?.bItinerance??0)==='0'&&normId(e?.sIdPool).startsWith('FR');}
function summary(e){return {id:e?.sIdPool,name:e?.sLibelle,private:e?.bPoolPrive,lat:e?.fLatitude,lon:e?.fLongitude,network:e?.sNomReseau,tariff:!!String(e?.sWebTexte||'').trim()};}
const out={};
for(const q of ['Carrefour Contact Périgny','Carrefour','SUPER U LE CHEYLARD','Super U','CBS - Gare de Culoz 1','CBS','Gare de Culoz','Promocash']){
  out[q]={};
  for(const flag of [0,1,2]){const r=await search(q,flag),d=r.elements.filter(direct);out[q][flag]={status:r.status,total:r.elements.length,direct:d.length,privateCounts:Object.fromEntries([...new Set(d.map(e=>String(e?.bPoolPrive)))].map(k=>[k,d.filter(e=>String(e?.bPoolPrive)===k).length])),sample:d.slice(0,8).map(summary)};}
}
console.log(JSON.stringify(out,null,2));await browser.close();
