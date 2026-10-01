import fs from 'node:fs/promises';
const SRC='data/national/france_public_charging_canonical.json';
const OUT='reports/electroverse-r3m-technical-residual.json';
const norm=x=>String(x??'').trim().toUpperCase().replace(/[^A-Z0-9]/g,'');
const root=JSON.parse(await fs.readFile(SRC,'utf8'));
const rows=[];
const seen=new WeakSet();
function walk(v){
  if(!v||typeof v!=='object')return;
  if(seen.has(v))return;seen.add(v);
  if(Array.isArray(v)){for(const x of v)walk(x);return;}
  const vals=Object.values(v);
  const hit=vals.some(x=>typeof x==='string'&&norm(x).startsWith('FRR3ME'));
  if(hit)rows.push(v);
  for(const x of vals)walk(x);
}
walk(root);
const sample=rows.slice(0,80).map(r=>{
  const out={};
  for(const [k,v] of Object.entries(r)){
    if(v==null||typeof v==='string'||typeof v==='number'||typeof v==='boolean')out[k]=v;
  }
  return out;
});
const keyCounts={};
for(const r of rows)for(const k of Object.keys(r))keyCounts[k]=(keyCounts[k]||0)+1;
const out={generatedAt:new Date().toISOString(),rootType:Array.isArray(root)?'array':typeof root,rootKeys:root&&typeof root==='object'&&!Array.isArray(root)?Object.keys(root):[],matchedObjects:rows.length,keyCounts:Object.entries(keyCounts).sort((a,b)=>b[1]-a[1]),samples:sample};
await fs.mkdir('reports',{recursive:true});
await fs.writeFile(OUT,JSON.stringify(out,null,2)+'\n');
console.log(JSON.stringify(out,null,2));
