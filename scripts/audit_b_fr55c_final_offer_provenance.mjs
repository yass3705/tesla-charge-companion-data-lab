import fs from 'node:fs/promises';import zlib from 'node:zlib';
const MAN='data/platforms/electroverse/france-evse/manifest.json';
const OUT='reports/electroverse/b-fr55c-final-offer-provenance-audit.json';
const targets=new Set([
'FR55CEFR83310PNEUVE0','FR55CEFR83310PNEUVE1',
'FR55CEFR33260P7PRVH0','FR55CEFR33260P7PRVH1',
'FR55CEFR77100P62QJPP0','FR55CEFR77100P62QJPP1',
'FR55CEFR25700P12PRDG10','FR55CEFR25700P12PRDG11',
'FR55CE84160FUL1321','FR55CE84160FUL1322'
]);
const man=JSON.parse(await fs.readFile(MAN,'utf8'));const rows=[];
for(const t of man.tiles||[]){
 const d=JSON.parse(zlib.gunzipSync(await fs.readFile('data/platforms/electroverse/france-evse/'+t.file)));
 for(const o of d.emspOffers||[]){
   const evse=(o.evseIds||[])[0];if(!targets.has(evse))continue;
   rows.push({evseId:evse,id:o.id,pricing:o.pricing,metadata:o.metadata});
 }
}
const out={generatedAt:new Date().toISOString(),offerCount:rows.length,rows};
await fs.writeFile(OUT,JSON.stringify(out,null,2)+'\n');console.log(JSON.stringify(out,null,2));