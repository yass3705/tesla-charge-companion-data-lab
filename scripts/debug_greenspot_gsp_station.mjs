import fs from 'node:fs/promises';
import zlib from 'node:zlib';

const raw=zlib.gunzipSync(await fs.readFile('data/greenspot/france/greenspot-france-current.json.gz')).toString('utf8');
const j=JSON.parse(raw);
const station='FRGSPP90329287';
const pdcs=new Set(['FRGSPE12345958361','FRGSPE12345958371']);
const hits=(j.records||[]).filter(r=>
  String(r?.irve?.id_station_itinerance||'')===station ||
  pdcs.has(String(r?.irve?.id_pdc_itinerance||'')) ||
  pdcs.has(String(r?.evseKey||''))
);
await fs.mkdir('reports/electroverse',{recursive:true});
const report={
  generatedAt:new Date().toISOString(),
  source:'data/greenspot/france/greenspot-france-current.json.gz',
  station,
  requestedEvseKeys:[...pdcs],
  hitCount:hits.length,
  hits
};
await fs.writeFile(
  'reports/electroverse/gsp-greenspot-debug.json',
  JSON.stringify(report,null,2)+'\n',
  'utf8'
);
console.log(JSON.stringify(report,null,2));
