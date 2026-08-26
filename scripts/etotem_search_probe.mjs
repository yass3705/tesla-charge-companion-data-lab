import { chromium } from 'playwright-core';

const browser=await chromium.launch({headless:true,executablePath:'/usr/bin/google-chrome',args:['--no-sandbox']});
const page=await browser.newPage({locale:'fr-FR',viewport:{width:1280,height:900}});
await page.goto('https://www.e-totem.fr/',{waitUntil:'domcontentloaded',timeout:60000});

const result=await page.evaluate(async()=>{
  const out={};
  async function call(name,url){
    const ctl=new AbortController(),timer=setTimeout(()=>ctl.abort(),25000);
    try{
      const r=await fetch(url,{credentials:'include',cache:'no-store',signal:ctl.signal});
      const text=await r.text();let json=null;try{json=JSON.parse(text);}catch{}
      const elements=Array.isArray(json?.aElements)?json.aElements:[];
      const direct=elements.filter(e=>String(e?.bOcpi??0)==='0'&&String(e?.bGireve??0)==='0'&&String(e?.bItinerance??0)==='0');
      out[name]={status:r.status,length:text.length,count:elements.length,directCount:direct.length,tariffCount:direct.filter(e=>String(e?.sWebTexte||'').trim()).length,prefixes:[...new Set(direct.map(e=>String(e?.sIdPool||'').replace(/\*/g,'').slice(0,5)).filter(Boolean))].slice(0,30),sample:direct.slice(0,5).map(e=>({sIdPool:e?.sIdPool,sLibelle:e?.sLibelle,nIdPool:e?.nIdPool,hasTariff:!!String(e?.sWebTexte||'').trim()}))};
    }catch(e){out[name]={error:String(e)};}finally{clearTimeout(timer);}
  }
  const qs=t=>'/api/Stations?sLibelleBorne='+encodeURIComponent(t)+'&bUniquementBornesDisponibles=false&bNePasClusteriser=1&nBornesPrivees=0';
  await call('searchEtotem',qs('e-Totem'));
  await call('searchIntermarche',qs('INTERMARCHE'));
  await call('searchSaintEtienne',qs('SAINT ETIENNE'));
  await call('searchCarrefour',qs('CARREFOUR'));
  await call('searchSuperU',qs('SUPER U'));
  await call('searchMane',qs('INTERMARCHE MANE'));
  return out;
});
console.log(JSON.stringify(result,null,2));
await browser.close();
