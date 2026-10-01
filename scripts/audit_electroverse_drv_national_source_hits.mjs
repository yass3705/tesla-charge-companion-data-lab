import fs from 'node:fs/promises';
import path from 'node:path';

const needles=['FRDRVE11838P1','FRDRVE11838P2','FRDRVE22011A00015701P1','FRDRVE22011A00015801P1'];
const skip=new Set(['.git','node_modules']);
const hits=[];
async function walk(dir){
  for(const ent of await fs.readdir(dir,{withFileTypes:true})){
    if(skip.has(ent.name))continue;
    const p=path.join(dir,ent.name);
    if(ent.isDirectory()){await walk(p);continue;}
    let st;try{st=await fs.stat(p)}catch{continue}
    if(st.size>25_000_000)continue;
    let txt;try{txt=await fs.readFile(p,'utf8')}catch{continue}
    for(const n of needles){
      const i=txt.indexOf(n);
      if(i>=0){
        hits.push({file:p,needle:n,excerpt:txt.slice(Math.max(0,i-1200),Math.min(txt.length,i+2500))});
      }
    }
  }
}
await walk('.');
await fs.mkdir('reports',{recursive:true});
const out={generatedAt:new Date().toISOString(),hits};
await fs.writeFile('reports/electroverse-fr-drv-national-source-hits.json',JSON.stringify(out,null,2)+'\n');
console.log(JSON.stringify(out,null,2));
