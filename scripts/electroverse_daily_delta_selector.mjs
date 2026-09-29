import fs from 'node:fs/promises';

const API_KEY=process.env.ELECTROVERSE_API_KEY;
if(!API_KEY) throw new Error('ELECTROVERSE_API_KEY required');

const Z=Number(process.env.ELECTROVERSE_INVENTORY_ZOOM||9);
const CONCURRENCY=Number(process.env.ELECTROVERSE_TILE_CONCURRENCY||8);
const SNAPSHOT='data/electroverse/inventory/france-current.json';
const REPORT='reports/electroverse/daily-delta.json';
const SELECTION='reports/electroverse/incremental-selection.json';
const MAPPING='data/electroverse/irve_location_mapping.json';
const CACHE_MANIFEST='data/electroverse/tariff_cache/manifest.json';
const FAILURE_REPORT='reports/electroverse/hybrid-refresh-failures.json';

const REGIONS=[
  {name:'metropolitan_france_corsica',minLon:-5.6,maxLon:10.0,minLat:41.0,maxLat:51.6},
  {name:'guadeloupe',minLon:-61.95,maxLon:-60.95,minLat:15.75,maxLat:16.65},
  {name:'martinique',minLon:-61.35,maxLon:-60.75,minLat:14.30,maxLat:14.95},
  {name:'guyane',minLon:-54.75,maxLon:-51.45,minLat:2.0,maxLat:5.95},
  {name:'reunion',minLon:55.10,maxLon:55.90,minLat:-21.55,maxLat:-20.75},
  {name:'mayotte',minLon:44.90,maxLon:45.40,minLat:-13.10,maxLat:-12.55},
  {name:'saint_pierre_miquelon',minLon:-56.55,maxLon:-55.90,minLat:46.70,maxLat:47.20},
  {name:'saint_martin_barthelemy',minLon:-63.20,maxLon:-62.75,minLat:17.80,maxLat:18.20},
];

function lon2x(lon,z){return Math.floor((lon+180)/360*2**z)}
function lat2y(lat,z){const r=lat*Math.PI/180;return Math.floor((1-Math.asinh(Math.tan(r))/Math.PI)/2*2**z)}
function varint(b,p){let v=0,s=0,x=0;do{x=b[p++];v+=(x&127)*2**s;s+=7;if(s>56)throw new Error('varint too long')}while(x&128);return[v,p]}
function fields(b,start=0,end=b.length){const out=[];let p=start;while(p<end){let t;[t,p]=varint(b,p);const n=t>>3,w=t&7;if(w===2){let l;[l,p]=varint(b,p);out.push({n,w,s:p,e:p+l});p+=l}else if(w===0){let v;const s=p;[v,p]=varint(b,p);out.push({n,w,s,e:p,v})}else if(w===5){out.push({n,w,s:p,e:p+4});p+=4}else if(w===1){out.push({n,w,s:p,e:p+8});p+=8}else throw new Error('unsupported wire '+w)}return out}
const dec=new TextDecoder();
function valueOf(vb){for(const f of fields(vb)){if(f.n===1&&f.w===2)return dec.decode(vb.slice(f.s,f.e));if((f.n===4||f.n===5||f.n===7)&&f.w===0)return f.v;if(f.n===6&&f.w===0)return (f.v>>>1)^-(f.v&1)}return null}
function tileIds(b){
  const ids=[];
  for(const lf of fields(b).filter(f=>f.n===3&&f.w===2)){
    const lb=b.slice(lf.s,lf.e), fs=fields(lb);
    const namef=fs.find(f=>f.n===1&&f.w===2), name=namef?dec.decode(lb.slice(namef.s,namef.e)):'';
    if(name!=='hits')continue;
    const keys=fs.filter(f=>f.n===3&&f.w===2).map(f=>dec.decode(lb.slice(f.s,f.e)));
    const vals=fs.filter(f=>f.n===4&&f.w===2).map(f=>valueOf(lb.slice(f.s,f.e)));
    for(const ff of fs.filter(f=>f.n===2&&f.w===2)){
      const fb=lb.slice(ff.s,ff.e), tf=fields(fb).find(f=>f.n===2&&f.w===2);if(!tf)continue;
      const packed=fb.slice(tf.s,tf.e), idx=[];let p=0;while(p<packed.length){let v;[v,p]=varint(packed,p);idx.push(v)}
      for(let i=0;i+1<idx.length;i+=2){
        if(keys[idx[i]]==='_id'){const v=vals[idx[i+1]];if(v!==null&&v!==undefined)ids.push(String(v));break}
      }
    }
  }
  return [...new Set(ids)];
}

const tileMap=new Map();
for(const r of REGIONS){
  const x1=lon2x(r.minLon,Z),x2=lon2x(r.maxLon,Z),y1=lat2y(r.maxLat,Z),y2=lat2y(r.minLat,Z);
  for(let x=x1;x<=x2;x++)for(let y=y1;y<=y2;y++)tileMap.set(`${Z}/${x}/${y}`,{z:Z,x,y,region:r.name});
}
const tiles=[...tileMap.values()];

