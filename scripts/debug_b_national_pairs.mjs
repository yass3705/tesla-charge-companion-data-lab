import fs from 'node:fs/promises';

const NATIONAL='data/national/france_public_charging_canonical.json';
const OUT='reports/electroverse/b-national-pair-debug.json';
const targets=new Set([
'FRSRGE12347805851','FRSRGE12347805852','FRSRGE12348894201','FRSRGE12348894202',
'FRSRGE12347806081','FRSRGE12347806082','FRSRGE12348894251','FRSRGE12348894252',
'FRSRGE12349434321','FRSRGE12349434322','FRSRGE12349434331','FRSRGE12349434332',
'FRSRGE12347806121','FRSRGE12347806122','FRSRGE12348894291','FRSRGE12348894292'
]);
const norm=x=>String(x??'').trim().toUpperCase().replace(/[^A-Z0-9]/g,'');
const nat=JSON.parse(await fs.readFile(NATIONAL,'utf8'));
const hits=[];
function walk(v,path=[],parent=null){
  if(v==null)return;
  if(typeof v==='string'){
    if(targets.has(norm(v))){
      hits.push({path:path.join('.'),value:v,parent});
    }
    return;
  }
  if(typeof v!=='object')return;
  if(Array.isArray(v)){for(let i=0;i<v.length;i++)walk(v[i],[...path,String(i)],v[i]);return;}
  for(const [k,x] of Object.entries(v))walk(x,[...path,k],v);
}
walk(nat);
const slim=hits.map(h=>{
  const p=h.parent&&typeof h.parent==='object'?h.parent:{};
  const out={pdc:h.value,path:h.path};
  for(const [k,v] of Object.entries(p)){
    if(v==null||typeof v!=='object') out[k]=v;
  }
  return out;
});
await fs.mkdir('reports/electroverse',{recursive:true});
await fs.writeFile(OUT,JSON.stringify({generatedAt:new Date().toISOString(),hits:slim},null,2)+'\n');
console.log(JSON.stringify({count:slim.length,hits:slim},null,2));
