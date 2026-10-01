import fs from 'node:fs/promises';
import zlib from 'node:zlib';

const OPS=new Set(['P01','H01','SIP']);
const CACHE='data/electroverse/tariff_cache';
const MAP='data/electroverse/irve_location_mapping.json';
const OVERLAY='data/platforms/electroverse/france-evse';
const norm=x=>String(x??'').trim().toUpperCase().replace(/[^A-Z0-9]/g,'');
const txt=x=>String(x??'').trim();
const opFromRef=raw=>{const s=txt(raw),a=s.split('*').map(x=>x.trim()).filter(Boolean);return a.length>=2&&/^FR$/i.test(a[0])?a[1].toUpperCase():null;};

const mapping=JSON.parse(await fs.readFile(MAP,'utf8'));
const byPk=new Map((mapping.mappings||[]).map(m=>[String(m.electroverseLocationPk),m]));
const owners=new Map();
for(const m of mapping.mappings||[])for(const p of m.irvePdcIds||[]){const k=norm(p);if(!k)continue;const s=owners.get(k)||new Set();s.add(String(m.irveStationId??''));owners.set(k,s);}
const oman=JSON.parse(await fs.readFile(OVERLAY+'/manifest.json','utf8'));
const publishedSourcePks=new Set(),publishedTargets=new Set();
for(const t of oman.tiles||[]){const tile=JSON.parse(zlib.gunzipSync(await fs.readFile(OVERLAY+'/'+t.file)));for(const o of tile.emspOffers||[]){for(const pk of o?.metadata?.electroverseEvsePks||[])if(pk!=null)publishedSourcePks.add(String(pk));if(o?.metadata?.electroverseEvsePk!=null)publishedSourcePks.add(String(o.metadata.electroverseEvsePk));for(const id of o.evseIds||[])publishedTargets.add(norm(id));}}

const cman=JSON.parse(await fs.readFile(CACHE+'/manifest.json','utf8'));
const rep={};for(const op of OPS)rep[op]={operator:op,residual:0,locations:0,candidateGroups:0,candidateTargets:0,sourceEntriesCovered:0,samples:[]};
const psig=e=>JSON.stringify((e.connectors||[]).map(c=>({f:c?.isChargingFree??null,p:c?.priceComponents??null,x:c?.complexPricingDetail??null})));

for(const sh of cman.shards||[]){const data=JSON.parse(await fs.readFile(CACHE+'/'+sh.file,'utf8'));for(const row of Object.values(data.stations||{})){const m=byPk.get(String(row.electroverseLocationPk));const local=[...new Set((m?.irvePdcIds||row.irvePdcIds||[]).map(norm).filter(Boolean))];for(const op of OPS){const es=(row?.tariff?.evses||[]).filter(e=>e?.pk!=null&&!publishedSourcePks.has(String(e.pk))&&opFromRef(e?.physicalReference)===op);if(!es.length)continue;const r=rep[op];r.residual+=es.length;r.locations++;
const groups=new Map();
for(const e of es){const raw=txt(e.physicalReference);const mm=raw.match(/^FR\*([A-Z0-9]+)\*E(.+?)\*(\d+)\*(\d+)$/i);if(!mm)continue;const parent=norm('FR'+mm[1]+'E'+mm[2]),first=Number(mm[3]);const key=parent+'|'+first;const a=groups.get(key)||[];a.push({e,raw,parent,first,second:Number(mm[4])});groups.set(key,a);}
const accepted=[];
for(const items of groups.values()){const {parent,first}=items[0];const target=parent+String(first);if(!local.includes(target)||publishedTargets.has(target)||(owners.get(target)?.size||0)!==1)continue;const sigs=new Set(items.map(x=>psig(x.e)));if(sigs.size!==1)continue;accepted.push({target,items});}
if(accepted.length){r.candidateGroups+=accepted.length;r.candidateTargets+=accepted.length;r.sourceEntriesCovered+=accepted.reduce((n,g)=>n+g.items.length,0);if(r.samples.length<25)r.samples.push({locationPk:String(row.electroverseLocationPk),groups:accepted.slice(0,20).map(g=>({target:g.target,refs:g.items.map(x=>x.raw),sourcePks:g.items.map(x=>x.e.pk)}))});}
}}}
await fs.mkdir('reports/electroverse',{recursive:true});
for(const op of OPS){const out={schemaVersion:1,generatedAt:new Date().toISOString(),...rep[op],policy:'Diagnostic only: exact normalized parent + first ordinal target; target must be local, currently unpublished, globally unique; all grouped source entries must have identical pricing. No proximity/order inference.'};await fs.writeFile(`reports/electroverse/${op.toLowerCase()}-parent-first-ordinal.json`,JSON.stringify(out,null,2)+'\n');console.log(JSON.stringify(out,null,2));}
