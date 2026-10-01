import fs from 'node:fs/promises';
import zlib from 'node:zlib';

const CACHE='data/electroverse/tariff_cache';
const manifest=JSON.parse(await fs.readFile(CACHE+'/manifest.json','utf8'));
const mapping=JSON.parse(await fs.readFile('data/electroverse/irve_location_mapping.json','utf8'));
const driveco=JSON.parse(await fs.readFile('data/operator_direct/driveco_evse_tariffs.json','utf8'));
const OVERLAY='data/platforms/electroverse/france-evse';
const overlayManifest=JSON.parse(await fs.readFile(OVERLAY+'/manifest.json','utf8'));

const norm=x=>String(x??'').trim().toUpperCase().replace(/[^A-Z0-9]/g,'');
const kwClass=n=>{
  n=Number(n); if(!Number.isFinite(n))return null;
  if(Math.abs(n-22.08)<=1.0 || Math.abs(n-22)<=1.0)return 22;
  if(Math.abs(n-50)<=2)return 50;
  if(Math.abs(n-100)<=3)return 100;
  if(Math.abs(n-150)<=4)return 150;
  if(Math.abs(n-180)<=5)return 180;
  if(Math.abs(n-200)<=5)return 200;
  return Math.round(n);
};
const sigConnector=c=>JSON.stringify({
  priceComponents:c?.priceComponents??null,
  complexPricingDetail:c?.complexPricingDetail??null,
  isChargingFree:c?.isChargingFree??null
});
const byPk=new Map((mapping.mappings||[]).map(m=>[String(m.electroverseLocationPk),m]));
const native=[...(driveco.resolved||[]),...(driveco.unresolved||[])];
const nativeByEvse=new Map(native.map(x=>[norm(x.evseId),x]));
const published=new Set();
for(const t of overlayManifest.tiles||[]){
  const gz=await fs.readFile(OVERLAY+'/'+t.file);
  const p=JSON.parse(zlib.gunzipSync(gz).toString('utf8'));
  for(const o of p.emspOffers||[])for(const id of o.evseIds||[])published.add(norm(id));
}
const globalPdcOwners=new Map();
for(const m of mapping.mappings||[])for(const p of m.irvePdcIds||[]){
  const k=norm(p);if(!k)continue;
  const s=globalPdcOwners.get(k)||new Set();s.add(m.irveStationId);globalPdcOwners.set(k,s);
}

const out={generatedAt:new Date().toISOString(),locations:0,candidateLocations:0,candidateTargets:0,byKw:{},rejects:{},samples:[]};
const rej=k=>out.rejects[k]=(out.rejects[k]||0)+1;

for(const sh of manifest.shards||[]){
  const data=JSON.parse(await fs.readFile(CACHE+'/'+sh.file,'utf8'));
  for(const row of Object.values(data.stations||{})){
    const m=byPk.get(String(row.electroverseLocationPk));if(!m)continue;
    const local=[...new Set((m.irvePdcIds||row.irvePdcIds||[]).map(norm).filter(Boolean))];
    const missing=local.filter(p=>p.startsWith('FRDRVE')&&!published.has(p));
    if(!missing.length)continue;
    out.locations++;

    const targetsByKw=new Map();
    let targetBad=false;
    for(const p of missing){
      const n=nativeByEvse.get(p);
      if(!n){targetBad=true;break;}
      const k=kwClass(n.powerKw);
      if(k==null||(globalPdcOwners.get(p)?.size||0)!==1){targetBad=true;break;}
      const arr=targetsByKw.get(k)||[];arr.push(p);targetsByKw.set(k,arr);
    }
    if(targetBad){rej('missing_native_power_or_nonunique_target');continue;}

    const srcByKw=new Map();
    for(const e of row.tariff?.evses||[]){
      const raw=String(e?.physicalReference??'').trim();if(!raw)continue;
      const k0=norm(raw);
      if(local.includes(k0)||published.has(k0))continue;
      if(!/^#\d{2}$/.test(raw))continue;
      const con=e.connectors||[];
      if(!con.length)continue;
      const k=kwClass(Math.max(...con.map(c=>Number(c.kilowatts)||0)));
      if(k==null)continue;
      const evseSigs=[...new Set(con.map(sigConnector))];
      if(evseSigs.length!==1)continue;
      const arr=srcByKw.get(k)||[];arr.push({e,raw,sig:evseSigs[0]});srcByKw.set(k,arr);
    }

    const groups=[];
    for(const [k,targets] of targetsByKw){
      const src=srcByKw.get(k)||[];
      if(!src.length){continue;}
      if(src.length!==targets.length){continue;}
      const sigs=new Set(src.map(x=>x.sig));
      if(sigs.size!==1){continue;}
      groups.push({kw:k,targets,refs:src.map(x=>x.raw),sig:[...sigs][0]});
    }
    if(!groups.length){rej('no_exact_homogeneous_power_group');continue;}
    const targets=groups.reduce((n,g)=>n+g.targets.length,0);
    out.candidateLocations++;
    out.candidateTargets+=targets;
    for(const g of groups)out.byKw[g.kw]=(out.byKw[g.kw]||0)+g.targets.length;
    if(out.samples.length<30)out.samples.push({locationPk:String(row.electroverseLocationPk),groups});
  }
}
await fs.mkdir('reports',{recursive:true});
await fs.writeFile('reports/electroverse-fr-drv-power-group-audit.json',JSON.stringify(out,null,2)+'\n');
console.log(JSON.stringify(out,null,2));
