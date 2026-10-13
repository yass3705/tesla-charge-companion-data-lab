// Bounded, read-only Electroverse UK pilot. No prices are promoted by this script.
import fs from 'node:fs/promises';
import zlib from 'node:zlib';
import {DirectElectroverseClient,SINGLE_LOCATION_QUERY} from './lib/electroverse_direct_client.mjs';

const OUT=process.env.PILOT_REPORT||'reports/emsp-pilots/electroverse-uk-cpo.json';
const Z=18, MAX_IDS=80, MAX_NEARBY=12, MAX_REQUESTS=100;
const client=new DirectElectroverseClient({timeoutMs:30000});
const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const norm=s=>String(s||'').toUpperCase().replace(/[^A-Z0-9]/g,'');
const readGz=async file=>JSON.parse(zlib.gunzipSync(await fs.readFile(file)));
const sources=[
  {file:'data/national/uk_source_ev_pcpr_v9.json.gz',name:'Source EV',id:'milton_gate_ev_hub'},
  {file:'data/national/uk_allego_uk_pcpr_v9.json.gz',name:'Allego UK',id:'GBLOC000116'},
  {file:'data/national/uk_validated_open_feeds.json.gz',name:'MFG EV Power',id:'3'},
];
function varint(b,p){let v=0,shift=0,x;do{if(p>=b.length)throw Error('truncated varint');x=b[p++];v+=(x&127)*2**shift;shift+=7;if(shift>56)throw Error('long varint');}while(x&128);return[v,p];}
function fields(b){const out=[];let p=0;while(p<b.length){let tag;[tag,p]=varint(b,p);const key=tag>>3,wire=tag&7;if(wire===2){let n;[n,p]=varint(b,p);if(p+n>b.length)throw Error('truncated field');out.push({key,wire,data:b.slice(p,p+n)});p+=n;}else if(wire===0){let v;[v,p]=varint(b,p);out.push({key,wire,value:v});}else if(wire===5)p+=4;else if(wire===1)p+=8;else throw Error('unsupported wire');}return out;}
const decoder=new TextDecoder();
function tileIds(b){const ids=[];for(const layer of fields(b).filter(x=>x.key===3&&x.wire===2)){const f=fields(layer.data),name=f.find(x=>x.key===1)?.data;if(!name||decoder.decode(name)!=='hits')continue;const keys=f.filter(x=>x.key===3).map(x=>decoder.decode(x.data));const vals=f.filter(x=>x.key===4).map(x=>{const v=fields(x.data).find(y=>[1,4,5,7].includes(y.key));return v?.wire===2?decoder.decode(v.data):v?.value;});for(const feature of f.filter(x=>x.key===2)){const packed=fields(feature.data).find(x=>x.key===2)?.data;if(!packed)continue;let p=0;while(p<packed.length){let ki,vi;[ki,p]=varint(packed,p);[vi,p]=varint(packed,p);if(keys[ki]==='_id'&&vals[vi]!=null){ids.push(String(vals[vi]));break;}}}}return [...new Set(ids)];}
function xy(lat,lon){const n=2**Z,r=lat*Math.PI/180;return[Math.floor((lon+180)/360*n),Math.floor((1-Math.asinh(Math.tan(r))/Math.PI)/2*n)];}
function distanceM(a,b){const lat=Number(b?.latitude??b?.lat),lon=Number(b?.longitude??b?.lon);return Number.isFinite(lat)&&Number.isFinite(lon)?Math.round(111195*Math.hypot(a.lat-lat,(a.lon-lon)*Math.cos(a.lat*Math.PI/180))):null;}
let requests=0;
async function graphql(query,variables={}){if(++requests>MAX_REQUESTS)throw Error('request cap exceeded');const r=await client.request(query,variables,{attempts:1});if(r.status!==200||r.json?.errors?.length||!r.json?.data)throw Error(`GraphQL status ${r.status}: ${(r.json?.errors||[]).map(x=>x.message).join(';').slice(0,100)}`);return r.json.data;}
async function target(spec){
  const data=await readGz(spec.file),source=(data.sources||[]).find(x=>x.name===spec.name);
  if(!source)throw Error('missing source '+spec.name);
  const loc=(source.locations||[]).find(x=>String(x.id)===spec.id);
  if(!loc||loc.publish!==true)throw Error('missing/public target '+spec.id);
  const point={lat:Number(loc.coordinates?.latitude),lon:Number(loc.coordinates?.longitude)};
  if(!Number.isFinite(point.lat)||!Number.isFinite(point.lon))throw Error('target coordinates invalid');
  const cpoEvses=new Map((loc.evses||[]).filter(e=>['AVAILABLE','CHARGING'].includes(e.status)).map(e=>[norm(e.evse_id),e]));
  const [cx,cy]=xy(point.lat,point.lon),ids=new Set(),tileCounts=[];
  for(let dx=-1;dx<=1;dx++)for(let dy=-1;dy<=1;dy++){
    const x=cx+dx,y=cy+dy,url=`https://api.electroverse.com/rest/locations/tiles/elastic/${Z}/${x}/${y}`;
    if(++requests>MAX_REQUESTS)throw Error('request cap exceeded');
    const response=await fetch(url,{headers:client.headers(),signal:AbortSignal.timeout(30000)});
    if(!response.ok)throw Error(`tile HTTP ${response.status} at ${Z}/${x}/${y}`);
    const tile=tileIds(new Uint8Array(await response.arrayBuffer()));tileCounts.push(tile.length);for(const id of tile)ids.add(id);
  }
  if(ids.size>MAX_IDS)throw Error(`candidate cap exceeded: ${ids.size}`);
  const nearby=[];
  for(let i=0;i<[...ids].length;i+=5){
    const batch=[...ids].sort().slice(i,i+5);
    const query=`query Pilot { ${batch.map((pk,j)=>`s${j}:chargingLocation(pk:${JSON.stringify(pk)}){chargingLocationPk name coordinates operator{name}}`).join(' ')} }`;
    const data=await graphql(query);
    for(let j=0;j<batch.length;j++){const v=data[`s${j}`],distance=v&&distanceM(point,v.coordinates);if(distance!=null&&distance<=120)nearby.push({pk:batch[j],distanceM:distance,name:v.name,operator:v.operator?.name});}
    await pause(350);
  }
  nearby.sort((a,b)=>a.distanceM-b.distanceM);
  if(nearby.length>MAX_NEARBY)throw Error(`nearby cap exceeded: ${nearby.length}`);
  const matches=[];
  for(const candidate of nearby){
    const detail=(await graphql(SINGLE_LOCATION_QUERY,{pk:candidate.pk})).chargingLocation;
    for(const edge of detail?.evses?.edges||[]){
      const evse=edge.node,key=norm(evse?.physicalReference),cpo=cpoEvses.get(key);
      if(!key||!cpo)continue;
      const connectors=(evse.connectors?.edges||[]).map(x=>x.node).filter(Boolean);
      matches.push({electroversePk:candidate.pk,distanceM:candidate.distanceM,cpoEvseId:cpo.evse_id,sourceEvsePk:evse.pk,
        cpoStatus:cpo.status,electroverseStatus:evse.status,
        cpoConnectorCount:(cpo.connectors||[]).length,electroverseConnectorCount:connectors.length,
        electroversePricing:connectors.map(c=>({pk:c.pk,kilowatts:c.kilowatts,standard:c.standard?.name||null,
          priceComponents:c.priceComponents||[],complexPricingDetail:c.complexPricingDetail||null}))});
    }
    await pause(350);
  }
  const duplicateMatches=[...new Set(matches.map(x=>x.cpoEvseId))].filter(id=>matches.filter(x=>x.cpoEvseId===id).length>1);
  return {cpo:spec.name,cpoLocationId:loc.id,cpoEvseCount:cpoEvses.size,tileCounts,candidatePkCount:ids.size,nearbyCount:nearby.length,
    exactEvseMatches:matches.length,duplicateMatches,matchingProof:'normalized exact EVSE ID, distance <=120m; no tariff promotion',matches};
}
const report={generatedAt:new Date().toISOString(),scope:'GB three CPO sites',requests:0,targets:[],errors:[]};
for(const spec of sources){try{report.targets.push(await target(spec));}catch(error){report.errors.push({cpo:spec.name,message:String(error).slice(0,180)});}}
report.requests=requests;
await fs.mkdir('reports/emsp-pilots',{recursive:true});await fs.writeFile(OUT,JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify({generatedAt:report.generatedAt,requests,targets:report.targets.map(({cpo,candidatePkCount,nearbyCount,exactEvseMatches,duplicateMatches})=>({cpo,candidatePkCount,nearbyCount,exactEvseMatches,duplicateMatches})),errors:report.errors}));
if(report.errors.length)process.exitCode=2;
