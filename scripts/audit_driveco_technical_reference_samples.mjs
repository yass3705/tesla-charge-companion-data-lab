import fs from 'node:fs/promises';

const src=JSON.parse(await fs.readFile('data/operator_direct/driveco_evse_tariffs.json','utf8'));
const arr=Array.isArray(src)?src:(src.records||src.evses||src.items||[]);
const ids=new Set(['FRDRVE11838P1','FRDRVE11838P2','FRDRVE22011A00015701P1','FRDRVE22011A00015801P1',
'FRDRVEBLQW1','FRDRVEFRSU1','FRDRVEGVWY1','FRDRVEGVWY2']);
const hits=arr.filter(x=>ids.has(x.evseId));
const shape=arr.slice(0,3);
await fs.mkdir('reports',{recursive:true});
const out={generatedAt:new Date().toISOString(),count:arr.length,shape,hits};
await fs.writeFile('reports/driveco-technical-reference-samples.json',JSON.stringify(out,null,2)+'\n');
console.log(JSON.stringify(out,null,2));
