import fs from 'node:fs/promises';import path from 'node:path';
export async function resolveSnapshot(root='data/reve-v2/raw'){
  if(process.env.REVE_SNAPSHOT)return process.env.REVE_SNAPSHOT;
  const entries=(await fs.readdir(root,{withFileTypes:true})).filter(e=>e.isDirectory()).map(e=>e.name).sort().reverse();
  for(const name of entries){const dir=path.join(root,name);try{const m=JSON.parse(await fs.readFile(path.join(dir,'manifest.json'),'utf8'));const complete=m.status==='captured'&&Number(m.pagesSucceeded)>0&&(!Number(m.reportedTotalPages)||Number(m.pagesSucceeded)===Number(m.reportedTotalPages))&&(!Array.isArray(m.failures)||m.failures.length===0);if(complete)return dir}catch{}}
  throw new Error('No complete REVE snapshot found');
}
export async function snapshotManifest(dir){return JSON.parse(await fs.readFile(path.join(dir,'manifest.json'),'utf8'));}
