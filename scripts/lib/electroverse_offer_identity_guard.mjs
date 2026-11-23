/**
 * Fail-closed guard for duplicate offer identities after all mapping and
 * deduplication passes. The same provider offer ID cannot describe multiple
 * prices or connector scopes. Quarantine ALL conflicting rows rather than
 * choosing a tariff without evidence. The national master remains unchanged.
 */
export function quarantineDuplicateOfferIds(tileMap) {
  if (!(tileMap instanceof Map)) throw Error('Expected a tile map');
  const encountered=new Map(),duplicates=new Set();
  for(const [tile, offers] of tileMap) {
    if(!Array.isArray(offers)) throw Error('Expected offer array for tile '+tile);
    for(const offer of offers) {
      const id=offer?.id;
      if(typeof id!=='string'||!id) throw Error('Untrusted blank offer identity');
      if(encountered.has(id)) duplicates.add(id);
      else encountered.set(id,{tile,offer});
    }
  }
  const quarantined=new Map();
  let excludedRows=0;
  for(const [tile,offers] of tileMap) {
    const keep=offers.filter(o=>!duplicates.has(o.id));
    excludedRows+=offers.length-keep.length;
    quarantined.set(tile,keep);
  }
  return {
    tiles:quarantined,
    duplicateIds:[...duplicates].sort(),
    quarantinedRows:excludedRows,
    sourceOfferCount:[...tileMap.values()].reduce((n,offers)=>n+offers.length,0),
  };
}
