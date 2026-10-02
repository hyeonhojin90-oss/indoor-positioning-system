const fs=require('fs'),path=require('path'),crypto=require('crypto');
const N=require('../web/src/positioning/navigation'),R=require('../web/src/positioning/runtime');
const weinberg=null;
const data=require('../web/data/navigation/areas-v1.json'),models=require('../web/data/positioning/motion-models.json');
const refs=require('../web/data/positioning/ble-references.json').references;
const root=path.resolve(__dirname,'../..'),out=path.join(root,'indoor/data/analysis/left-grid-20260923');
const map=N.compile(data,4),core=70.804,left=map.distanceMetric.mapBreaks.at(-1),metric=x=>N.metricDistance(map,x),length=metric(left)-metric(core);
const median=a=>{const b=a.filter(Number.isFinite).sort((x,y)=>x-y);return b.length?(b[(b.length-1)>>1]+b[b.length>>1])/2:null;};
const mean=a=>a.reduce((s,v)=>s+v,0)/a.length;
const inverse=d=>{let lo=core,hi=left;for(let i=0;i<35;i++){const m=(lo+hi)/2;if(metric(m)<metric(core)+d)lo=m;else hi=m;}return (lo+hi)/2;};
const yaw=v=>{const[x,y,z,w0]=v,w=Number.isFinite(w0)?w0:Math.sqrt(Math.max(0,1-x*x-y*y-z*z));return (Math.atan2(2*(w*z+x*y),1-2*(y*y+z*z))*180/Math.PI+360)%360;};
const files=require('../data/analysis/weinberg-combined-20260923/results.json').folds.map(r=>r.file).filter(f=>require('../data/analysis/stationary-magnetic-20260923/evaluation.json').routes.some(r=>r.file===f));
const right=map.distanceMetric.mapBreaks[0];
const aligned=require('../data/analysis/magnetic-map-4f-20260921/aligned-sessions.json');
const LENGTH=aligned.coordinate.lengthM;
function session(file){const bytes=fs.readFileSync(path.join(root,file)),rows=bytes.toString().trim().split(/\r?\n/).map(JSON.parse),s=rows[0],reverse=s.label.route_id.endsWith('_REVERSE'),isRight=s.label.route_id.includes('TO_RIGHT_STAIRS'),edge=isRight?right:left;return {file,sha256:crypto.createHash('sha256').update(bytes).digest('hex'),rows,device:s.device,platform:'android',isRight,reverse,start:reverse?edge:core,end:reverse?core:edge,sign:(reverse?-1:1)*(isRight?-1:1),endTime:rows.filter(r=>r.kind==='label').at(-1).wall_time_ms};}
function replay(s,templates,mode,extract=false){
 const fit=weinberg&&!extract?weinberg.folds.find(f=>f.file===s.file)?.constant.model:null;
 if(weinberg&&!extract&&!fit)throw new Error('Missing query-excluded Weinberg fold');
 const r=R.create(data,{...models,templates},refs,{floor:4,x:s.start,y:0,platform:'android',device:s.device,initialDirectionSign:s.sign,magneticZoneEnabled:false,bleEnabled:mode.includes('ble'),sequenceEnabled:mode.includes('v2')||mode.includes('hybrid'),magneticGridEnabled:mode.includes('grid')||mode.includes('hybrid'),magneticGrid:(mode.includes('grid')||mode.includes('hybrid'))?gridFor(s):null,sequenceFallbackEnabled:mode.includes('hybrid')});
 if(fit)r.weinbergModel={coefficient:fit.coefficients[0],baseMeters:weinberg.fixedStrideMeters};
 const explicit=s.rows.some(r=>r.sensor==='heading_degrees');let latest=null,sent=null,sentTime=-Infinity,pending=[],steps=[],history=[],bleEvents=[];
 for(const row of s.rows){const t=row.kind==='sample'&&Number.isFinite(row.sensor_wall_time_ms)?row.sensor_wall_time_ms:row.wall_time_ms;if(!Number.isFinite(t)||t>s.endTime)continue;
  if(row.sensor==='heading_degrees')R.heading(r,t,row.values[0],3);
  else if(row.sensor==='rotation_vector'&&!explicit)latest=Math.round(yaw(row.values));
  else if(row.sensor==='magnetic_field_ut'){R.magnetic(r,t,row.values);if(extract){const g=r.gravityVector&&Math.hypot(...r.gravityVector);pending.push({norm:Math.hypot(...row.values.slice(0,3)),mv:g>1&&t>=r.gravityVectorTime&&t-r.gravityVectorTime<=250?row.values.slice(0,3).reduce((a,v,i)=>a+v*r.gravityVector[i]/g,0):null});}}
  else if(row.kind==='ble_observation'){const before=R.snapshot(r,[]);if(R.ble(r,t,row)){const after=R.snapshot(r,[]);bleEvents.push({elapsedMs:t-s.rows[0].wall_time_ms,steps:after.steps,beforeM:metric(before.x)-metric(core),afterM:metric(after.x)-metric(core),candidates:r.engine.radioObservation?.candidates});}}
  else if(row.sensor==='accelerometer_mps2'&&R.acceleration(r,t,row.values)){if(extract){steps.push({t,norm:median(pending.map(p=>p.norm)),mv:median(pending.map(p=>p.mv))});pending=[];}history.push(metric(R.snapshot(r,[]).x)-metric(core));}
  if(!explicit&&latest!==null&&['rotation_vector','magnetic_field_ut','pressure_hpa','step_counter'].includes(row.sensor)&&(latest!==sent||t-sentTime>=750)){R.heading(r,t,latest,3);sent=latest;sentTime=t;}
 }
 const snap=R.snapshot(r,[]);return {steps,history,bleEvents,detectedSteps:snap.steps,endpointErrorM:Math.abs(metric(snap.x)-metric(s.end)),sequence:snap.sequenceStats,grid:snap.magneticGridStats,ble:snap.bleStats};
}

