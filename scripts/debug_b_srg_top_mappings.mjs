import fs from 'node:fs/promises';
const MAP='data/electroverse/irve_location_mapping.json';
const OUT='reports/electroverse/b-srg-top-mapping-debug.json';
const ids=new Set(['4537230','4472643','4462976','4542916','4542915','4648160','4461982']);
const m=JSON.parse(await fs.readFile(MAP,'utf8'));
const rows=(m.mappings||[]).filter(x=>ids.has(String(x.electroverseLocationPk)));
await fs.mkdir('reports/electroverse',{recursive:true});
await fs.writeFile(OUT,JSON.stringify({generatedAt:new Date().toISOString(),rows},null,2)+'\n');
console.log(JSON.stringify({count:rows.length,rows},null,2));
