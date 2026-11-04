import {appendBatch,recoverBatches} from './generation_store.mjs';
import {validateFixture,validateRecord,pkOf,sha,fixtureTransport} from './model.mjs';
export async function runJournal(fixture,{outDir,transport=fixtureTransport(fixture),batchSize=5,interruptAfter=null}={}){
 validateFixture(fixture);
 if(!Number.isInteger(batchSize)||batchSize<1||batchSize>5)throw Error('invalid batch size');
 const sourceHash=sha(fixture.stations.map(x=>[pkOf(x),x.tariffHash]));
 const restored=await recoverBatches(outDir,{sourceHash});
 const all=fixture.stations.map(pkOf),committed=restored.completed.length;
 // Check journal sequence against this generation's exact worklist before reusing records.
 for(let i=0;i<restored.completed.length;i++){
  const expected=all.slice(i*batchSize,(i+1)*batchSize);
  const actual=restored.records.slice(i*batchSize,(i+1)*batchSize).map(pkOf);
  if(JSON.stringify(expected)!==JSON.stringify(actual))throw Error('journal worklist mismatch');
 }
 const existing=new Map(restored.records.map(r=>[pkOf(r),validateRecord(r)]));
 const batches=Math.ceil(all.length/batchSize);
 const stats={writes:0,skippedBatches:committed,processedBatches:0,unresolved:0};
 for(let index=committed;index<batches;index++){
  const keys=all.slice(index*batchSize,(index+1)*batchSize),response=await transport.request(keys,'batch');
  if(response.status!==200)throw Error('batch status '+response.status);
  const records=[];
  for(const pk of keys){
   let row=response.records?.[pk];
   if(!row||row.complete===false){const single=await transport.request([pk],'single');row=single.status===200?single.records?.[pk]:null;}
   if(!row||row.complete===false){stats.unresolved++;throw Error('incomplete batch '+index)}
   validateRecord(row);if(pkOf(row)!==pk)throw Error('identity mismatch');records.push(row);
  }
  await appendBatch(outDir,{sourceHash,index,records});
  stats.writes++;stats.processedBatches++;
  for(const row of records)existing.set(pkOf(row),row);
  if(interruptAfter!==null&&stats.processedBatches===interruptAfter)throw Object.assign(Error('simulated interruption'),{code:'SIMULATED_INTERRUPT'});
 }
 return{records:all.map(pk=>existing.get(pk)),metrics:{...stats,...transport.metrics(),covered:existing.size,expected:all.length}};
}