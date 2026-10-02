const fs=require('fs'),path=require('path'),crypto=require('crypto');
const root=path.resolve(__dirname,'../..');
const read=f=>fs.readFileSync(path.join(root,f),'utf8').trim().split(/\r?\n/).map(JSON.parse);
const q=(a,p)=>{const b=a.filter(Number.isFinite).sort((x,y)=>x-y);if(!b.length)return null;const k=(b.length-1)*p;return b[Math.floor(k)]+(b[Math.ceil(k)]-b[Math.floor(k)])*(k%1);};
const old='indoor/data/curated/android/2026-09-18/';
const files=fs.readdirSync(path.join(root,old)).filter(f=>/f4-(core|stairs-left|stairs-right)/.test(f)).map(f=>old+f).concat([
 'indoor/data/raw/android/2026-09-22/post-grid-four/indoor_positioning_20260922_211406.jsonl',
 'indoor/data/raw/android/2026-09-22/post-grid-four/indoor_positioning_20260922_211528.jsonl',
 'indoor/data/curated/android/2026-09-22/post-grid-four/indoor_positioning_20260922_211714-left-stairs-corrected.jsonl']);
const sessions=files.map(file=>{
 const rows=read(file),start=rows[0];let gravity=null,last=null;const points=[];
 for(const r of rows){const t=r.sensor_wall_time_ms??r.wall_time_ms;
  if(r.sensor==='accelerometer_mps2'){const a=r.values.slice(0,3),alpha=last===null?1:1-Math.exp(-Math.max(.001,Math.min(.2,(t-last)/1000)));gravity=gravity?gravity.map((v,i)=>v+alpha*(a[i]-v)):a;last=t;}
  if(r.sensor==='magnetic_field_ut'&&r.wall_time_ms-start.wall_time_ms>=2000){const m=r.values.slice(0,3);const g=gravity&&Math.hypot(...gravity);points.push({norm:Math.hypot(...m),mv:g&&t-last<=250?m.reduce((s,v,i)=>s+v*gravity[i]/g,0):null});}
 }
 const stat=key=>{const v=points.map(p=>p[key]).filter(Number.isFinite);return {n:v.length,median:q(v,.5),p10:q(v,.1),p90:q(v,.9),spread90_10:q(v,.9)-q(v,.1)};};
 return {file,sha256:crypto.createHash('sha256').update(fs.readFileSync(path.join(root,file))).digest('hex'),zone:start.label.zone_id,device:start.device,norm:stat('norm'),mv:stat('mv')};
});
const tests=['norm','norm+mv'].map(feature=>({feature,folds:sessions.map(s=>{const candidates=sessions.filter(r=>r!==s&&r.device===s.device).map(r=>({zone:r.zone,file:r.file,distance:Math.hypot(s.norm.median-r.norm.median,...(feature==='norm+mv'?[s.mv.median-r.mv.median]:[]))})).sort((a,b)=>a.distance-b.distance);return {file:s.file,truth:s.zone,predicted:candidates[0].zone,correct:s.zone===candidates[0].zone,candidates};})}));
function walk(d){return fs.readdirSync(path.join(root,d),{withFileTypes:true}).flatMap(e=>e.isDirectory()?walk(d+'/'+e.name):e.name.endsWith('.jsonl')?[d+'/'+e.name]:[]);}
const routes=walk('indoor/data/raw/android/2026-09-22').map(file=>{const r=read(file),s=r[0],route=s.label?.route_id;return {file,route,complete:r.at(-1).kind==='session_end',magneticSamples:r.filter(x=>x.sensor==='magnetic_field_ut').length,lastLabel:r.filter(x=>x.kind==='label').at(-1)?.label?.location};}).filter(r=>r.route?.includes('LEFT_STAIRS'));
const result={note:'Six stationary sessions / three anchors only. LOSO nearest session median diagnostic, no tuned weights; not production or orientation-controlled trial. First 2s excluded. mv approximate causal accelerometer EMA tau1s, max age250ms. Raw data unchanged.',sessions,tests,routes};
const out=path.join(root,'indoor/data/analysis/stationary-magnetic-20260923');fs.mkdirSync(out,{recursive:true});fs.writeFileSync(path.join(out,'evaluation.json'),JSON.stringify(result,null,2)+'\n');
console.log(JSON.stringify({sessions:sessions.map(({file,zone,norm,mv})=>({file:path.basename(file),zone,norm,mv})),tests:tests.map(t=>({feature:t.feature,correct:t.folds.filter(f=>f.correct).length,total:t.folds.length,folds:t.folds.map(({truth,predicted})=>({truth,predicted}))})),routes},null,2));
