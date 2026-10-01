import fs from 'node:fs/promises';

const norm=x=>String(x??'').trim().toUpperCase().replace(/[^A-Z0-9]/g,'');
const targets=new Set(['FRGSPE12345958361','FRGSPE12345958371']);
const mapping=JSON.parse(await fs.readFile('data/electroverse/irve_location_mapping.json','utf8'));
const m=(mapping.mappings||[]).find(x=>String(x.electroverseLocationPk)==='4456304')||null;
console.log('MAPPING '+JSON.stringify(m,null,2));

const stationId=norm(m?.irveStationId||'');
const data=JSON.parse(await fs.readFile('data/national/france_public_charging_canonical.json','utf8'));
const hits=[];
function walk(x,path=[]){
  if(Array.isArray(x)){x.forEach((v,i)=>walk(v,path.concat(i)));return;}
  if(!x||typeof x!=='object')return;
  const vals=Object.entries(x);
  const strings=vals.filter(([,v])=>typeof v==='string').map(([,v])=>norm(v));
  if(strings.some(v=>targets.has(v)) || (stationId && strings.includes(stationId))){
    hits.push({path,obj:x});
  }
  for(const [k,v] of vals) if(v&&typeof v==='object') walk(v,path.concat(k));
}
walk(data);
console.log('NATIONAL '+JSON.stringify(hits.slice(0,50),null,2));
