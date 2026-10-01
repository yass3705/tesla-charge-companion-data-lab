import fs from 'node:fs/promises';

const FILE='data/national/france_public_charging_canonical.json';
const targets=['FRHPCPNF058543','FRTCBP00699','FRETIP77131A','FRV75PHBSAGLOB','FRG10P69382CA'];
const raw=await fs.readFile(FILE,'utf8');
const out={fileBytes:Buffer.byteLength(raw),samples:{}};
for(const target of targets){
  const i=raw.indexOf(target);
  out.samples[target]=i<0?null:{index:i,context:raw.slice(Math.max(0,i-2500),Math.min(raw.length,i+6500))};
}
console.log(JSON.stringify(out,null,2));
