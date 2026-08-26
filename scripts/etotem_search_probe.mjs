import { chromium } from 'playwright-core';

const browser=await chromium.launch({headless:true,executablePath:'/usr/bin/google-chrome',args:['--no-sandbox']});
const page=await browser.newPage({locale:'fr-FR',viewport:{width:1280,height:900}});
await page.goto('https://www.e-totem.fr/',{waitUntil:'domcontentloaded',timeout:60000});

const result=await page.evaluate(async()=>{
  const out={};
  async function call(name,url){
    const ctl=new AbortController(),timer=setTimeout(()=>ctl.abort(),20000);
    try{
      const r=await fetch(url,{credentials:'include',cache:'no-store',signal:ctl.signal});
      const text=await r.text();let json=null;try{json=JSON.parse(text);}catch{}
      const elements=Array.isArray(json?.aElements)?json.aElements:[];
      out[name]={status:r.status,length:text.length,count:elements.length,sample:elements.slice(0,5).map(e=>({sIdPool:e?.sIdPool,sIdPoolUnique:e?.sIdPoolUnique,sLibelle:e?.sLibelle,sOrigine:e?.sOrigine,nIdPool:e?.nIdPool,bOcpi:e?.bOcpi,bGireve:e?.bGireve,bItinerance:e?.bItinerance,hasTariff:!!String(e?.sWebTexte||'').trim()})),keys:json&&typeof json==='object'?Object.keys(json).slice(0,30):[]};
    }catch(e){out[name]={error:String(e)};}finally{clearTimeout(timer);}
  }
  await call('searchMane','/api/Stations?sLibelleBorne=INTERMARCHE%20MANE&bUniquementBornesDisponibles=false&bNePasClusteriser=1&nBornesPrivees=0');
  await call('selectsBornes','/api/SelectsBornes');
  await call('detailMane','/api/Stations/cpo_pool/601');
  return out;
});
console.log(JSON.stringify(result,null,2));
await browser.close();
