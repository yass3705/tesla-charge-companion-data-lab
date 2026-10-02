import fs from 'node:fs/promises';
const FILE='data/national/france_public_charging_canonical.json';
const OUT='reports/electroverse/b-srg-canonical-pdc-audit.json';
const targets=[
'FRSRGE12347805851','FRSRGE12347805852','FRSRGE12348894201','FRSRGE12348894202',
'FRSRGE12347806081','FRSRGE12347806082','FRSRGE12348894251','FRSRGE12348894252',
'FRSRGE12347806121','FRSRGE12347806122','FRSRGE12348894291','FRSRGE12348894292',
'FRSRGE12347805821','FRSRGE12347805822','FRSRGE12348894191','FRSRGE12348894192',
'FRSRGE12347805871','FRSRGE12347805872','FRSRGE12348894221','FRSRGE12348894222'
];
const raw=await fs.readFile(FILE,'utf8');
const includes=Object.fromEntries(targets.map(t=>[t,raw.includes(t)]));
const data=JSON.parse(raw);
const found=[];
function walk(v,path=[]){
 if(v==null||typeof v!=='object')return;
 if(Array.isArray(v)){for(let i=0;i<v.length;i++)walk(v[i],[...path,String(i)]);return;}
 const vals=Object.values(v).filter(x=>typeof x==='string').map(String);
 const hits=targets.filter(t=>vals.includes(t));
 if(hits.length){
   const scalars={};
   for(const [k,x] of Object.entries(v)) if(x==null||['string','number','boolean'].includes(typeof x))scalars[k]=x;
   found.push({path:path.join('.'),hits,scalars});
 }
 for(const [k,x] of Object.entries(v)) if(x&&typeof x==='object')walk(x,[...path,k]);
}
walk(data);
const out={generatedAt:new Date().toISOString(),includes,foundCount:found.length,found};
await fs.mkdir('reports/electroverse',{recursive:true});
await fs.writeFile(OUT,JSON.stringify(out,null,2)+'\n');
console.log(JSON.stringify(out,null,2));
