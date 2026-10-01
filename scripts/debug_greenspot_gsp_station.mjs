import fs from 'node:fs/promises';
import zlib from 'node:zlib';
const raw=zlib.gunzipSync(await fs.readFile('data/greenspot/france/greenspot-france-current.json.gz')).toString('utf8');
const j=JSON.parse(raw);
const targets=['90329287','12345958361','12345958371','DAUGERE','BORDEAUX LAC','44.8877','-0.5924'];
const hits=[];
function walk(x,path=[]){
  if(Array.isArray(x)){x.forEach((v,i)=>walk(v,path.concat(i)));return;}
  if(!x||typeof x!=='object')return;
  const s=JSON.stringify(x).toUpperCase();
  if(targets.some(t=>s.includes(t)))hits.push({path,obj:x});
  for(const [k,v] of Object.entries(x))if(v&&typeof v==='object')walk(v,path.concat(k));
}
walk(j);
console.log(JSON.stringify(hits.slice(0,100),null,2));
