import fs from 'node:fs/promises';
import zlib from 'node:zlib';

const CACHE='data/electroverse/tariff_cache';
const MANIFEST=CACHE+'/manifest.json';
const MAP='data/electroverse/irve_location_mapping.json';
const OVERLAY='data/platforms/electroverse/france-evse';
const OUT='reports/electroverse-fr-via-55c-structured-residual.json';

const norm=x=>String(x??'').trim().toUpperCase().replace(/[^A-Z0-9]/g,'');
const txt=x=>String(x??'').trim();

const mapping=JSON.parse(await fs.readFile(MAP,'utf8'));
const manifest=JSON.parse(await fs.readFile(MANIFEST,'utf8'));
const overlayManifest=JSON.parse(await fs.readFile(OVERLAY+'/manifest.json','utf8'));
const byPk=new Map((mapping.mappings||[]).map(m=>[String(m.electroverseLocationPk),m]));
const globalPdcOwners=new Map();
for(const m of mapping.mappings||[])for(const p of m.irvePdcIds||[]){
  const k=norm(p); if(!k)continue;
  const s=globalPdcOwners.get(k)||new Set(); s.add(m.irveStationId); globalPdcOwners.set(k,s);
}
const published=new Set();
for(const t of overlayManifest.tiles||[]){
  const gz=await fs.readFile(OVERLAY+'/'+t.file);
  const p=JSON.parse(zlib.gunzipSync(gz).toString('utf8'));
  for(const o of p.emspOffers||[])for(const id of o.evseIds||[])published.add(norm(id));
}

const report={
  generatedAt:new Date().toISOString(),
  via:{locations:0,candidateLocations:0,candidateTargets:0,samples:[]},
  c55:{locations:0,candidateLocations:0,candidateTargets:0,samples:[]}
};

for(const sh of manifest.shards||[]){
  const data=JSON.parse(await fs.readFile(CACHE+'/'+sh.file,'utf8'));
  for(const row of Object.values(data.stations||{})){
    const m=byPk.get(String(row.electroverseLocationPk)); if(!m)continue;
    const local=[...new Set((m.irvePdcIds||row.irvePdcIds||[]).map(norm).filter(Boolean))];
    const missing=local.filter(p=>!published.has(p));
    if(!missing.length)continue;
    const unresolved=(row.tariff?.evses||[]).map(e=>({e,raw:txt(e?.physicalReference),k:norm(e?.physicalReference)}))
      .filter(x=>x.raw && !local.includes(x.k) && !published.has(x.k));

    if(missing.some(p=>p.startsWith('FRVIAE'))){
      report.via.locations++;
      const viaMissing=missing.filter(p=>p.startsWith('FRVIAE'));
      const viaUnresolved=unresolved.filter(x=>{
        const r=x.raw;
        return /-\d{2}(?:-\d)?$/.test(r);
      });
      const byStem=new Map();
      for(const x of viaUnresolved){
        let mm=x.raw.match(/^(.*?)-(\d{2})-(\d)$/);
        let kind='nested',g=null,c=null,n=null,stem=null;
        if(mm){stem=norm(mm[1]);g=Number(mm[2]);c=Number(mm[3]);}
        else{
          mm=x.raw.match(/^(.*?)-(\d{2})$/);
          if(!mm)continue;
          kind='flat';stem=norm(mm[1]);n=Number(mm[2]);
        }
        const arr=byStem.get(stem)||[];arr.push({...x,kind,g,c,n});byStem.set(stem,arr);
      }
      const groups=[];
      for(const [stem,items] of byStem){
        const flat=items.every(x=>x.kind==='flat');
        const nested=items.every(x=>x.kind==='nested');
        if(!flat&&!nested)continue;
        const candidates=[];
        for(const width of [3,4]){
          const byPrefix=new Map();
          for(const p of viaMissing){
            if(p.length<=width)continue;
            const tail=p.slice(-width);
            if(!/^\d+$/.test(tail))continue;
            const prefix=p.slice(0,-width);
            const arr=byPrefix.get(prefix)||[];arr.push({p,tail});byPrefix.set(prefix,arr);
          }
          for(const rows of byPrefix.values()){
            if(rows.some(r=>(globalPdcOwners.get(r.p)?.size||0)!==1))continue;
            const map=new Map();
            let ok=true;
            if(flat){
              for(const r of rows){
                const tail=r.tail.padStart(3,'0');
                const g=Number(tail.slice(-3,-1)), c=Number(tail.slice(-1));
                if(!Number.isFinite(g)||!Number.isFinite(c)||g<1||c<1)continue;
                const n=(g-1)*2+c;
                if(map.has(n)){ok=false;break;}
                map.set(n,r.p);
              }
              const wanted=[...new Set(items.map(x=>x.n))].sort((a,b)=>a-b);
              if(!ok||map.size!==wanted.length||wanted.some(n=>!map.has(n)))continue;
            }else{
              for(const r of rows){
                const tail=r.tail.padStart(3,'0');
                const g=Number(tail.slice(-3,-1)), c=Number(tail.slice(-1));
                const key=`${g}:${c}`;
                if(map.has(key)){ok=false;break;}
                map.set(key,r.p);
              }
              const wanted=[...new Set(items.map(x=>`${x.g}:${x.c}`))];
              if(!ok||map.size!==wanted.length||wanted.some(k=>!map.has(k)))continue;
            }
            candidates.push({width,rows,map});
          }
        }
        if(candidates.length!==1)continue;
        const cand=candidates[0];
        groups.push({stem,count:items.length,kind:items[0].kind,targetCount:cand.rows.length});
      }
      const candidateTargets=groups.reduce((n,g)=>n+g.targetCount,0);
      if(candidateTargets){
        report.via.candidateLocations++;
        report.via.candidateTargets+=candidateTargets;
        if(report.via.samples.length<20)report.via.samples.push({
          locationPk:String(row.electroverseLocationPk),
          missingPdcs:viaMissing,
          refs:viaUnresolved.map(x=>x.raw),
          groups
        });
      }
    }

    if(missing.some(p=>p.startsWith('FR55CE'))){
      report.c55.locations++;
      const p55=missing.filter(p=>p.startsWith('FR55CE'));
      const brefs=unresolved.map(x=>{
        const m=x.raw.match(/^B(\d{2})(?:\b|\s|-)/i) || x.raw.match(/^B(\d{2})$/i);
        return m?{...x,n:Number(m[1])}:null;
      }).filter(Boolean);
      if(brefs.length){
        const uniqueNs=[...new Set(brefs.map(x=>x.n))].sort((a,b)=>a-b);
        if(uniqueNs.length===brefs.length){
          const suffixRows=[];
          for(const p of p55){
            const tail=p.slice(-1);
            const alphabet='0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ';
            const idx=alphabet.indexOf(tail);
            if(idx<0)continue;
            suffixRows.push({p,idx});
          }
          const expected=uniqueNs.map(n=>n-1);
          const exact=suffixRows.length===expected.length &&
            suffixRows.every(r=>(globalPdcOwners.get(r.p)?.size||0)===1) &&
            expected.every(i=>suffixRows.some(r=>r.idx===i));
          if(exact){
            report.c55.candidateLocations++;
            report.c55.candidateTargets+=suffixRows.length;
            if(report.c55.samples.length<20)report.c55.samples.push({
              locationPk:String(row.electroverseLocationPk),
              missingPdcs:p55,refs:brefs.map(x=>x.raw),indices:uniqueNs
            });
          }
        }
      }
    }
  }
}
await fs.mkdir('reports',{recursive:true});
await fs.writeFile(OUT,JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify(report,null,2));
