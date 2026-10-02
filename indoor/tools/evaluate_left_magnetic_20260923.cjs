// Latest left-corridor LOSO, production Runtime and detector, no lap input during replay.
const fs=require('fs'),path=require('path'),crypto=require('crypto');
const N=require('../web/src/positioning/navigation');
const ablation=process.argv.includes('--no-ble-proposal')?'no-ble-proposal':process.argv.includes('--no-ble-weight')?'no-ble-weight':null;
const weinberg=process.argv.includes('--weinberg')?require('../data/analysis/weinberg-combined-20260923/results.json'):null;
let R=require('../web/src/positioning/runtime');
if(ablation){
 const Module=require('module'),engineFile=require.resolve('../web/src/positioning/fusion-engine'),runtimeFile=require.resolve('../web/src/positioning/runtime');
 const engine=new Module(engineFile,module);engine.filename=engineFile;engine.paths=module.paths;
 let source=fs.readFileSync(engineFile,'utf8');
 if(ablation==='no-ble-proposal')throw new Error('BLE proposals have been removed from production; use normal replay. Archived pre-fix ablations are retained.');
 else {const target='p.weight*=Math.pow(.2+.8*likelihood,.35*(observation.quality??1));';if(!source.includes(target))throw new Error('BLE weighting target not found');source=source.replace(target,'p.weight*=1;');}
 engine._compile(source,engineFile);
 const runtime=new Module(runtimeFile,module);runtime.filename=runtimeFile;runtime.paths=module.paths;
 const req=Module.createRequire(runtimeFile);runtime.require=id=>id==='./fusion-engine'?engine.exports:req(id);runtime._compile(fs.readFileSync(runtimeFile,'utf8'),runtimeFile);R=runtime.exports;
}
const data=require('../web/data/navigation/areas-v1.json'),models=require('../web/data/positioning/motion-models.json');
const refs=require('../web/data/positioning/ble-references.json').references;
const root=path.resolve(__dirname,'../..'),out=path.join(root,'indoor/data/analysis/left-magnetic-20260923'+(process.argv.includes('--radio-fix')?'-radio-fix':'')+(ablation?'-'+ablation:'')+(weinberg?'-weinberg':''));
const map=N.compile(data,4),core=70.804,left=map.distanceMetric.mapBreaks.at(-1),metric=x=>N.metricDistance(map,x),length=metric(left)-metric(core);
const median=a=>{const b=a.filter(Number.isFinite).sort((x,y)=>x-y);return b.length?(b[(b.length-1)>>1]+b[b.length>>1])/2:null;};
const mean=a=>a.reduce((s,v)=>s+v,0)/a.length;
const inverse=d=>{let lo=core,hi=left;for(let i=0;i<35;i++){const m=(lo+hi)/2;if(metric(m)<metric(core)+d)lo=m;else hi=m;}return (lo+hi)/2;};
const yaw=v=>{const[x,y,z,w0]=v,w=Number.isFinite(w0)?w0:Math.sqrt(Math.max(0,1-x*x-y*y-z*z));return (Math.atan2(2*(w*z+x*y),1-2*(y*y+z*z))*180/Math.PI+360)%360;};
const files=require('../data/analysis/stationary-magnetic-20260923/evaluation.json').routes.map(r=>r.file);
function session(file){const bytes=fs.readFileSync(path.join(root,file)),rows=bytes.toString().trim().split(/\r?\n/).map(JSON.parse),s=rows[0],reverse=s.label.route_id.endsWith('_REVERSE');return {file,sha256:crypto.createHash('sha256').update(bytes).digest('hex'),rows,device:s.device,reverse,start:reverse?left:core,end:reverse?core:left,sign:reverse?-1:1,endTime:rows.filter(r=>r.kind==='label').at(-1).wall_time_ms};}
function replay(s,templates,mode,extract=false){
 const fit=weinberg&&!extract?weinberg.folds.find(f=>f.file===s.file)?.constant.model:null;
 if(weinberg&&!extract&&!fit)throw new Error('Missing query-excluded Weinberg fold');
 const r=R.create(data,{...models,templates},refs,{floor:4,x:s.start,y:0,platform:'android',device:s.device,initialDirectionSign:s.sign,magneticZoneEnabled:false,bleEnabled:mode!=='pdr',sequenceEnabled:['norm','mv'].includes(mode),verticalSequenceEnabled:mode==='mv'});
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
 const snap=R.snapshot(r,[]);return {steps,history,bleEvents,detectedSteps:snap.steps,endpointErrorM:Math.abs(metric(snap.x)-metric(s.end)),sequence:snap.sequenceStats,ble:snap.bleStats};
}
const sessions=files.map(session);
const templates=[];
for(const s of sessions){const e=replay(s,[],'pdr',true);s.steps=e.steps;s.templates=[];
 for(let end=7;end<e.steps.length;end+=2){const w=e.steps.slice(end-7,end+1);if(w.every(p=>Number.isFinite(p.norm)&&Number.isFinite(p.mv))){const progress=(end+1)/e.steps.length;const item={source:s.file,sourceSha256:s.sha256,platform:'android',device:s.device,floor:4,corridor:'main_left',direction:s.reverse?'right':'left',values:w.map(p=>p.norm),verticalValues:w.map(p=>p.mv),x:inverse((s.reverse?1-progress:progress)*length),y:0,weakLabel:true,alignment:'surveyed_endpoints_detected_step_progress'};templates.push(item);s.templates.push(item);}}
}
const folds=sessions.map(s=>{const train=templates.filter(t=>t.sourceSha256!==s.sha256);const variants={};
 for(const mode of ['pdr','ble','norm','mv']){const r=replay(s,train,mode);const target=r.history.map((_,i)=>length*(s.reverse?1-(i+1)/r.history.length:(i+1)/r.history.length));variants[mode]={...r,steps:undefined,history:undefined,weakIntermediateMAE:mean(r.history.map((x,i)=>Math.abs(x-target[i])))};}
 return {file:s.file,sha256:s.sha256,direction:s.reverse?'reverse':'forward',trainingSources:[...new Set(train.map(t=>t.source))],...{variants}};
});
const summary=Object.fromEntries(['pdr','ble','norm','mv'].map(k=>[k,{endpointMAE:mean(folds.map(f=>f.variants[k].endpointErrorM)),worstEndpoint:Math.max(...folds.map(f=>f.variants[k].endpointErrorM)),weakIntermediateMAE:mean(folds.map(f=>f.variants[k].weakIntermediateMAE)),sequenceApplied:folds.reduce((a,f)=>a+f.variants[k].sequence.applied,0),bleApplied:folds.reduce((a,f)=>a+f.variants[k].ble.applied,0)}]));
fs.mkdirSync(out,{recursive:true});
fs.writeFileSync(path.join(out,'candidate-model.json'),JSON.stringify({version:'left-survey-aligned-20260923',runtimeDefault:false,templates,limitations:['Training intermediate position is weak endpoint/step interpolation','Same day/device/person','All five training sessions: deployment candidate only, NOT evaluation model']},null,2)+'\n');
fs.writeFileSync(path.join(out,'evaluation.json'),JSON.stringify({lengthM:length,method:'Full runtime LOSO, same raw sensor stream, query hash excluded from templates, BLE refs from separate stationary sessions; no query laps used by engine',limitations:['Endpoint uses survey and user start/end labels, not independently tracked trajectory','Intermediate errors are weak step-interpolated truth and cannot certify meter accuracy','No AP observations; does not evaluate AP fusion','This compares V2 pattern features, not a left-grid HMM'],summary,folds},null,2)+'\n');
console.log(JSON.stringify({lengthM:length,templates:templates.length,summary,folds:folds.map(f=>({file:path.basename(f.file),variants:Object.fromEntries(Object.entries(f.variants).map(([k,v])=>[k,{error:v.endpointErrorM,applied:v.sequence.applied,ble:v.ble.applied}]))}))},null,2));
if(process.argv.includes('--publish')){
 if(ablation||weinberg)throw new Error('Do not publish an ablation');
 const target=path.join(root,'indoor/web/data/positioning/motion-models.json');
 const backup=path.join(out,'motion-models-before.json');if(!fs.existsSync(backup))fs.copyFileSync(target,backup);
 const updated={...models,templates:[...models.templates.filter(t=>!(t.platform==='android'&&t.floor===4&&(t.corridor==='main_left'||t.x>core))),...templates],
  leftCorridorUpdate:{version:'20260923',sources:sessions.map(s=>({file:s.file,sha256:s.sha256})),verticalRuntimeDefault:false,validation:'LOSO 5 sessions, magnitude marginally improves BLE arm; combined engine still worse than no-radio arm; experimental'}};
 fs.writeFileSync(target,JSON.stringify(updated,null,2)+'\n');
 console.log('Published left magnitude templates; mv remains opt-in. Backup: '+backup);
}
