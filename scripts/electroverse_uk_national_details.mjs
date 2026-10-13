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

export async function boundedRequest(client, gql, variables, state, delayMs=20000){
  let response;
  for(let attempt=0;attempt<2;attempt++){
    if(++state.requests>30)throw Error('request cap exceeded');
    response=await client.request(gql,variables,{attempts:1});
    if(response.status===200&&!response.json?.errors?.length&&response.json?.data)
      return response.json.data;
    const transient=response.status===200||response.status===429||response.status>=500;
    if(!transient||attempt===1)break;
    await pause(delayMs);
  }
  throw Error(`GraphQL HTTP ${response.status}: ${(response.json?.errors||[]).map(x=>x.message).join(';').slice(0,160)}`);
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
  const rows=[],state={requests:0};let failure=null;
  try { for(let start=0;start<slice.length;start+=5){
    const group=slice.slice(start,start+5);
    const data=await boundedRequest(client,query(group.map(x=>x.electroversePk)),{},state);
    for(let i=0;i<group.length;i++){
      const source=retainAllowed(data[`s${i}`]);
      while(source?.hasMoreEvses){
        if(!source.endCursor)throw Error(`EVSE pagination cursor missing at PK ${group[i].electroversePk}`);
        await pause(1000);
        const next=await boundedRequest(client,PAGED_LOCATION_QUERY,
          {pk:group[i].electroversePk,first:100,after:source.endCursor},state);
        const page=retainAllowed(next.chargingLocation);
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
  }} catch(error){failure=error;}
  const report={schemaVersion:1,generatedAt:new Date().toISOString(),country:'GB',
    status:failure?'partial_source_details_no_tariff_promotion':'source_details_only_no_evse_link_or_tariff_promotion',
    candidateQueueSize:input.candidates.length,offset,count,requests:state.requests,
    nextOffset:offset+rows.length,failure:failure?String(failure).slice(0,220):null,rows};
  await fs.mkdir(OUT,{recursive:true});
  const file=`${OUT}/offset-${String(offset).padStart(5,'0')}-count-${count}.json.gz`;
  await fs.writeFile(file,zlib.gzipSync(JSON.stringify(report)+'\n'));
  console.log(JSON.stringify({file,offset,count,requests:state.requests,nextOffset:report.nextOffset,status:report.status,
    locationsFound:rows.filter(x=>x.source).length,
    locationsWithAllowedConnector:rows.filter(x=>x.source?.evses.length).length,
    evsesWithAllowedConnector:rows.reduce((n,x)=>n+(x.source?.evses.length||0),0)}));
  if(failure)throw failure;
}
if(process.argv[1]&&import.meta.url===pathToFileURL(process.argv[1]).href)await main();
