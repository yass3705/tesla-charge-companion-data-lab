import {execFileSync} from 'node:child_process';
const refs=[
"088e47b5fd7a837dff7fac7ff53d77417bf4aa74",
"80e43f9f3da8ccccd411ada6007aafe310c0467f",
"fb8386a9e0617f92b0b30098a75d9b2d598979bd",
"7e8c21dce5d550b931c396fac0fb33e5b111d909",
"eb6ea9bd58de1932087961a52e85c5bdf7bb52a7"
];
const wanted=new Set([
"FR55CP83310GRIPNEUVE",
"FR55CP33260LATP7PRVH",
"FR55CP77107MEAP62QJPP",
"FR55CP25700VALP12PRDG1",
"FR55CP84160LOUD943"
]);
const out={generatedAt:new Date().toISOString(),snapshots:[]};
for(const ref of refs){
  const raw=execFileSync('git',['show',ref+':data/national/electric55_stations_france.json'],{encoding:'utf8',maxBuffer:50*1024*1024});
  const data=JSON.parse(raw);
  const arr=Array.isArray(data)?data:(data.stations||[]);
  const rows=arr.filter(x=>wanted.has(String(x.stationId||x.irveStationId||x.id_station_itinerance||x.id)));
  out.snapshots.push({ref,rows});
}
await import('node:fs/promises').then(async fs=>{
  await fs.mkdir('reports/electroverse',{recursive:true});
  await fs.writeFile('reports/electroverse/b-electric55-history-audit.json',JSON.stringify(out,null,2)+'\n');
});
console.log(JSON.stringify(out,null,2));