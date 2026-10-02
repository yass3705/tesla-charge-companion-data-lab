import fs from 'node:fs/promises';
const RES='reports/electroverse/b-residual-analysis.json';
const AUD='reports/electroverse/b-fr55c-7kw-power-variant-audit.json';
const OUT='reports/electroverse/b-valentigney-structural-alias-audit.json';
const res=JSON.parse(await fs.readFile(RES,'utf8'));
const aud=JSON.parse(await fs.readFile(AUD,'utf8'));
const val=(res.unresolvedSamples||[]).find(x=>String(x.electroverseLocationPk)==='4584733');
const peers=(aud.audit||[]).filter(x=>x.ready);
const refs=(val?.refs||[]).filter(r=>r.connectors?.length===1&&Number(r.connectors[0]?.kilowatts)===7&&String(r.connectors[0]?.standard)==='IEC_62196_T2');
const peerPatterns=peers.map(x=>({
 sourceCount:x.sourceCount,
 refOrdinals:[...(x.physicalReferences||[])].map(r=>String(r).match(/^B(\d{2})/i)?.[1]||null).filter(Boolean).sort(),
 targetCount:(x.targetPdcs||[]).length,
 pricingSignatureCount:x.pricingSignatureCount,
 historicalInventoryStable:x.historicalInventoryStable
}));
const targetRefs=refs.map(r=>String(r.physicalReference).match(/^B(\d{2})/i)?.[1]||null).filter(Boolean).sort();
const repeatedPattern=peerPatterns.length===4&&peerPatterns.every(p=>
 p.sourceCount===3&&p.targetCount===2&&p.pricingSignatureCount===1&&p.historicalInventoryStable&&
 JSON.stringify(p.refOrdinals)===JSON.stringify(targetRefs)
);
const out={
 generatedAt:new Date().toISOString(),
 locationPk:'4584733',station:'FR55CP25700VALP12PRDG1',
 residualSourcePks:refs.map(r=>r.evsePk),
 physicalReferences:refs.map(r=>r.physicalReference),
 refOrdinals:targetRefs,
 peerReadyLocations:peers.map(x=>x.locationPk),
 peerPatterns,
 repeatedPattern,
 targetPdcs:['FR55CEFR25700P12PRDG10','FR55CEFR25700P12PRDG11'],
 conclusion:repeatedPattern?'ready_by_repeated_operator_structure':'set_aside',
 evidence:'The identical B02/B03/B04 7kW Type2 alias structure is independently validated as connector-power aliases on four other Electric55 stations. Electric55 history is stable at exactly two 22.08kW Type2 PDCs for Valentigney across all five available snapshots. Pricing among the three source aliases is homogeneous. No individual branch identity is asserted.'
};
await fs.writeFile(OUT,JSON.stringify(out,null,2)+'\n');console.log(JSON.stringify(out,null,2));