import fs from 'node:fs/promises';

const FILE='data/national/france_public_charging_canonical.json';
const OUT='reports/electroverse-fr-via-national-tech.json';
const targets=new Set([
  'FRVIAE20141078011','FRVIAE20141078012','FRVIAE20141078013',
  'FRVIAE12346030581','FRVIAE12346030582',
  'FRVIAE12346030591','FRVIAE12346030592',
  'FRVIAE10001205451','FRVIAE10001205452',
  'FRVIAE10001229571','FRVIAE10001229572'
]);
const norm=x=>String(x??'').trim().toUpperCase().replace(/[^A-Z0-9]/g,'');

const raw=await fs.readFile(FILE,'utf8');
const root=JSON.parse(raw);
const hits=[];
const seen=new WeakSet();

function summarize(obj){
  const out={};
  for(const [k,v] of Object.entries(obj||{})){
    if(v==null||typeof v==='string'||typeof v==='number'||typeof v==='boolean'){
      if(String(k).match(/id|evse|pdc|power|kw|puissance|plug|prise|connector|standard|type|nom|name|station/i)) out[k]=v;
    }else if(Array.isArray(v) && v.length<=12 && v.every(x=>x==null||typeof x!=='object')){
      if(String(k).match(/plug|prise|connector|standard|type|power|kw/i)) out[k]=v;
    }
  }
  return out;
}
function walk(v,path=[],depth=0){
  if(v==null||depth>9)return;
  if(typeof v==='object'){
    if(seen.has(v))return; seen.add(v);
    if(!Array.isArray(v)){
      let matched=[];
      for(const [k,val] of Object.entries(v)){
        if(typeof val==='string'){
          const n=norm(val);
          for(const t of targets) if(n===t){matched.push(t);break;}
        }
      }
      if(matched.length){
        hits.push({path:path.join('.'),matched:[...new Set(matched)],summary:summarize(v)});
      }
    }
    if(Array.isArray(v)){
      for(let i=0;i<v.length;i++)walk(v[i],[...path,String(i)],depth+1);
    }else{
      for(const [k,val] of Object.entries(v))walk(val,[...path,k],depth+1);
    }
  }
}
walk(root,['root'],0);
const out={
  generatedAt:new Date().toISOString(),
  topLevelType:Array.isArray(root)?'array':typeof root,
  topLevelKeys:Array.isArray(root)?[]:Object.keys(root).slice(0,100),
  targetCount:targets.size,
  hitCount:hits.length,
  hits
};
await fs.mkdir('reports',{recursive:true});
await fs.writeFile(OUT,JSON.stringify(out,null,2)+'\n');
console.log(JSON.stringify(out,null,2));
