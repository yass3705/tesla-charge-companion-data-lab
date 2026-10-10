// Electra app-check shortlist; strictly evidence requests, never publish guessed tariffs.
import fs from 'node:fs/promises';
import zlib from 'node:zlib';
const load=async p=>JSON.parse(zlib.gunzipSync(await fs.readFile(p)).toString('utf8'));
const root='reports/france/irve/';
const cases=(await load(root+'electra-pricing-residual-cases-2026-10-08.json.gz')).cases;
const locations=(await load('data/platforms/electra/france/source-locations.json.gz')).locations;
const src=new Map(locations.map(x=>[String(x.id),x]));
const str=x=>String(x??'').trim();
const outputs='reports/france/electra/';
await fs.mkdir(outputs,{recursive:true});
const cap=values=>[...new Set(values.filter(x=>Number.isFinite(x)))].sort((a,b)=>a-b);
function rates(loc){
 const values=[],fees=[];
 for(const t of loc.chargeTariffs||[])for(const e of t.elements||[])for(const p of e.priceComponents||[]){
  if(p.type==='ENERGY'&&Number.isFinite(Number(p.price)))values.push(Number(p.price));
  if(p.type!=='ENERGY'&&Number.isFinite(Number(p.price)))fees.push(p.type+':'+p.price);
 }
 return {eurPerKwh:cap(values),fees:[...new Set(fees)].slice(0,12)};
}
const byCpo=new Map(),histogram={},modes={};
for(const c of cases){
 const loc=src.get(c.locationId);if(!loc)continue;
 const t=c.triage||{},names=(loc.evses||[]).map(e=>str(e.evseId)).filter(Boolean);
 const energy=Boolean(t.energyPriceVariation),anc=Boolean(t.ancillaryPriceVariation),rest=Boolean(t.restrictionVariation);
 const pattern=(energy?'energy+':'')+(anc?'ancillary+':'')+(rest?'restriction+':'')||'other+';
 const key=pattern.slice(0,-1);histogram[key]=(histogram[key]||0)+1;
 const klass=t.class||'unknown';modes[klass]=(modes[klass]||0)+1;
 const address=[loc.address,loc.postalCode,loc.city].map(str).filter(Boolean).join(', ');
 const knownPower=t.distinctKnownPowers||[];
 const canSearch=Boolean(str(loc.name)&&str(loc.city)&&loc.coordinates);
 const isPdcShort=names.length<=6&&names.length>=2;
 const stationData={
   priority:null,operator:str(c.cpo),name:str(loc.name),city:str(loc.city),postalCode:str(loc.postalCode),address:str(loc.address),
   country:str(loc.country),lat:loc.coordinates?.latitude??null,lon:loc.coordinates?.longitude??null,
   electraLocationId:c.locationId,evseIds:names,knownPowersKw:knownPower,sourceMaxPowerW:loc.maxPower??null,
   connectorTypes:loc.connectorTypes||[],differentTariffs:c.tariffCount,
   sourceTariffIds:(loc.chargeTariffs||[]).map(x=>x.chargeTariffId||x.id).filter(Boolean),
   observedCandidatePrices:rates(loc),uncertaintyClass:klass,variationKind:key,
   sourceEvidence:'Electra eMSP GraphQL station snapshot',
   instruction:'Dans l’app Electra, ouvrir cette station et chaque puissance/borne; relever prix au kWh, frais annexes, horaire, offre/profil et capture montrant l’identifiant de borne. Ne pas se fier au prix global de la station.',
   note:'Les tarifs listés sont des candidats de la source et non des prix associés avec certitude aux EVSE.',
   sourceEvseCount:t.sourceEvseCount||names.length
 };
 if(!canSearch)continue;
 let score=(isPdcShort?25:0)+(knownPower.length>0?15:0)+(c.tariffCount>=2&&c.tariffCount<=3?20:0)+(energy?12:0)+(anc?3:0)+
    (str(loc.address)?10:0)+(names.length<=4?12:0)+(str(loc.name).length>=12?7:0);
 if(c.cpo==='Electra')score+=30;
 (byCpo.get(c.cpo)||byCpo.set(c.cpo,[]).get(c.cpo)).push({...stationData,score});
}
for(const rows of byCpo.values())rows.sort((a,b)=>b.score-a.score||a.electraLocationId.localeCompare(b.electraLocationId));
const quotas=[['Electra',7],['Powerdot',3],['DRIVECO',3],['Freshmile',2],['Izivia',2],['TotalEnergies',2],['Mobive',2],['Greenflux',2],['Révéo',2],['E-Totem',2],['Carrefour',1]];
const chosen=[],pickedIds=new Set(),pickedCities=new Map();
for(const [cpo,n] of quotas){
 let count=0;for(const r of byCpo.get(cpo)||[]){
  if(count>=n)break;
  const cityKey=cpo+'|'+r.city.toLowerCase();
  if(pickedCities.has(cityKey)||pickedIds.has(r.electraLocationId))continue;
  chosen.push(r);pickedIds.add(r.electraLocationId);pickedCities.set(cityKey,true);count++;
 }
}
// The first app-check batch must cover distinct operator families, not only
// the first CPO in the quota list. Leave the remaining cases available as P2.
const p1Plan=[['Electra',5],['Powerdot',2],['DRIVECO',1],['Freshmile',1],['Izivia',1],['TotalEnergies',1],['Mobive',1]];
const p1=[],p1Ids=new Set();
for(const [name,n] of p1Plan){
 for(const x of chosen.filter(z=>z.operator===name).slice(0,n)){p1.push(x);p1Ids.add(x.electraLocationId);}
}
const ordered=[...p1,...chosen.filter(x=>!p1Ids.has(x.electraLocationId))];
let rank=0;
for(const row of ordered){rank++;row.priority=rank<=p1.length?'P1':'P2';row.rank=rank;delete row.score;}
chosen.splice(0,chosen.length,...ordered);
function csv(v){let s=str(v);return /[;"\n\r]/.test(s)?'"'+s.replaceAll('"','""')+'"':s;}
const fields=[
 ['rank','Ordre'],['priority','Priorite'],['operator','Operateur'],['name','Nom station dans Electra'],['city','Ville'],
 ['postalCode','Code postal'],['address','Adresse'],['lat','Latitude'],['lon','Longitude'],
 ['electraLocationId','Identifiant station Electra'],['evseIds','EVSE a verifier'],['knownPowersKw','Puissances kW identifiees'],
 ['differentTariffs','Grilles tarifaires presentes'],['observedCandidatePrices','Tarifs candidats non attribues'],
 ['variationKind','Type de divergence'],['uncertaintyClass','Cause blocage'],['instruction','Capture a fournir']];
function cell(row,key){const v=row[key];if(key==='observedCandidatePrices')return v.eurPerKwh.join('|')+' EUR/kWh; annexes: '+v.fees.join('|');return Array.isArray(v)?v.join('|'):v;}
const rows=[fields.map(x=>csv(x[1])).join(';'),...chosen.map(row=>fields.map(x=>csv(cell(row,x[0]))).join(';'))];
const file=outputs+'app-verification-shortlist-latest.csv';
await fs.writeFile(file,String.fromCharCode(0xFEFF)+rows.join(String.fromCharCode(10))+String.fromCharCode(10));
const summary={
 schemaVersion:1,generatedAt:new Date().toISOString(),sourceCaseCount:cases.length,sourceLocationCount:locations.length,
 shortlistCount:chosen.length,priority1:chosen.filter(x=>x.priority==='P1').length,priority2:chosen.filter(x=>x.priority==='P2').length,
 byCpo:Object.fromEntries([...byCpo.entries()].map(([k,v])=>[k,v.length]).sort((a,b)=>b[1]-a[1])),
 variationPatterns:histogram,uncertaintyClasses:modes,
 publicationDecision:'none; manual evidence required',
 screenshotRequirements:['Borne exacte/identifiant EVSE ou numéro du connecteur','Puissance AC/DC annoncée','Prix de recharge pour le compte Electra sans réduction de profil','Frais de temps, parking et congestion','Créneaux horaires et jours si prix variables','Capture de chaque variante de puissance'],
 shortlistFile:file,stations:chosen
};
await fs.writeFile(outputs+'app-verification-shortlist-latest.json',JSON.stringify(summary,null,2)+'\n');
console.log(JSON.stringify({shortlist:chosen.length,P1:summary.priority1,P2:summary.priority2,sourceCaseCount:cases.length,variationPatterns:histogram,operators:chosen.map(x=>x.operator),first:chosen.slice(0,5).map(x=>({name:x.name,city:x.city,cpo:x.operator,powers:x.knownPowersKw,prices:x.observedCandidatePrices.eurPerKwh}))}).slice(0,7500));
