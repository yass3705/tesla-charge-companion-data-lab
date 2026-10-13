// Read-only, bounded UK Electroverse inventory listing around eligible CPO seeds.
// Tile IDs are discovery evidence only; prices require later EVSE-level checks.
import fs from 'node:fs/promises';
import zlib from 'node:zlib';
import {DirectElectroverseClient} from './lib/electroverse_direct_client.mjs';
import {tileHits,xy} from './electroverse_uk_cpo_pilot.mjs';

const Z=10,MAX_TILES=60;
const batchIndex=Number(process.argv[2]??0),batchSize=Number(process.argv[3]??40);
if(!Number.isInteger(batchIndex)||batchIndex<0||!Number.isInteger(batchSize)||batchSize<1||batchSize>MAX_TILES)
  throw Error('batch index >=0 and batch size 1..60 required');
const source=JSON.parse(zlib.gunzipSync(await fs.readFile('data/platforms/electroverse/uk-national-cpo-seeds.json.gz')));
if(source.status!=='cpo_seed_queue_only_no_emsp_claim')throw Error('invalid seed queue');
const tileSet=new Set();
for(const place of source.locations){
  // ±0.002° includes neighbouring z10 tiles when an EVSE lies close to a border.
  for(const dlat of [-.002,0,.002])for(const dlon of [-.002,0,.002]){
    const [x,y]=xy(place.latitude+dlat,place.longitude+dlon,Z);
    tileSet.add(`${x}/${y}`);
  }
}
const tiles=[...tileSet].sort((a,b)=>{
  const [ax,ay]=a.split('/').map(Number),[bx,by]=b.split('/').map(Number);
  return ax-bx||ay-by;
});
const selected=tiles.slice(batchIndex*batchSize,(batchIndex+1)*batchSize);
if(!selected.length)throw Error(`empty batch ${batchIndex}, total tiles ${tiles.length}`);
const client=new DirectElectroverseClient({timeoutMs:30000});
const rows=[],errors=[];
for(const tile of selected){
  const response=await fetch(`https://api.electroverse.com/rest/locations/tiles/elastic/${Z}/${tile}`,{
    headers:client.headers(),signal:AbortSignal.timeout(30000)}).catch(error=>({error:String(error)}));
  if(response.error||!response.ok){
    errors.push({tile,status:response.status||0,error:response.error||`HTTP ${response.status}`,
      retryAfter:response.headers?.get('retry-after')||null});
    break;
  }
  const [x,y]=tile.split('/').map(Number);
  const hits=tileHits(new Uint8Array(await response.arrayBuffer()),Z,x,y);
  rows.push({tile,hits,possibleTruncation:hits.length>=1950});
  await new Promise(resolve=>setTimeout(resolve,750));
}
const report={schemaVersion:1,generatedAt:new Date().toISOString(),country:'GB',
  status:errors.length?'incomplete':'tile_ids_only_no_emsp_tariffs',
  seedLocationCount:source.locationCount,z:Z,totalTiles:tiles.length,
  batchIndex,batchSize,selectedTiles:selected.length,completedTiles:rows.length,
  distinctLocationPks:new Set(rows.flatMap(x=>x.hits.map(h=>h.pk))).size,
  hitsWithoutCoarsePosition:rows.reduce((n,r)=>n+r.hits.filter(h=>h.latitude==null||h.longitude==null).length,0),
  possibleTruncatedTiles:rows.filter(x=>x.possibleTruncation).map(x=>x.tile),
  rows,errors};
await fs.mkdir('reports/emsp-national/electroverse-uk-tiles',{recursive:true});
const path=`reports/emsp-national/electroverse-uk-tiles/batch-${String(batchIndex).padStart(3,'0')}.json.gz`;
await fs.writeFile(path,zlib.gzipSync(Buffer.from(JSON.stringify(report))));
console.log(JSON.stringify({path,status:report.status,seedLocationCount:report.seedLocationCount,
  totalTiles:report.totalTiles,selectedTiles:report.selectedTiles,completedTiles:report.completedTiles,
  distinctLocationPks:report.distinctLocationPks,possibleTruncatedTiles:report.possibleTruncatedTiles.length,
  errors:report.errors}));
if(errors.length)process.exitCode=2;
