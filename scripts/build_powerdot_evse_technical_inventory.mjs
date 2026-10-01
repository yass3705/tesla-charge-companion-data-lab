import fs from 'node:fs/promises';
import { execFileSync } from 'node:child_process';

const URL='https://www.data.gouv.fr/api/1/datasets/r/1bf98bac-94a9-4909-8726-47a203038a40';
const CSV='/tmp/powerdot.csv';
execFileSync('curl',['-L','--fail','--silent','--show-error',URL,'-o',CSV],{stdio:'inherit'});
const raw=await fs.readFile(CSV,'utf8');
function parseCsv(s){
  const rows=[];let row=[],field='',q=false;
  for(let i=0;i<s.length;i++){
    const ch=s[i];
    if(q){if(ch==='"'&&s[i+1]==='"'){field+='"';i++;}else if(ch==='"')q=false;else field+=ch;}
    else if(ch==='"')q=true;
    else if(ch===','){row.push(field);field='';}
    else if(ch==='\n'){row.push(field.replace(/\r$/,''));rows.push(row);row=[];field='';}
    else field+=ch;
  }
  if(field||row.length){row.push(field);rows.push(row);}return rows;
}
const rows=parseCsv(raw),headers=rows[0]||[];
const objs=rows.slice(1).filter(r=>r.some(Boolean)).map(r=>Object.fromEntries(headers.map((h,i)=>[h,r[i]??''])));
const bool=v=>String(v).toLowerCase()==='true';
const compact=objs.map(o=>({
  evseId:String(o.id_pdc_itinerance||'').trim(),
  powerKw:Number(o.puissance_nominale),
  plugs:[
    bool(o.prise_type_ef)?'EF':null,
    bool(o.prise_type_2)?'T2':null,
    bool(o.prise_type_combo_ccs)?'CCS':null,
    bool(o.prise_type_chademo)?'CHA':null,
    bool(o.prise_type_autre)?'OTHER':null
  ].filter(Boolean).sort(),
  publisherUpdatedAt:o.date_maj||null
})).filter(x=>x.evseId&&Number.isFinite(x.powerKw));
const maxDate=compact.map(x=>x.publisherUpdatedAt).filter(Boolean).sort().at(-1)||null;
const out={
  schemaVersion:1,
  dataset:'powerdot-official-france-technical-inventory',
  generatedAt:new Date().toISOString(),
  source:URL,
  publisherLastUpdateKnown:maxDate,
  rowCount:compact.length,
  fields:['evseId','powerKw','plugs','publisherUpdatedAt'],
  policy:{technicalIdentityOnly:true,tariffNotUsed:true,liveStatusNotUsed:true},
  evses:compact
};
await fs.mkdir('data/operator_direct',{recursive:true});
await fs.writeFile('data/operator_direct/powerdot_evse_technical_inventory.json',JSON.stringify(out,null,2)+'\n');
console.log(JSON.stringify({rowCount:out.rowCount,publisherLastUpdateKnown:maxDate,samples:compact.slice(0,5)},null,2));
