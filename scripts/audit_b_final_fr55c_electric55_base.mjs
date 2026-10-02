import fs from 'node:fs/promises';
const RES='reports/electroverse/b-residual-analysis.json';
const BASE='data/national/electric55_stations_france.json';
const OUT='reports/electroverse/b-final-fr55c-electric55-base-audit.json';
const res=JSON.parse(await fs.readFile(RES,'utf8'));
const base=JSON.parse(await fs.readFile(BASE,'utf8'));
const wanted=new Map((res.unresolvedSamples||[])
 .filter(g=>String(g.irveStationId||'').startsWith('FR55C'))
 .map(g=>[String(g.irveStationId),g]));
const rows=[];
for(const [stationId,g] of wanted){
  const st=(base.stations||[]).find(s=>String(s.stationId)===stationId);
  rows.push({
    stationId,
    residualLocationPk:String(g.electroverseLocationPk),
    residualCount:g.residualCount,
    residualRefs:(g.refs||[]).map(r=>({pk:r.evsePk,ref:r.physicalReference,connectors:r.connectors})),
    found:!!st,
    station:st?{
      name:st.name,address:st.address,updatedAt:st.updatedAt??null,
      chargePoints:(st.chargePoints||[]).map(p=>({
        evseId:p.evseId,localEvseId:p.localEvseId,powerKw:p.powerKw,kind:p.kind,
        connectors:p.connectors,commissionedAt:p.commissionedAt,updatedAt:p.updatedAt,
        observations:p.observations
      }))
    }:null
  });
}
const out={generatedAt:new Date().toISOString(),baseGeneratedAt:base.generatedAt,wantedStations:wanted.size,foundStations:rows.filter(r=>r.found).length,rows};
await fs.mkdir('reports/electroverse',{recursive:true});
await fs.writeFile(OUT,JSON.stringify(out,null,2)+'\n');
console.log(JSON.stringify({baseGeneratedAt:base.generatedAt,wanted:wanted.size,found:rows.filter(r=>r.found).length,counts:rows.map(r=>({station:r.stationId,residual:r.residualCount,officialPoints:r.station?.chargePoints?.length??0}))},null,2));
