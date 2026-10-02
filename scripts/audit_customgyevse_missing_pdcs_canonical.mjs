import fs from 'node:fs/promises';
const paths=[
 'data/national/france_public_charging_canonical.json',
 'data/france_public_charging_canonical.json',
 'data/national/france-canonical.json'
];
const targets=[
'FRGYMEC12403042','FRGYMEC12403043',
'FRGYMEC12309006','FRGYMEC22309006',
'FRGYMEC12309016','FRGYMEC22309016',
'FRGYMEC12309023','FRGYMEC22309023'
];
const out={generatedAt:new Date().toISOString(),files:[]};
for(const p of paths){
 try{
  const raw=await fs.readFile(p,'utf8');
  const hits={};
  for(const t of targets)hits[t]=raw.includes(t);
  out.files.push({path:p,size:raw.length,hits});
 }catch(e){out.files.push({path:p,error:e.code||String(e)})}
}
await fs.mkdir('reports/electroverse',{recursive:true});
await fs.writeFile('reports/electroverse/customgyevse-missing-pdc-canonical-audit.json',JSON.stringify(out,null,2)+'\n');
console.log(JSON.stringify(out,null,2));
