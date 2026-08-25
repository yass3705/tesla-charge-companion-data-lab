import fs from 'fs';
import { chromium } from 'playwright-core';

const outPath = 'data/national/etotem_network_probe.json';
const target = 'https://www.e-totem.fr/#/home/ou_se_recharger';
const browser = await chromium.launch({headless:true, executablePath:'/usr/bin/google-chrome', args:['--no-sandbox']});
const page = await browser.newPage({locale:'fr-FR', viewport:{width:1440,height:1000}});
const events=[];
const interesting = /(e-totem|etotem|api|borne|station|pool|tarif|charge|pdc|ocpi)/i;

page.on('request', req => {
  const u=req.url();
  if (!u.startsWith('data:') && (interesting.test(u) || ['xhr','fetch'].includes(req.resourceType()))) {
    events.push({kind:'request', method:req.method(), resourceType:req.resourceType(), url:u, postData:(req.postData()||'').slice(0,4000)});
  }
});
page.on('response', async res => {
  const req=res.request(); const u=res.url();
  if (!(interesting.test(u) || ['xhr','fetch'].includes(req.resourceType()))) return;
  const ct=(res.headers()['content-type']||'').toLowerCase();
  let body=null;
  if (ct.includes('json') || ct.includes('text') || ['xhr','fetch'].includes(req.resourceType())) {
    try { body=(await res.text()).slice(0,30000); } catch {}
  }
  events.push({kind:'response', status:res.status(), resourceType:req.resourceType(), url:u, contentType:ct, body});
});

let pageError=null;
try {
  await page.goto(target,{waitUntil:'domcontentloaded',timeout:60000});
  await page.waitForTimeout(18000);
} catch(e) { pageError=String(e); }

const texts = await page.locator('body').innerText().catch(()=> '');
const result={target, finalUrl:page.url(), title:await page.title().catch(()=>''), pageError, bodyText:texts.slice(0,30000), events};
fs.mkdirSync('data/national',{recursive:true});
fs.writeFileSync(outPath,JSON.stringify(result,null,2));
console.log(JSON.stringify({target:result.target,finalUrl:result.finalUrl,title:result.title,pageError,eventCount:events.length},null,2));
for (const ev of events) {
  console.log(ev.kind.toUpperCase(), ev.status||'', ev.method||'', ev.resourceType, ev.url);
  if (ev.postData) console.log('POSTDATA',ev.postData.slice(0,1000));
  if (ev.body && (interesting.test(ev.body) || ev.contentType.includes('json'))) console.log('BODY',ev.body.slice(0,5000));
}
await browser.close();
