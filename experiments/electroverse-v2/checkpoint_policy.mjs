// Pure, offline-only policy analysis; does not import or modify V1/V2 collectors.
export function planCheckpoints(totalBatches, {every=4, maxUncheckpointed=4}={}) {
  if (!Number.isInteger(totalBatches)||totalBatches<0||!Number.isInteger(every)||every<1||!Number.isInteger(maxUncheckpointed)||maxUncheckpointed<1) throw new Error('invalid checkpoint policy');
  const points=[];
  for(let i=1;i<=totalBatches;i++) if(i%Math.min(every,maxUncheckpointed)===0||i===totalBatches) points.push(i);
  return points;
}
export function compareCheckpointPolicies(totalBatches,{every=4,maxUncheckpointed=4}={}){
  const v2=planCheckpoints(totalBatches,{every:1,maxUncheckpointed:1});
  const candidate=planCheckpoints(totalBatches,{every,maxUncheckpointed});
  const worstCaseRedo=totalBatches===0?0:Math.min(every,maxUncheckpointed)-1;
  return {kind:'OFFLINE_POLICY_MODEL_NOT_COLLECTOR_BENCHMARK',totalBatches,
    v2:{commitPoints:v2,logicalWrites:v2.length*2},
    candidate:{commitPoints:candidate,logicalWrites:candidate.length*2,worstCaseRedoBatches:worstCaseRedo},
    assumptions:['An atomic state+checkpoint pair counts as two logical writes.',
      'Actual crash-consistency requires a single atomic generation commit or journal.',
      'Replaying a bounded number of batches does not imply identical network performance.']};
}
export function checkpointBatchBeforeOrAt(points,interruptedAfter){
  if(!Number.isInteger(interruptedAfter)||interruptedAfter<0)throw new Error('invalid interruption');
  return points.filter(n=>n<=interruptedAfter).at(-1)??0;
}