const sessions=files.map(session);
const alignedLeft=sessions.map(s=>{
 const e=replay(s,[],'pdr',true),n=e.steps.length;
 return {file:s.file,sha256:s.sha256,points:e.steps.map((p,i)=>({distance:(s.reverse?1-(i+1)/n:(i+1)/n)*length,norm:p.norm})).sort((a,b)=>a.distance-b.distance)};
});
function gridFor(query){
 const train=alignedLeft.filter(s=>s.sha256!==query?.sha256);
 const cells=[];
 for(let x=0;x<=length;x+=.5){
  const values=[];
  for(const s of train){
   const a=s.points.filter(p=>p.distance<=x&&Number.isFinite(p.norm)).at(-1),b=s.points.find(p=>p.distance>=x&&Number.isFinite(p.norm));
   if(a&&b)values.push(a.distance===b.distance?a.norm:a.norm+(b.norm-a.norm)*(x-a.distance)/(b.distance-a.distance));
  }
  const avg=values.length?mean(values):null;
  cells.push({x,mean:avg,variance:values.length>1?Math.max(4,values.reduce((a,v)=>a+(v-avg)**2,0)/(values.length-1)):null,sessions:values.length,samples:values.length});
 }
 return {version:'left-grid-20260923',coordinate:{corridor:'main_left',lengthM:length,gridStepM:.5,strideM:.6194213261100863},platforms:{android:{norm:cells}},sources:train.map(s=>({file:s.file,sha256:s.sha256})),alignment:'Surveyed endpoints plus detected-step interpolation; weak intermediate coordinates'};
}
const modes=['pdr','v2_ble','grid','grid_ble','hybrid_ble'];
const folds=sessions.map(s=>{
 const templates=models.templates.filter(t=>t.sourceSha256!==s.sha256&&path.basename(t.source||'')!==path.basename(s.file));
 const variants={};for(const mode of modes){const v=replay(s,templates,mode);delete v.steps;delete v.history;delete v.bleEvents;variants[mode]=v;}
 return {file:s.file,direction:s.reverse?'reverse':'forward',excludedSha256:s.sha256,trainingSources:gridFor(s).sources,variants};
});
const summary=Object.fromEntries(modes.map(mode=>[mode,{mae:mean(folds.map(f=>f.variants[mode].endpointErrorM)),worst:Math.max(...folds.map(f=>f.variants[mode].endpointErrorM)),gridApplied:folds.reduce((a,f)=>a+f.variants[mode].grid.applied,0)}]));
fs.mkdirSync(out,{recursive:true});fs.writeFileSync(path.join(out,'grid-4f-left.json'),JSON.stringify(gridFor(null),null,2));
fs.writeFileSync(path.join(out,'aligned-sessions.json'),JSON.stringify(alignedLeft,null,2));
fs.writeFileSync(path.join(out,'evaluation.json'),JSON.stringify({method:'5-session LOSO; query hash excluded; actual Runtime; no lap fed to tracker; endpoint error only',summary,folds},null,2));console.log(JSON.stringify(summary,null,2));
