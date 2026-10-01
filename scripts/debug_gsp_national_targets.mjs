import fs from 'node:fs/promises';

const targets=new Set(['FRGSPE12345958361','FRGSPE12345958371']);
const norm=x=>String(x??'').trim().toUpperCase().replace(/[^A-Z0-9]/g,'');
const data=JSON.parse(await fs.readFile('data/national/france_public_charging_canonical.json','utf8'));
const hits=[];
function walk(x,path=[]){
  if(Array.isArray(x)){
    x.forEach((v,i)=>walk(v,path.concat(i)));
    return;
  }
  if(!x||typeof x!=='object')return;
  const vals=Object.entries(x);
  const matched=vals.some(([k,v])=>typeof v==='string'&&targets.has(norm(v)));
  if(matched) hits.push({path,obj:x});
  for(const [k,v] of vals){
    if(v&&typeof v==='object')walk(v,path.concat(k));
  }
}
walk(data);
console.log(JSON.stringify(hits,null,2));
