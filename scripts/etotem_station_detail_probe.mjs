import fs from 'fs';
import { chromium } from 'playwright-core';

const outPath='data/national/etotem_station_detail_probe.json';
const target='https://www.e-totem.fr/#/home/ou_se_recharger';
const browser=await chromium.launch({headless:true,executablePath:'/usr/bin/google-chrome',args:['--no-sandbox']});
const page=await browser.newPage({locale:'fr-FR',viewport:{width:1440,height:1000}});
const events=[];
const interesting=/(\/api\/|e-totem)/i;
let stationsRequestHeaders=null;
let anonymousBody=null;

page.on('request', req=>{
  const u=req.url();
  if(interesting.test(u) && ['xhr','fetch'].includes(req.resourceType())) {
    const ev={kind:'request',method:req.method(),resourceType:req.resourceType(),url:u,headers:req.headers(),postData:(req.postData()||'').slice(0,8000)};
    events.push(ev);
    if(u.includes('/api/Stations?')) stationsRequestHeaders=req.headers();
  }
});
page.on('response', async res=>{
  const req=res.request(),u=res.url();
  if(!(interesting.test(u) && ['xhr','fetch'].includes(req.resourceType()))) return;
  let body='';
  try{body=(await res.text()).slice(0,100000);}catch{}
  events.push({kind:'response',status:res.status(),resourceType:req.resourceType(),url:u,headers:res.headers(),body});
  if(u.includes('/api/ConnexionAnonyme')) anonymousBody=body;
});

await page.goto(target,{waitUntil:'domcontentloaded',timeout:60000});
await page.waitForTimeout(18000);

// Reuse the exact headers the app itself used for its public anonymous Stations request.
let directResults={};
if(stationsRequestHeaders){
  directResults=await page.evaluate(async ({headers})=>{
    const keep={};
    for(const [k,v] of Object.entries(headers||{})){
      const lk=k.toLowerCase();
      if(!['host','content-length','origin','referer','sec-fetch-dest','sec-fetch-mode','sec-fetch-site','user-agent'].includes(lk)) keep[k]=v;
    }
    const requests={};
    const urls={
      unclusterFrance:'/api/Stations?fLatSudOuest=41.0&fLongSudOuest=-6.0&fLatNordEst=51.5&fLongNordEst=10.5&bUniquementBornesDisponibles=false&bCompatibleAutocharge=0&nZoom=12&bNePasClusteriser=1&nBornesPrivees=0&bRecupererBorneLaPlusProche=0',
      mane:'/api/Stations?fLatSudOuest=43.05&fLongSudOuest=0.82&fLatNordEst=43.15&fLongNordEst=0.98&bUniquementBornesDisponibles=false&bCompatibleAutocharge=0&nZoom=16&bNePasClusteriser=1&nBornesPrivees=0&bRecupererBorneLaPlusProche=0'
    };
    for(const [name,url] of Object.entries(urls)){
      try{const r=await fetch(url,{headers:keep});requests[name]={status:r.status,text:(await r.text()).slice(0,200000)}}catch(e){requests[name]={error:String(e)}}
    }
    return {headers:keep,requests};
  },{headers:stationsRequestHeaders});
}

const result={target,finalUrl:page.url(),anonymousBody,stationsRequestHeaders,directResults,events};
fs.mkdirSync('data/national',{recursive:true});
fs.writeFileSync(outPath,JSON.stringify(result,null,2));
console.log(JSON.stringify({eventCount:events.length,hasStationsHeaders:!!stationsRequestHeaders,direct:Object.fromEntries(Object.entries(directResults.requests||{}).map(([k,v])=>[k,{status:v.status,length:(v.text||'').length,error:v.error}]))},null,2));
for(const [k,v] of Object.entries(directResults.requests||{})){console.log('\n###',k,'STATUS',v.status,'\n',String(v.text||v.error||'').slice(0,20000));}
await browser.close();
