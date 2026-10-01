import fs from 'node:fs/promises';

const src=JSON.parse(await fs.readFile('data/operator_direct/driveco_evse_tariffs.json','utf8'));
const describe=v=>{
  if(Array.isArray(v))return {type:'array',length:v.length,sample:v.slice(0,3)};
  if(v&&typeof v==='object')return {type:'object',keys:Object.keys(v).slice(0,50),sample:Object.fromEntries(Object.entries(v).slice(0,5))};
  return {type:typeof v,value:v};
};
const top=describe(src);
const nested={};
if(src&&typeof src==='object'&&!Array.isArray(src)){
  for(const [k,v] of Object.entries(src).slice(0,20))nested[k]=describe(v);
}
const ids=new Set(['FRDRVE11838P1','FRDRVE11838P2','FRDRVE22011A00015701P1','FRDRVE22011A00015801P1',
'FRDRVEBLQW1','FRDRVEFRSU1','FRDRVEGVWY1','FRDRVEGVWY2']);
const hits=[];
const seen=new Set();
function walk(v,path='root'){
  if(!v||typeof v!=='object'||seen.has(v))return;
  seen.add(v);
  if(!Array.isArray(v) && ids.has(v.evseId))hits.push({path,value:v});
  if(Array.isArray(v)){for(let i=0;i<v.length;i++)walk(v[i],path+'['+i+']');}
  else for(const [k,x] of Object.entries(v))walk(x,path+'.'+k);
}
walk(src);
const out={generatedAt:new Date().toISOString(),top,nested,hits};
await fs.mkdir('reports',{recursive:true});
await fs.writeFile('reports/driveco-technical-reference-samples.json',JSON.stringify(out,null,2)+'\n');
console.log(JSON.stringify(out,null,2));
