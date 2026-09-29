import fs from 'node:fs/promises';

const API_KEY=process.env.ELECTROVERSE_API_KEY;
if(!API_KEY) throw new Error('ELECTROVERSE_API_KEY required');
const Z=Number(process.env.ELECTROVERSE_INVENTORY_ZOOM||9);
const CONCURRENCY=Number(process.env.ELECTROVERSE_TILE_CONCURRENCY||8);

const COUNTRY=process.env.COUNTRY||'DE';
const BOXES={
  DE:[{name:'germany',minLon:5.5,maxLon:15.6,minLat:47.0,maxLat:55.2}],
  GB:[{name:'great_britain',minLon:-8.8,maxLon:2.2,minLat:49.8,maxLat:59.0},{name:'northern_ireland',minLon:-8.3,maxLon:-5.3,minLat:54.0,maxLat:55.4}]
};
const regions=BOXES[COUNTRY];
if(!regions) throw new Error('unsupported COUNTRY '+COUNTRY);

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
      for(let i=0;i+1<idx.length;i+=2){if(keys[idx[i]]==='_id'){const v=vals[idx[i+1]];if(v!==null&&v!==undefined)ids.push(String(v));break}}
    }
  }
  return [...new Set(ids)];
}

const tileMap=new Map();
for(const r of regions){
  const x1=lon2x(r.minLon,Z),x2=lon2x(r.maxLon,Z),y1=lat2y(r.maxLat,Z),y2=lat2y(r.minLat,Z);
  for(let x=x1;x<=x2;x++)for(let y=y1;y<=y2;y++)tileMap.set(`${Z}/${x}/${y}`,{z:Z,x,y,region:r.name});
}
const tiles=[...tileMap.values()];
let cursor=0, failed=[], all=[];
async function worker(){
  while(true){
    const i=cursor++;if(i>=tiles.length)return;
    const t=tiles[i];
    try{
      const url=`https://api.electroverse.com/rest/locations/tiles/elastic/${t.z}/${t.x}/${t.y}`;
      const r=await fetch(url,{headers:{'Api-Key':API_KEY,source:'android','X-App-Version':'2026.09.08'}});
      if(!r.ok) throw new Error('HTTP '+r.status);
      all.push(...tileIds(new Uint8Array(await r.arrayBuffer())));
    }catch(error){failed.push({tile:`${t.z}/${t.x}/${t.y}`,error:error instanceof Error?error.message:String(error)})}
  }
}
const t0=Date.now();
await Promise.all(Array.from({length:Math.min(CONCURRENCY,tiles.length)},()=>worker()));
const ids=[...new Set(all)].sort((a,b)=>a.localeCompare(b));
const report={generatedAt:new Date().toISOString(),country:COUNTRY,zoom:Z,tileCount:tiles.length,failedTileCount:failed.length,inventoryCount:ids.length,elapsedSeconds:Number(((Date.now()-t0)/1000).toFixed(2)),failedTiles:failed,ids};
await fs.mkdir('reports/electroverse',{recursive:true});
await fs.writeFile(`reports/electroverse/inventory-${COUNTRY.toLowerCase()}.json`,JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify({...report,ids:ids.slice(0,20)},null,2));
