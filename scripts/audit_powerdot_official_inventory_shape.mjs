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
    if(q){
      if(ch==='"'&&s[i+1]==='"'){field+='"';i++;}
      else if(ch==='"')q=false;
      else field+=ch;
    }else{
      if(ch==='"')q=true;
      else if(ch===','){row.push(field);field='';}
      else if(ch==='\n'){row.push(field.replace(/\r$/,''));rows.push(row);row=[];field='';}
      else field+=ch;
    }
  }
  if(field||row.length){row.push(field);rows.push(row);}
  return rows;
}
const rows=parseCsv(raw);
const headers=rows[0]||[];
const objs=rows.slice(1).filter(r=>r.some(Boolean)).map(r=>Object.fromEntries(headers.map((h,i)=>[h,r[i]??''])));
const samples=objs.slice(0,5);
const targetIds=new Set(['FRPD1EASCGUYBBC0011','FRPD1EDUVVRSKP0013','FRPD1ECACSDSIES50013']);
const idCols=headers.filter(h=>/id.*pdc|id.*station|id.*borne|evse|pdc/i.test(h));
const powerCols=headers.filter(h=>/puissance|power/i.test(h));
const hits=objs.filter(o=>Object.values(o).some(v=>targetIds.has(String(v).replace(/[^A-Za-z0-9]/g,''))));
const out={generatedAt:new Date().toISOString(),url:URL,bytes:raw.length,rowCount:objs.length,headers,idCols,powerCols,samples,hits};
await fs.mkdir('reports',{recursive:true});
await fs.writeFile('reports/powerdot-official-inventory-shape.json',JSON.stringify(out,null,2)+'\n');
console.log(JSON.stringify(out,null,2));
