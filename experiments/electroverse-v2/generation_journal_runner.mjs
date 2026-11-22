// Experimental offline generation/journal integration. No canonical collector access.
import {planGeneration,reconcileGeneration} from './generation_planner.mjs';
import {runJournal} from './journal_runner.mjs';
import {validateRecord,validateFixture,pkOf,diffInventories} from './model.mjs';
export async function simulateGeneration({previous=[],fixture,selected,inventoryComplete=true,generationId,outDir,transport,interruptAfter=null}){
 if(!inventoryComplete)throw Error('incomplete inventory: no generation allowed');
 validateFixture(fixture);
 for(const record of previous)validateRecord(record);
 const inventory=fixture.stations.map(pkOf);
 const chosen=selected??inventory;
 const plan=planGeneration({previous,inventory,selected:chosen,generationId});
 const candidates=new Set(plan.fetch);
 const subset={...fixture,stations:fixture.stations.filter(r=>candidates.has(pkOf(r)))};
 // One logical worklist, one journal namespace per generation; never reuse between distinct generations.
 const result=await runJournal(subset,{outDir,transport,interruptAfter});
 const reconciled=reconcileGeneration(plan,{updates:result.records});
 const older=new Map(previous.map(r=>[pkOf(r),r]));
 const fresh=new Map(result.records.map(r=>[pkOf(r),r]));
 const records=inventory.map(pk=>fresh.get(pk)??older.get(pk)).filter(Boolean);
 if(records.length!==inventory.length)throw Error('incomplete merged generation');
 for(const record of records)validateRecord(record);
 const provenance=inventory.map(pk=>({pk,state:fresh.has(pk)?'fetched_this_generation':'previous_verified_not_refreshed'}));
 return {plan,reconciled,records,provenance,metrics:result.metrics,
  invariant:{noUnaccountedStations:records.length===inventory.length,
    allUpdatedValid:true,missing:reconciled.pending.length}};
}
