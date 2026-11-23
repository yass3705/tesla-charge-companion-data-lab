import test from 'node:test';
import assert from 'node:assert/strict';
import {quarantineDuplicateOfferIds} from '../scripts/lib/electroverse_offer_identity_guard.mjs';

test('different tariffs with one offer ID are BOTH quarantined, without picking a price',()=>{
 const a={id:'same',pricing:{rules:[{price:0.7}]}};
 const b={id:'same',pricing:{rules:[{price:1.1}]}};
 const healthy={id:'independent',pricing:{rules:[{price:0.4}]}};
 const original=new Map([['t_a',[a,healthy]],['t_b',[b]]]);
 const screened=quarantineDuplicateOfferIds(original);
 assert.deepEqual(screened.duplicateIds,['same']);
 assert.equal(screened.quarantinedRows,2);
 assert.deepEqual(screened.tiles.get('t_a'),[healthy]);
 assert.deepEqual(screened.tiles.get('t_b'),[]);
 assert.deepEqual(original.get('t_a'),[a,healthy],'original observations remain immutable');
});

test('even identical duplicated offer IDs must be quarantined pending unique source identity',()=>{
 const a={id:'same',pricing:{}},b={id:'same',pricing:{}};
 const out=quarantineDuplicateOfferIds(new Map([['x',[a,b]]]));
 assert.equal(out.quarantinedRows,2);
 assert.equal(out.duplicateIds.length,1);
});

test('unique offers and distinct priced variants with distinct explicit IDs are preserved',()=>{
 const a={id:'location:target:22kw',pricing:{}};
 const b={id:'location:target:7kw',pricing:{}};
 const out=quarantineDuplicateOfferIds(new Map([['x',[a,b]]]));
 assert.equal(out.quarantinedRows,0);
 assert.deepEqual(out.tiles.get('x'),[a,b]);
});

test('blank or non-string identities fail the build instead of risking an ambiguous publication',()=>{
 assert.throws(()=>quarantineDuplicateOfferIds(new Map([['x',[{id:''}]])),/blank offer identity/);
 assert.throws(()=>quarantineDuplicateOfferIds(new Map([['x',[{id:17}]])),/blank offer identity/);
});
