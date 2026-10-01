import fs from 'node:fs/promises';
import zlib from 'node:zlib';

const OVERLAY='data/platforms/electroverse/france-evse';
const CACHE='data/electroverse/tariff_cache';
const OUT='reports/electroverse/b-published-rule-audit.json';
const norm=x=>String(x??'').trim().toUpperCase().replace(/[^A-Z0-9]/g,'');
const parseB=raw=>{
  const s=String(raw??'').trim().toUpperCase();
  const m=s.match(/^B0*([1-9]\d*)\b/);
  return m?Number(m[1]):null;
};

const cman=JSON.parse(await fs.readFile(CACHE+'/manifest.json','utf8'));
const src=new Map();
for(const sh of cman.shards||[]){
  const d=JSON.parse(await fs.readFile(CACHE+'/'+sh.file,'utf8'));
  for(const row of Object.values(d.stations||{})){
    for(const e of row?.tariff?.evses||[]){
      if(e?.pk==null)continue;
      const b=parseB(e.physicalReference);
      if(b==null)continue;
      src.set(String(e.pk),{locationPk:String(row.electroverseLocationPk),pk:e.pk,raw:String(e.physicalReference),b,connectors:(e.connectors||[]).map(c=>({kw:c?.kilowatts??null,std:c?.standard?.name??c?.standard??null}))});
    }
  }
}
const man=JSON.parse(await fs.readFile(OVERLAY+'/manifest.json','utf8'));
const rows=[];
for(const t of man.tiles||[]){
  const tile=JSON.parse(zlib.gunzipSync(await fs.readFile(OVERLAY+'/'+t.file)));
  for(const o of tile.emspOffers||[]){
    const ids=(o.evseIds||[]).map(norm).filter(Boolean);
    const pks=[...(o?.metadata?.electroverseEvsePks||[])];
    if(o?.metadata?.electroverseEvsePk!=null)pks.push(o.metadata.electroverseEvsePk);
    for(const pk0 of pks){
      const x=src.get(String(pk0)); if(!x)continue;
      for(const target of ids){
        const m=target.match(/(\d+)$/);
        const tail=m?m[1]:null;
        rows.push({...x,target,targetTail:tail,identityMode:o?.metadata?.identityMode??null,offerGranularity:o?.metadata?.offerGranularity??null});
      }
    }
  }
}
const identityRows=rows.filter(r=>[
  'strict_55c_bindex_zero_based_suffix'
].includes(r.identityMode));
const relation={};
for(const r of identityRows){
  const tail=r.targetTail;
  const key=tail==null?'none':
    Number(tail)===r.b-1?'b_minus_1':
    Number(tail)===r.b?'b_equal':
    Number(tail.slice(-2))===r.b-1?'last2_b_minus_1':
    Number(tail.slice(-2))===r.b?'last2_b_equal':'other';
  relation[key]=(relation[key]||0)+1;
}
const samples={};
for(const k of Object.keys(relation))samples[k]=identityRows.filter(r=>{
  const tail=r.targetTail;
  const kk=tail==null?'none':
    Number(tail)===r.b-1?'b_minus_1':
    Number(tail)===r.b?'b_equal':
    Number(tail.slice(-2))===r.b-1?'last2_b_minus_1':
    Number(tail.slice(-2))===r.b?'last2_b_equal':'other';
  return kk===k;
}).slice(0,25);
const offsets={};
for(const r of identityRows){
  const m=String(r.target).match(/(\d+)$/); if(!m)continue;
  const digits=m[1];
  for(const width of [1,2,3]){
    if(digits.length<width)continue;
    const n=Number(digits.slice(-width));
    const off=n-(r.b-1);
    const key=width+':'+off;
    offsets[key]=(offsets[key]||0)+1;
  }
}
const out={generatedAt:new Date().toISOString(),publishedBSourceTargetPairs:rows.length,identityRows:identityRows.length,relation,offsets,samples};
await fs.mkdir('reports/electroverse',{recursive:true});
await fs.writeFile(OUT,JSON.stringify(out,null,2)+'\n');
console.log(JSON.stringify(out,null,2));
