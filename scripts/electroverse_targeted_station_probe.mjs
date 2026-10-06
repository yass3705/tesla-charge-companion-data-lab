import fs from 'node:fs/promises';
import {DirectElectroverseClient,SINGLE_LOCATION_QUERY} from './lib/electroverse_direct_client.mjs';

const targets=[
  {id:'electra-bois-d-arcy',lat:48.79955,lon:2.039,nationalIds:['FRELCP12954082','FRELCP5265355','FRELCPBDALE']},
  {id:'lidl-dole',lat:47.08248,lon:5.48995,nationalIds:['FRLDLPLFR3233EVCP']}
];
const client=new DirectElectroverseClient();
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
function varint(bytes,start){let n=0,shift=0,pos=start,byte;do{byte=bytes[pos++];n+=(byte&127)*2**shift;shift+=7;if(shift>56)throw Error('varint too long');}while(byte&128);return[n,pos]}
function fields(bytes){const out=[];let pos=0;while(pos<bytes.length){let tag;[tag,pos]=varint(bytes,pos);const wire=tag&7,key=tag>>3;if(wire===2){let size;[size,pos]=varint(bytes,pos);out.push({key,wire,data:bytes.slice(pos,pos+size)});pos+=size;}else if(wire===0){let value;[value,pos]=varint(bytes,pos);out.push({key,wire,value});}else if(wire===5)pos+=4;else if(wire===1)pos+=8;else throw Error('unsupported vector tile wire '+wire);}return out;}
const decoder=new TextDecoder();
function tileIds(bytes){const ids=[];for(const layer of fields(bytes).filter(x=>x.key===3&&x.wire===2)){const parts=fields(layer.data),name=parts.find(x=>x.key===1)?.data;if(!name||decoder.decode(name)!=='hits')continue;const keys=parts.filter(x=>x.key===3).map(x=>decoder.decode(x.data)),values=parts.filter(x=>x.key===4).map(x=>{const f=fields(x.data).find(v=>v.key===1||v.key===4||v.key===5||v.key===7);return f?.wire===2?decoder.decode(f.data):f?.value;});for(const feature of parts.filter(x=>x.key===2)){const tag=fields(feature.data).find(x=>x.key===2)?.data;if(!tag)continue;let pos=0;while(pos<tag.length){let ki,vi;[ki,pos]=varint(tag,pos);[vi,pos]=varint(tag,pos);if(keys[ki]==='_id'&&values[vi]!=null){ids.push(String(values[vi]));break;}}}}return [...new Set(ids)];}
function xy(lat,lon,z){const n=2**z,rad=lat*Math.PI/180;return[Math.floor((lon+180)/360*n),Math.floor((1-Math.asinh(Math.tan(rad))/Math.PI)/2*n)];}
function distanceM(a,b){const lat=Number(b?.latitude??b?.lat),lon=Number(b?.longitude??b?.lon);if(!Number.isFinite(lat)||!Number.isFinite(lon))return null;return Math.round(111195*Math.hypot(a.lat-lat,(a.lon-lon)*Math.cos(a.lat*Math.PI/180)));}
function projectedLocation(value){const loc=value?.json?.data?.chargingLocation;return loc||null;}
const mapping=JSON.parse(await fs.readFile('data/electroverse/irve_location_mapping.json','utf8'));
const mapped=new Map((mapping.mappings||[]).map(row=>[String(row.electroverseLocationPk),row]));
const report={generatedAt:new Date().toISOString(),targets:[],errors:[]};
for(const target of targets){
  const z=16,[cx,cy]=xy(target.lat,target.lon,z),ids=new Set(),tileCounts=[];
  for(let dx=-1;dx<=1;dx++)for(let dy=-1;dy<=1;dy++){
    const x=cx+dx,y=cy+dy,url=`https://api.electroverse.com/rest/locations/tiles/elastic/${z}/${x}/${y}`;
    const response=await fetch(url,{headers:client.headers()});
    if(!response.ok){report.errors.push({target:target.id,tile:`${z}/${x}/${y}`,status:response.status});continue;}
    const tile=tileIds(new Uint8Array(await response.arrayBuffer()));tileCounts.push({tile:`${z}/${x}/${y}`,count:tile.length});for(const id of tile)ids.add(id);
  }
  if(ids.size>250)throw Error(`${target.id}: ${ids.size} tile candidates exceeds safe bound`);
  const candidates=[],all=[...ids].sort();
  for(let index=0;index<all.length;index+=5){
    const batch=all.slice(index,index+5),query=`query Targeted { ${batch.map((pk,i)=>`s${i}:chargingLocation(pk:${JSON.stringify(pk)}){chargingLocationPk name address city coordinates operator{name}}`).join(' ')} }`;
    const response=await client.request(query,{}, {attempts:2});
    if(response.status!==200||response.json?.errors?.length){report.errors.push({target:target.id,batch,status:response.status,errors:(response.json?.errors||[]).map(e=>e.message)});continue;}
    for(const [i,pk] of batch.entries()){const loc=response.json?.data?.[`s${i}`];if(!loc)continue;const distance=distanceM(target,loc.coordinates);if(distance!=null&&distance<=250)candidates.push({pk,distanceM:distance,name:loc.name,address:loc.address,city:loc.city,coordinates:loc.coordinates,operator:loc.operator?.name,mapping:mapped.get(pk)||null});}
    await sleep(500);
  }
  candidates.sort((a,b)=>a.distanceM-b.distanceM);
  const near=candidates.filter(row=>row.distanceM<=100);
  for(const row of near){const result=await client.request(SINGLE_LOCATION_QUERY,{pk:row.pk},{attempts:2});const loc=projectedLocation(result);if(!loc){report.errors.push({target:target.id,pk:row.pk,status:result.status,errors:(result.json?.errors||[]).map(e=>e.message)});continue;}row.tariff={evses:(loc.evses?.edges||[]).map(edge=>({pk:edge.node?.pk,physicalReference:edge.node?.physicalReference,connectors:(edge.node?.connectors?.edges||[]).map(c=>c.node)}))};await sleep(500);}
  report.targets.push({id:target.id,nationalIds:target.nationalIds,tileCounts,candidateCount:all.length,nearby:candidates});
}
await fs.mkdir('reports/electroverse',{recursive:true});await fs.writeFile('reports/electroverse/targeted-station-probe.json',JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify({generatedAt:report.generatedAt,targets:report.targets.map(t=>({id:t.id,candidateCount:t.candidateCount,nearby:t.nearby.map(x=>({pk:x.pk,distanceM:x.distanceM,name:x.name,operator:x.operator,evses:x.tariff?.evses?.length||0}))})),errors:report.errors},null,2));
if(report.errors.length)process.exitCode=2;