let previous={tiles:{},allIds:[]};
try{previous=JSON.parse(await fs.readFile(SNAPSHOT,'utf8'))}catch{}
previous.tiles??={};

const results={},failedTiles=[];
let cursor=0;
async function worker(){
  while(true){
    const i=cursor++;if(i>=tiles.length)return;
    const t=tiles[i],k=`${t.z}/${t.x}/${t.y}`;
    try{
      const url=`https://api.electroverse.com/rest/locations/tiles/elastic/${t.z}/${t.x}/${t.y}`;
      const r=await fetch(url,{headers:{'Api-Key':API_KEY,source:'android','X-App-Version':'2026.09.08'}});
      if(!r.ok)throw new Error('HTTP '+r.status);
      results[k]={...t,ids:tileIds(new Uint8Array(await r.arrayBuffer()))};
    }catch(error){
      failedTiles.push({tile:k,error:error instanceof Error?error.message:String(error)});
      const prev=previous.tiles[k];
      results[k]={...t,ids:Array.isArray(prev?.ids)?prev.ids:[],carriedForward:true};
    }
  }
}
await Promise.all(Array.from({length:Math.min(CONCURRENCY,tiles.length)},()=>worker()));

const allIds=[...new Set(Object.values(results).flatMap(t=>t.ids||[]))].sort((a,b)=>a.localeCompare(b));
const baseline=!previous.generatedAt;
const prevIds=new Set(previous.allIds||[]);
const nowIds=new Set(allIds);
const newIds=baseline?[]:allIds.filter(id=>!prevIds.has(id));
const disappearedIds=[...prevIds].filter(id=>!nowIds.has(id));

const mapping=JSON.parse(await fs.readFile(MAPPING,'utf8'));
const mappingRows=mapping.mappings||[];
const mappedByPk=new Map(mappingRows.map(m=>[String(m.electroverseLocationPk),m]));
const mappedNewIds=newIds.filter(id=>mappedByPk.has(id));
const unmappedNewIds=newIds.filter(id=>!mappedByPk.has(id));

const manifest=JSON.parse(await fs.readFile(CACHE_MANIFEST,'utf8'));
const cached=new Set();
for(const sh of manifest.shards||[]){
  if(!sh.count)continue;
  const data=JSON.parse(await fs.readFile(`data/electroverse/tariff_cache/${sh.file}`,'utf8'));
  for(const pk of Object.keys(data.stations||{}))cached.add(String(pk));
}
const mappingNotCached=mappingRows.map(m=>String(m.electroverseLocationPk)).filter(pk=>!cached.has(pk));

let failureIds=[];
try{failureIds=(JSON.parse(await fs.readFile(FAILURE_REPORT,'utf8')).failures||[]).map(f=>String(f.pk)).filter(Boolean)}catch{}

const reasons=new Map();
for(const pk of mappedNewIds)reasons.set(pk,'new_tile_id_mapped');
for(const pk of mappingNotCached)reasons.set(pk,reasons.get(pk)||'mapping_not_cached');
for(const pk of failureIds)if(mappedByPk.has(pk))reasons.set(pk,reasons.get(pk)||'retry_failure');
const selected=[...reasons].map(([pk,reason])=>({pk,irveStationId:mappedByPk.get(pk)?.irveStationId||null,reason,ageHours:null}));

const generatedAt=new Date().toISOString();
await fs.mkdir('data/electroverse/inventory',{recursive:true});
await fs.mkdir('reports/electroverse',{recursive:true});
await fs.writeFile(SNAPSHOT,JSON.stringify({version:1,generatedAt,zoom:Z,tileCount:tiles.length,tiles:results,allIds},null,2)+'\n');
await fs.writeFile(REPORT,JSON.stringify({
  generatedAt,baseline,zoom:Z,tileCount:tiles.length,failedTileCount:failedTiles.length,failedTiles,
  inventoryCount:allIds.length,previousInventoryCount:(previous.allIds||[]).length,
  newIdCount:newIds.length,disappearedIdCount:disappearedIds.length,
  mappedNewCount:mappedNewIds.length,unmappedNewCount:unmappedNewIds.length,
  mappingNotCachedCount:mappingNotCached.length,retryFailureCount:failureIds.length,
  newIds,mappedNewIds,unmappedNewIds,disappearedIds
},null,2)+'\n');
await fs.writeFile(SELECTION,JSON.stringify({
  generatedAt,storage:'sharded-v1',policy:{mode:'daily_inventory_delta_plus_retries'},
  mappingPopulation:mappingRows.length,cachePopulation:cached.size,
  dueTotal:selected.length,selectedCount:selected.length,selected
},null,2)+'\n');
console.log(JSON.stringify({
  generatedAt,baseline,tileCount:tiles.length,failedTileCount:failedTiles.length,
  inventoryCount:allIds.length,newIdCount:newIds.length,mappedNewCount:mappedNewIds.length,
  unmappedNewCount:unmappedNewIds.length,mappingNotCachedCount:mappingNotCached.length,
  retryFailureCount:failureIds.length,selectedCount:selected.length
},null,2));
