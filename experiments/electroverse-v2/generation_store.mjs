import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import crypto from 'node:crypto';
const digest=x=>crypto.createHash('sha256').update(JSON.stringify(x)).digest('hex');
const name=i=>'batch-'+String(i).padStart(7,'0')+'.json';
function rootOf(dir){
 const r=path.resolve(dir),t=path.resolve(os.tmpdir())+path.sep;
 if(!r.startsWith(t)||!path.basename(r).startsWith('electroverse-v2-'))throw Error('unsafe journal directory');
 return r;
}
export async function appendBatch(dir,{sourceHash,index,records}){
 const root=rootOf(dir);
 if(typeof sourceHash!=='string'||!sourceHash||!Number.isSafeInteger(index)||index<0||!Array.isArray(records))throw Error('invalid batch');
 const ids=new Set();
 for(const rec of records){if(typeof rec?.electroverseLocationPk!=='string'||ids.has(rec.electroverseLocationPk))throw Error('duplicate or invalid PK');ids.add(rec.electroverseLocationPk)}
 await fs.mkdir(root,{recursive:true});
 const data={version:1,sourceHash,index,records},payload={...data,hash:digest(data)};
 const target=path.join(root,name(index));
 try{const old=JSON.parse(await fs.readFile(target,'utf8'));if(JSON.stringify(old)===JSON.stringify(payload))return {reused:true,bytes:0};throw Error('conflicting batch commit')}catch(e){if(e.code!=='ENOENT')throw e}
 const tmp=path.join(root,'.tmp-'+process.pid+'-'+crypto.randomBytes(8).toString('hex'));
 try{await fs.writeFile(tmp,JSON.stringify(payload),{flag:'wx'});await fs.rename(tmp,target)}finally{await fs.rm(tmp,{force:true})}
 return {reused:false,bytes:Buffer.byteLength(JSON.stringify(payload))};
}
export async function recoverBatches(dir,{sourceHash}){
 const root=rootOf(dir);let entries=[];
 try{entries=await fs.readdir(root)}catch(e){if(e.code!=='ENOENT')throw e;return {completed:[],records:[]}}
 const files=entries.filter(x=>/^batch-\d{7}\.json$/.test(x)).sort(),completed=[],records=[],seen=new Set();
 for(const file of files){
  let payload;try{payload=JSON.parse(await fs.readFile(path.join(root,file),'utf8'))}catch{throw Error('corrupt batch '+file)}
  const {hash,...data}=payload;
  if(data.version!==1||data.sourceHash!==sourceHash||name(data.index)!==file||!Array.isArray(data.records)||hash!==digest(data))throw Error('untrusted batch '+file);
  if(data.index!==completed.length)throw Error('noncontiguous batch '+file);
  for(const row of data.records){if(typeof row?.electroverseLocationPk!=='string'||seen.has(row.electroverseLocationPk))throw Error('duplicate PK across batches');seen.add(row.electroverseLocationPk);records.push(row)}
  completed.push(data.index);
 }
 return {completed,records};
}
