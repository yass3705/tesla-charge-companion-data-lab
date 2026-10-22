import fs from 'node:fs/promises';
import path from 'node:path';

const ROOT='data/reve-v2';
const URL='https://www.mapareve.es/api/public/v1/locations';
const PER_PAGE=25;
const CHECKPOINT_EVERY=100;
const MAX_PAGES=800;
const BBOX={latitude_ne:44.5,longitude_ne:5.0,latitude_sw:35.5,longitude_sw:-10.5};
const ts=new Date().toISOString();
const stamp=ts.replace(/[:.]/g,'-');
const out=path.join(ROOT,'raw',stamp);
await fs.mkdir(out,{recursive:true});

const manifest={schemaVersion:2,collectedAt:ts,source:'reve-public-web',endpoint:URL,method:'POST',perPage:PER_PAGE,bbox:BBOX,pagesAttempted:0,pagesSucceeded:0,records:0,failures:[],status:'started'};
let consecutiveFailures=0;
let totalPages=null;

function rows(j){
  if(Array.isArray(j)) return j;
  for(const k of ['data','locations','results','items']) if(Array.isArray(j?.[k])) return j[k];
  return [];
}
function pageCount(j){
  for(const v of [j?.total_pages,j?.totalPages,j?.meta?.total_pages,j?.meta?.totalPages,j?.pagination?.total_pages,j?.pagination?.totalPages]){
    if(Number.isFinite(Number(v))) return Number(v);
  }
  const total=Number(j?.total ?? j?.meta?.total ?? j?.pagination?.total);
  if(Number.isFinite(total)) return Math.ceil(total/PER_PAGE);
  return null;
}
async function fetchPage(page){
  const body={page,per_page:PER_PAGE,...BBOX};
  for(let attempt=1;attempt<=4;attempt++){
    try{
      const res=await fetch(URL,{method:'POST',headers:{accept:'application/json','content-type':'application/json','user-agent':'TCC-REVE-V2/2.0'},body:JSON.stringify(body),signal:AbortSignal.timeout(15000)});
      const text=await res.text();
      if(res.ok) return {ok:true,status:res.status,text,body};
      if(res.status===400||res.status===403) return {ok:false,status:res.status,text,body,noRetry:true};
      if(attempt<4) await new Promise(r=>setTimeout(r,Math.min(8000,500*2**(attempt-1))));
      else return {ok:false,status:res.status,text,body};
    }catch(e){
      if(attempt<4) await new Promise(r=>setTimeout(r,Math.min(8000,500*2**(attempt-1))));
      else return {ok:false,error:String(e),body};
    }
  }
}

for(let page=1;page<=MAX_PAGES;page++){
  manifest.pagesAttempted++;
  const r=await fetchPage(page);
  if(!r.ok){
    manifest.failures.push({page,httpStatus:r.status??null,error:r.error??null,response:r.text?.slice(0,500)??null});
    consecutiveFailures++;
    if(r.noRetry||consecutiveFailures>=3) break;
    continue;
  }
  consecutiveFailures=0;
  let j;
  try{ j=JSON.parse(r.text); }catch(e){
    manifest.failures.push({page,httpStatus:r.status,error:'invalid-json'});
    break;
  }
  const data=rows(j);
  if(page===1){
    totalPages=pageCount(j);
    manifest.reportedTotalPages=totalPages;
    manifest.firstPageKeys=Object.keys(j??{});
  }
  await fs.writeFile(path.join(out,`locations-page-${String(page).padStart(4,'0')}.json`),r.text);
  manifest.pagesSucceeded++;
  manifest.records+=data.length;
  if(page % CHECKPOINT_EVERY===0){
    manifest.checkpoint={page,records:manifest.records,at:new Date().toISOString()};
    await fs.writeFile(path.join(out,'manifest.checkpoint.json'),JSON.stringify(manifest,null,2)+'\n');
  }
  console.log(`page ${page}: ${data.length} records; total=${manifest.records}`);
  if(data.length===0 || data.length<PER_PAGE || (totalPages && page>=totalPages)){
    manifest.endedByShortPage=data.length<PER_PAGE;
    break;
  }
  await new Promise(r=>setTimeout(r,100));
}
manifest.paginationComplete=manifest.failures.length===0&&manifest.pagesSucceeded>0&&
  (totalPages?manifest.pagesSucceeded===totalPages:manifest.endedByShortPage===true);
manifest.status=manifest.paginationComplete?'captured':'failed';
manifest.completedAt=new Date().toISOString();
await fs.writeFile(path.join(out,'manifest.json'),JSON.stringify(manifest,null,2)+'\n');
console.log(JSON.stringify(manifest,null,2));
if(manifest.status==='failed') process.exitCode=2;
