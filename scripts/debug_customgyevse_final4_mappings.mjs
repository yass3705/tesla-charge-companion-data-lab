import fs from 'node:fs/promises';
const MAP='data/electroverse/irve_location_mapping.json';
const OUT='reports/electroverse/customgyevse-final4-mapping-debug.json';
const ids=new Set(['4221832','4225422','4221647','4225816']);
const m=JSON.parse(await fs.readFile(MAP,'utf8'));
const rows=(m.mappings||[]).filter(x=>ids.has(String(x.electroverseLocationPk)));
await fs.mkdir('reports/electroverse',{recursive:true});
await fs.writeFile(OUT,JSON.stringify({generatedAt:new Date().toISOString(),rows},null,2)+'\n');
console.log(JSON.stringify({count:rows.length,rows},null,2));
