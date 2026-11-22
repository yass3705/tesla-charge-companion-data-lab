import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {performance} from 'node:perf_hooks';
import {appendBatch,recoverBatches} from './generation_store.mjs';
const stations=5000,batchSize=5;
const dir=await fs.mkdtemp(path.join(os.tmpdir(),'electroverse-v2-'));
const sourceHash='synthetic-stress-fixed';
let writeBytes=0;
const start=performance.now();
try {
 for(let i=0;i<stations/batchSize;i++){
  const records=Array.from({length:batchSize},(_,j)=>({electroverseLocationPk:String(i*batchSize+j),tariff:{chargingLocationPk:String(i*batchSize+j),evses:[{pk:i*batchSize+j,connectors:[{pk:i*batchSize+j,priceComponents:[{__typename:'ConsumptionRate',formattedValue:'€0.42/kWh'}]}]}]}}));
  const r=await appendBatch(dir,{sourceHash,index:i,records});writeBytes+=r.bytes;
 }
 const afterWrites=performance.now();
 const restored=await recoverBatches(dir,{sourceHash});
 const finish=performance.now();
 if(restored.records.length!==stations||restored.completed.length!==stations/batchSize)throw Error('mismatch');
 console.log(JSON.stringify({kind:'SYNTHETIC_OFFLINE_STRESS',stations,batches:restored.completed.length,bytesSerialized:writeBytes,writeMs:Math.round(afterWrites-start),recoveryMs:Math.round(finish-afterWrites),node:process.version},null,2));
} finally {await fs.rm(dir,{recursive:true,force:true})}
