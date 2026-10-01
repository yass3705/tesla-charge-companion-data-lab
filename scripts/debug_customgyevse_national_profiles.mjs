import fs from 'node:fs/promises';

const MAP='data/electroverse/irve_location_mapping.json';
const NATIONAL='data/national/france_public_charging_canonical.json';
const OUT='reports/electroverse/customgyevse-national-sample.json';
const targetLocations=new Set(['4222135','4225537','4226165']);
const norm=x=>String(x??'').trim().toUpperCase().replace(/[^A-Z0-9]/g,'');

const mapping=JSON.parse(await fs.readFile(MAP,'utf8'));
const targets=[];
for(const m of mapping.mappings||[]){
  if(!targetLocations.has(String(m.electroverseLocationPk)))continue;
  for(const p of m.irvePdcIds||[])targets.push({locationPk:String(m.electroverseLocationPk),stationId:m.irveStationId??null,pdc:String(p),norm:norm(p)});
}
const targetSet=new Set(targets.map(x=>x.norm));
const nat=JSON.parse(await fs.readFile(NATIONAL,'utf8'));
const hits=[];
const seen=new Set();
function shallow(v){
  if(v==null||typeof v!=='object')return v;
  if(Array.isArray(v))return {__arrayLength:v.length,__sample:v.slice(0,3).map(x=>typeof x==='object'?Object.keys(x||{}):x)};
  const o={};
  for(const [k,x] of Object.entries(v)){
    if(x==null||typeof x!=='object')o[k]=x;
    else if(Array.isArray(x))o[k]={__arrayLength:x.length,__sample:x.slice(0,5).map(y=>typeof y==='object'?Object.keys(y||{}):y)};
    else o[k]={__keys:Object.keys(x).slice(0,30)};
  }
  return o;
}
function walk(v,path=[],parent=null){
  if(v==null)return;
  if(typeof v==='string'){
    const n=norm(v);
    if(targetSet.has(n)){
      const key=path.join('.');
      if(!seen.has(key)){seen.add(key);hits.push({path:key,value:v,parent:shallow(parent)});}
    }
    return;
  }
  if(typeof v!=='object')return;
  if(Array.isArray(v)){for(let i=0;i<v.length;i++)walk(v[i],[...path,String(i)],v);return;}
  for(const [k,x] of Object.entries(v))walk(x,[...path,k],v);
}
walk(nat);
await fs.mkdir('reports/electroverse',{recursive:true});
const out={generatedAt:new Date().toISOString(),targets,hits:hits.slice(0,200)};
await fs.writeFile(OUT,JSON.stringify(out,null,2)+'\n');
console.log(JSON.stringify(out,null,2));
