import test from 'node:test';
import assert from 'node:assert/strict';
import {planCheckpoints,compareCheckpointPolicies,checkpointBatchBeforeOrAt} from './checkpoint_policy.mjs';
test('five batches checkpoint every four plus final',()=>assert.deepEqual(planCheckpoints(5,{every:4}),[4,5]));
test('zero batches generates no writes',()=>assert.deepEqual(planCheckpoints(0),[]));
test('max-uncheckpointed caps interval',()=>assert.deepEqual(planCheckpoints(10,{every:7,maxUncheckpointed:3}),[3,6,9,10]));
test('write counts are theoretical and bounded',()=>{const r=compareCheckpointPolicies(5,{every:4});assert.equal(r.v2.logicalWrites,10);assert.equal(r.candidate.logicalWrites,4);assert.equal(r.candidate.worstCaseRedoBatches,3)});
test('replay estimates after interruption',()=>{const points=planCheckpoints(5,{every:4});assert.equal(checkpointBatchBeforeOrAt(points,2),0);assert.equal(checkpointBatchBeforeOrAt(points,4),4)});
test('reject invalid configuration',()=>assert.throws(()=>planCheckpoints(10,{every:0})));
