import crypto from 'node:crypto';
const digest=v=>crypto.createHash('sha256').update(JSON.stringify(v)).digest('hex');
const id=r=>String(r?.electroverseLocationPk??'');
export function planGeneration({previous=[],inventory=[],selected=[],generationId}){
 if(typeof generationId!=='string'||!generationId)throw Error('generationId required');
 if(!Array.isArray(previous)||!Array.isArray(inventory)||!Array.isArray(selected))throw Error('invalid inputs');
 const keys=new Set(),prev=new Map(),chosen=new Set();
 for(const r of previous){const pk=id(r);if(!pk||prev.has(pk)||typeof r.tariffHash!=='string'||!r.tariffHash)throw Error('invalid previous');prev.set(pk,r)}
 for(const item of inventory){const pk=String(item);if(!pk||keys.has(pk))throw Error('invalid inventory');keys.add(pk)}
 for(const item of selected){const pk=String(item);if(!keys.has(pk)||chosen.has(pk))throw Error('invalid selection');chosen.add(pk)}
 const fetch=[],retained=[],absent=[];
 for(const pk of keys){if(chosen.has(pk)||!prev.has(pk))fetch.push(pk);else retained.push({pk,tariffHash:prev.get(pk).tariffHash,provenance:'previous_verified_not_refreshed'})}
 for(const pk of prev.keys())if(!keys.has(pk))absent.push(pk);
 return {generationId,inventoryHash:digest([...keys].sort()),fetch,retained,absent,
 rule:'Retained snapshots are stale until refreshed; never mark retained as freshly checked'};
}
export function reconcileGeneration(plan,{updates=[]}={}){
 const expected=new Set(plan.fetch),seen=new Set(),accepted=[];
 for(const r of updates){const pk=id(r);if(!expected.has(pk)||seen.has(pk)||!r.tariff||typeof r.tariffHash!=='string')throw Error('invalid update identity');seen.add(pk);accepted.push({pk,tariffHash:r.tariffHash,provenance:'fetched_this_generation'})}
 return {generationId:plan.generationId,inventoryHash:plan.inventoryHash,accepted,retained:plan.retained,
 pending:plan.fetch.filter(pk=>!seen.has(pk)),absent:plan.absent};
}
