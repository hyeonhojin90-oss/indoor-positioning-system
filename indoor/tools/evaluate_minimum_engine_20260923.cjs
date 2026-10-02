const fs=require('fs'),path=require('path'),crypto=require('crypto');
const N=require('../web/src/positioning/navigation'),R=require('../web/src/positioning/runtime');
const weinberg=null;
const data=require('../web/data/navigation/areas-v1.json'),models=require('../web/data/positioning/motion-models.json');
const refs=require('../web/data/positioning/ble-references.json').references;
const root=path.resolve(__dirname,'../..'),out=path.join(root,'indoor/data/analysis/minimum-engine-20260923');
const map=N.compile(data,4),core=70.804,left=map.distanceMetric.mapBreaks.at(-1),metric=x=>N.metricDistance(map,x),length=metric(left)-metric(core);
const median=a=>{const b=a.filter(Number.isFinite).sort((x,y)=>x-y);return b.length?(b[(b.length-1)>>1]+b[b.length>>1])/2:null;};
const mean=a=>a.reduce((s,v)=>s+v,0)/a.length;
const inverse=d=>{let lo=core,hi=left;for(let i=0;i<35;i++){const m=(lo+hi)/2;if(metric(m)<metric(core)+d)lo=m;else hi=m;}return (lo+hi)/2;};
const yaw=v=>{const[x,y,z,w0]=v,w=Number.isFinite(w0)?w0:Math.sqrt(Math.max(0,1-x*x-y*y-z*z));return (Math.atan2(2*(w*z+x*y),1-2*(y*y+z*z))*180/Math.PI+360)%360;};
const files=require('../data/analysis/weinberg-combined-20260923/results.json').folds.map(r=>r.file);
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
function gridFor(query){
  const training=aligned.sessions.filter(s=>s.platform===query.platform&&crypto.createHash('sha256').update(fs.readFileSync(path.join(root,s.file))).digest('hex')!==query.sha256);
  const norm=[];
  for(let i=0;i<=Math.floor(LENGTH/.5);i++){
    const x=i*.5,values=[],sources=new Set();
    for(const session of training)for(const point of session.points)
      if(Math.abs(point.distanceMFromCore-x)<=.375&&Number.isFinite(point.magneticMagnitudeUt)){
        values.push(point.magneticMagnitudeUt);sources.add(session.file);
      }
    const average=mean(values),variance=values.length>1?values.reduce((s,v)=>s+(v-average)**2,0)/(values.length-1):0;
    norm.push({x,mean:average,variance,samples:values.length,sessions:sources.size});
  }
  for(let i=1;i<norm.length-1;i++)if(norm[i].mean===null&&norm[i-1].mean!==null&&norm[i+1].mean!==null){
    norm[i].mean=(norm[i-1].mean+norm[i+1].mean)/2;
    norm[i].variance=Math.max(4,norm[i-1].variance,norm[i+1].variance);
    norm[i].sessions=Math.min(norm[i-1].sessions,norm[i+1].sessions);
  }
  return {coordinate:{lengthM:LENGTH,gridStepM:.5},platforms:{[query.platform]:{norm}}};
}

const modes=['pdr','ble','v2','v2_ble','grid','grid_ble','hybrid','hybrid_ble'];
const folds=files.map(file=>{
 const s=session(file);
 const heldout=models.templates.filter(t=>t.sourceSha256!==s.sha256&&path.basename(t.source||'')!==path.basename(file));
 const variants={};
 for(const mode of modes){
  if(!s.isRight&&(mode.includes('grid')||mode.includes('hybrid')))continue;
  const started=performance.now(),result=replay(s,heldout,mode);
  delete result.steps;delete result.history;delete result.bleEvents;
  variants[mode]={...result,replayMs:performance.now()-started};
 }
 console.log(path.basename(file));
 return {file,sha256:s.sha256,corridor:s.isRight?'right':'left',direction:s.reverse?'reverse':'forward',variants};
});
const summarize=rows=>Object.fromEntries(modes.map(mode=>{
 const eligible=rows.filter(f=>f.variants[mode]),v=eligible.map(f=>f.variants[mode]);
 return [mode,{n:v.length,endpointMAE:v.length?mean(v.map(x=>x.endpointErrorM)):null,worst:v.length?Math.max(...v.map(x=>x.endpointErrorM)):null,
 over3m:v.filter(x=>x.endpointErrorM>3).length,over5m:v.filter(x=>x.endpointErrorM>5).length,
 winsOverPdr:eligible.filter(f=>f.variants[mode].endpointErrorM<f.variants.pdr.endpointErrorM-.1).length,
 harmsOverPdr:eligible.filter(f=>f.variants[mode].endpointErrorM>f.variants.pdr.endpointErrorM+.1).length,
 magneticApplications:v.reduce((a,x)=>a+x.sequence.applied+x.grid.applied,0),bleApplications:v.reduce((a,x)=>a+x.ble.applied,0)}];
}));
const result={method:'Actual sensor Runtime, fixed stride, production BLE refs, query excluded from V2 by source basename/hash and grid by content hash. Sensor timestamps and heading bridge follow existing left replay. No laps fed to engine.',
 limitations:['Endpoint physical distance only; no independent intermediate trajectory truth','Same user/device; retrospective model selection, not a new held-out final test','Right grid supported only; left compares PDR, BLE, V2, V2+BLE','AP absent from movement logs; no AP ranking','Replay wall time is desktop timing, not phone energy'],
 summary:{left:summarize(folds.filter(f=>f.corridor==='left')),right:summarize(folds.filter(f=>f.corridor==='right'))},folds};
fs.mkdirSync(out,{recursive:true});fs.writeFileSync(path.join(out,'evaluation.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result.summary,null,2));
