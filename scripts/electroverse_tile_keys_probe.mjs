import fs from 'node:fs/promises';
const key=process.env.ELECTROVERSE_API_KEY;if(!key)throw new Error('missing key');
const u8=n=>n&255;
function varint(b,p){let v=0,s=0,x;do{x=b[p++];v+=(x&127)*2**s;s+=7}while(x&128);return[v,p]}
function fields(b,start=0,end=b.length){const out=[];let p=start;while(p<end){let t;[t,p]=varint(b,p);const n=t>>3,w=t&7;if(w===2){let l;[l,p]=varint(b,p);out.push([n,p,p+l]);p+=l}else if(w===0){let q;[,q]=varint(b,p);p=q}else if(w===5)p+=4;else if(w===1)p+=8;else break}return out}
const z=10,lon=2.35,lat=48.86,n=2**z,x=Math.floor((lon+180)/360*n),y=Math.floor((1-Math.asinh(Math.tan(lat*Math.PI/180))/Math.PI)/2*n);
const url='https://api.electroverse.com/rest/locations/tiles/elastic/'+z+'/'+x+'/'+y;
const r=await fetch(url,{headers:{'Api-Key':key,source:'android','X-App-Version':'2026.09.08'}});
const b=new Uint8Array(await r.arrayBuffer()), dec=new TextDecoder(), layers=[];
if(r.ok)for(const f of fields(b).filter(x=>x[0]===3)){const lb=b.slice(f[1],f[2]), lf=fields(lb);const namef=lf.find(x=>x[0]===1);const name=namef?dec.decode(lb.slice(namef[1],namef[2])):'?';const keys=lf.filter(x=>x[0]===3).map(x=>dec.decode(lb.slice(x[1],x[2])));const features=lf.filter(x=>x[0]===2).length;layers.push({name,features,keys:[...new Set(keys)].sort()})}
const report={generatedAt:new Date().toISOString(),tile:{z,x,y},status:r.status,contentType:r.headers.get('content-type'),bytes:b.length,layers,pricingLikeKeys:[...new Set(layers.flatMap(l=>l.keys).filter(k=>/(price|tariff|cost|fee|currency|free|rate)/i.test(k)))]};
await fs.mkdir('reports/electroverse',{recursive:true});await fs.writeFile('reports/electroverse/tile-keys-probe.json',JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report,null,2));
