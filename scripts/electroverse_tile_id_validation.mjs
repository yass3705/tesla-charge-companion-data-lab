import fs from 'node:fs/promises';
const key=process.env.ELECTROVERSE_API_KEY;if(!key)throw new Error('ELECTROVERSE_API_KEY required');

function varint(b,p){let v=0,s=0,x=0;do{x=b[p++];v+=(x&127)*2**s;s+=7;if(s>56)throw new Error('varint too long')}while(x&128);return[v,p]}
function fields(b,start=0,end=b.length){const out=[];let p=start;while(p<end){let t;[t,p]=varint(b,p);const n=t>>3,w=t&7;if(w===2){let l;[l,p]=varint(b,p);out.push({n,w,s:p,e:p+l});p+=l}else if(w===0){const s=p;let v;[v,p]=varint(b,p);out.push({n,w,s,e:p,v})}else if(w===5){out.push({n,w,s:p,e:p+4});p+=4}else if(w===1){out.push({n,w,s:p,e:p+8});p+=8}else throw new Error('wire '+w)}return out}
const dec=new TextDecoder();
function valueOf(vb){
  for(const f of fields(vb)){
    if(f.n===1&&f.w===2)return dec.decode(vb.slice(f.s,f.e));
    if((f.n===4||f.n===5||f.n===7)&&f.w===0)return f.v;
    if(f.n===6&&f.w===0)return (f.v>>>1)^-(f.v&1);
  }
  return null;
}
function parseTile(b){
  const ids=[];
  for(const lf of fields(b).filter(f=>f.n===3&&f.w===2)){
    const lb=b.slice(lf.s,lf.e), fs=fields(lb);
    const namef=fs.find(f=>f.n===1&&f.w===2);
    const name=namef?dec.decode(lb.slice(namef.s,namef.e)):'';
    if(name!=='hits')continue;
    const keys=fs.filter(f=>f.n===3&&f.w===2).map(f=>dec.decode(lb.slice(f.s,f.e)));
    const vals=fs.filter(f=>f.n===4&&f.w===2).map(f=>valueOf(lb.slice(f.s,f.e)));
    for(const ff of fs.filter(f=>f.n===2&&f.w===2)){
      const fb=lb.slice(ff.s,ff.e), tagf=fields(fb).find(f=>f.n===2&&f.w===2);if(!tagf)continue;
      const packed=fb.slice(tagf.s,tagf.e), idx=[];let p=0;while(p<packed.length){let v;[v,p]=varint(packed,p);idx.push(v)}
      const props={};for(let i=0;i+1<idx.length;i+=2)props[keys[idx[i]]]=vals[idx[i+1]];
      if(props._id!==undefined&&props._id!==null)ids.push(String(props._id));
    }
  }
  return [...new Set(ids)];
}
const z=10,lon=2.35,lat=48.86,n=2**z,x=Math.floor((lon+180)/360*n),y=Math.floor((1-Math.asinh(Math.tan(lat*Math.PI/180))/Math.PI)/2*n);
const url=`https://api.electroverse.com/rest/locations/tiles/elastic/${z}/${x}/${y}`;
const r=await fetch(url,{headers:{'Api-Key':key,source:'android','X-App-Version':'2026.09.08'}});
if(!r.ok)throw new Error('tile HTTP '+r.status);
const ids=parseTile(new Uint8Array(await r.arrayBuffer()));
const mapping=JSON.parse(await fs.readFile('data/electroverse/irve_location_mapping.json','utf8'));
const known=new Set((mapping.mappings||[]).map(m=>String(m.electroverseLocationPk)));
const overlap=ids.filter(id=>known.has(id));
const report={generatedAt:new Date().toISOString(),tile:{z,x,y},tileIds:ids.length,overlapWithMapping:overlap.length,overlapPct:ids.length?Number((overlap.length/ids.length*100).toFixed(2)):0,sampleIds:ids.slice(0,20),sampleOverlap:overlap.slice(0,20)};
await fs.mkdir('reports/electroverse',{recursive:true});await fs.writeFile('reports/electroverse/tile-id-validation.json',JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report,null,2));
