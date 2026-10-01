import fs from 'node:fs/promises';
const SRC='reports/electroverse/remaining-batch-analysis.json';
const OUT='reports/electroverse/current-homogeneous-quickwins.json';
const src=JSON.parse(await fs.readFile(SRC,'utf8'));
const groups=[];
for(const op of src.operators||[]){
  for(const g of op.safeGroups||[]){
    if(g.mode!=='homogeneous_exact_set')continue;
    groups.push({
      operator:op.operator,
      electroverseLocationPk:String(g.electroverseLocationPk),
      irveStationId:g.irveStationId??null,
      residualCount:g.residualCount,
      availablePdcCount:g.availablePdcCount,
      refs:g.refs||[],
      commonPrefix:g.commonPrefix??null
    });
  }
}
const out={generatedAt:new Date().toISOString(),count:groups.length,totalSourceEvses:groups.reduce((n,g)=>n+g.residualCount,0),groups};
await fs.writeFile(OUT,JSON.stringify(out,null,2)+'\n');
console.log(JSON.stringify(out,null,2));