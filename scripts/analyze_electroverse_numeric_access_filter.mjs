import fs from 'node:fs/promises';

const NUMERIC='reports/electroverse/numeric-analysis.json';
const LEDGER='reports/france/irve-public-access-validation-ledger.json';
const OUT='reports/electroverse/numeric-access-filtered.json';
const TOTAL='reports/electroverse/total-tariff-coherence-candidates.json';

const numeric=JSON.parse(await fs.readFile(NUMERIC,'utf8'));
const ledger=JSON.parse(await fs.readFile(LEDGER,'utf8'));
const decisions=Array.isArray(ledger.decisions)?ledger.decisions:[];
const excluded=new Set();
for(const d of decisions){
  if(d?.decision!=='exclude_non_public') continue;
  for(const id of d.stationIds||[]) if(id) excluded.add(String(id));
}

const rows=[];
const totalCandidates=[];
for(const bucket of numeric.buckets||[]){
  const kept=[];
  let excludedResidual=0;
  for(const g of bucket.groups||[]){
    const station=String(g.irveStationId??'');
    if(excluded.has(station)){
      excludedResidual+=Number(g.residualCount||0);
      rows.push({bucket:bucket.bucket,electroverseLocationPk:String(g.electroverseLocationPk),irveStationId:station,residualCount:Number(g.residualCount||0),reason:'exclude_non_public',source:'reports/france/irve-public-access-validation-ledger.json'});
      continue;
    }
    kept.push(g);
    if(bucket.bucket==='NUMERIC' && station==='FRTCBP05235' && Number(g.residualCount)===22 && Number(g.availablePdcCount)===22){
      totalCandidates.push({
        electroverseLocationPk:String(g.electroverseLocationPk),
        irveStationId:station,
        residualCount:22,
        availablePdcCount:22,
        status:'candidate_tariff_coherence_only',
        cpo:'TotalEnergies',
        expectedGroups:[
          {connector:'Type 2',powerKw:7,count:16,electroverseTariffEurPerKwh:0.52},
          {connector:'CCS',powerKw:200,count:6,electroverseTariffEurPerKwh:0.65}
        ],
        rule:'Accept only if the IRVE/CPO fingerprint confirms the same station, connector/power cardinalities, and one tariff per power group; no individual PDC permutation is inferred.',
        evidence:['IRVE station FRTCBP05235','Electroverse tariff manually verified by user on 2026-10-03']
      });
    }
  }
  if(kept.length!== (bucket.groups||[]).length){
    rows.push({bucket:bucket.bucket,keptGroups:kept.length,excludedResidual,excludedStationCount:new Set(rows.filter(x=>x.bucket===bucket.bucket&&x.reason==='exclude_non_public').map(x=>x.irveStationId)).size});
  }
}
const filtered={schemaVersion:1,generatedAt:new Date().toISOString(),policy:{
  excludedDecision:'exclude_non_public',
  note:'Non-public IRVE stations are removed from the candidate/result perimeter; they remain in the source datasets.',
  totalFallback:'CPO tariff in the FR base has priority; Electroverse coherence is accepted only as a candidate until the IRVE fingerprint is complete.'
},excludedStationCount:excluded.size,excludedGroups:rows.filter(x=>x.reason==='exclude_non_public'),summary:rows.filter(x=>x.keptGroups!==undefined)};
await fs.mkdir('reports/electroverse',{recursive:true});
await fs.writeFile(OUT,JSON.stringify(filtered,null,2)+'\n');
await fs.writeFile(TOTAL,JSON.stringify({schemaVersion:1,generatedAt:filtered.generatedAt,policy:filtered.policy,candidates:totalCandidates},null,2)+'\n');
console.log(JSON.stringify({excludedStationCount:excluded.size,excludedGroups:filtered.excludedGroups.length,excludedResidual:filtered.excludedGroups.reduce((n,x)=>n+x.residualCount,0),totalCandidates:totalCandidates.length},null,2));
