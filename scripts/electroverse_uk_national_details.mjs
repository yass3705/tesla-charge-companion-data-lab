// Bounded source-only Electroverse detail collection. No EVSE or price promotion.
import fs from 'node:fs/promises';
import zlib from 'node:zlib';
import {pathToFileURL} from 'node:url';
import {DirectElectroverseClient, EVSE_FIELDS, PAGED_LOCATION_QUERY} from './lib/electroverse_direct_client.mjs';
import {connectorKind} from './electroverse_uk_cpo_pilot.mjs';

const INPUT='data/platforms/electroverse/uk-coarse-location-candidates.json.gz';
const OUT='reports/emsp-national/electroverse-uk-details';
const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));

export function retainAllowed(location){
  if(!location)return null;
  const evses=(location.evses?.edges||[]).map(edge=>{
    const evse=edge.node;
    const connectors=(evse?.connectors?.edges||[]).map(e=>e.node)
      .filter(c=>connectorKind(c?.standard?.name));
    return connectors.length?{pk:evse.pk,physicalReference:evse.physicalReference,
      status:evse.status,connectors}:null;
  }).filter(Boolean);
  return {chargingLocationPk:location.chargingLocationPk,name:location.name,
    coordinates:location.coordinates,operator:location.operator,
    hasMoreEvses:Boolean(location.evses?.pageInfo?.hasNextPage),
    endCursor:location.evses?.pageInfo?.endCursor||null,evses};
}

function query(pks){
  return `query UkNationalDetails { ${pks.map((pk,i)=>
    `s${i}:chargingLocation(pk:${JSON.stringify(pk)}) {
      chargingLocationPk name coordinates operator { name }
      evses(first:100) { edges { node { ${EVSE_FIELDS} } }
        pageInfo { hasNextPage endCursor } }
    }`).join('\n')} }`;
}

export async function main(args=process.argv.slice(2)){
  const offset=Number(args[0]??0),count=Number(args[1]??100);
  if(!Number.isInteger(offset)||offset<0||!Number.isInteger(count)||count<1||count>100)
    throw Error('offset must be nonnegative and count must be 1..100');
  const input=JSON.parse(zlib.gunzipSync(await fs.readFile(INPUT)));
  if(input.status!=='coarse_candidates_not_evse_links' || input.coveredTiles!==415)
    throw Error('unexpected UK candidate queue');
  const slice=input.candidates.slice(offset,offset+count);
  if(slice.length!==count)throw Error('requested range exceeds candidate queue');
  const client=new DirectElectroverseClient({timeoutMs:45000});
  const rows=[];let requests=0;
  for(let start=0;start<slice.length;start+=5){
    const group=slice.slice(start,start+5);
    if(++requests>30)throw Error('request cap exceeded');
    const response=await client.request(query(group.map(x=>x.electroversePk)),{}, {attempts:1});
    if(response.status!==200||response.json?.errors?.length||!response.json?.data)
      throw Error(`GraphQL batch failed at offset ${offset+start}: HTTP ${response.status}; ${(response.json?.errors||[]).map(x=>x.message).join(';').slice(0,160)}`);
    for(let i=0;i<group.length;i++){
      const source=retainAllowed(response.json.data[`s${i}`]);
      while(source?.hasMoreEvses){
        if(!source.endCursor||++requests>30)throw Error(`EVSE pagination/cap at PK ${group[i].electroversePk}`);
        await pause(1000);
        const next=await client.request(PAGED_LOCATION_QUERY,
          {pk:group[i].electroversePk,first:100,after:source.endCursor},{attempts:1});
        if(next.status!==200||next.json?.errors?.length||!next.json?.data?.chargingLocation)
          throw Error(`EVSE page failed at PK ${group[i].electroversePk}: HTTP ${next.status}`);
        const page=retainAllowed(next.json.data.chargingLocation);
        if(!page||String(page.chargingLocationPk)!==group[i].electroversePk)
          throw Error(`EVSE page PK mismatch at ${group[i].electroversePk}`);
        source.evses.push(...page.evses);
        if(page.hasMoreEvses&&page.endCursor===source.endCursor)
          throw Error(`EVSE cursor did not advance at ${group[i].electroversePk}`);
        source.hasMoreEvses=page.hasMoreEvses;
        source.endCursor=page.endCursor;
      }
      if(source&&String(source.chargingLocationPk)!==group[i].electroversePk)
        throw Error(`PK mismatch at ${group[i].electroversePk}`);
      rows.push({electroversePk:group[i].electroversePk,
        coarseCoordinates:group[i].coarseCoordinates,
        nearbyCpoSeeds:group[i].nearbyCpoSeeds,
        source});
    }
    if(start+5<slice.length)await pause(1000);
  }
  const report={schemaVersion:1,generatedAt:new Date().toISOString(),country:'GB',
    status:'source_details_only_no_evse_link_or_tariff_promotion',candidateQueueSize:input.candidates.length,
    offset,count,requests,rows};
  await fs.mkdir(OUT,{recursive:true});
  const file=`${OUT}/offset-${String(offset).padStart(5,'0')}-count-${count}.json.gz`;
  await fs.writeFile(file,zlib.gzipSync(JSON.stringify(report)+'\n'));
  console.log(JSON.stringify({file,offset,count,requests,locationsFound:rows.filter(x=>x.source).length,
    locationsWithAllowedConnector:rows.filter(x=>x.source?.evses.length).length,
    evsesWithAllowedConnector:rows.reduce((n,x)=>n+(x.source?.evses.length||0),0)}));
}
if(process.argv[1]&&import.meta.url===pathToFileURL(process.argv[1]).href)await main();
