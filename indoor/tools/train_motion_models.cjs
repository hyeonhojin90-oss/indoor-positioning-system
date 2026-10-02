const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const root=path.resolve(__dirname,'../..'),data=path.join(root,'indoor/data');
if(fs.existsSync(path.join(root,'indoor/web/data/positioning/motion-models.json'))&&
 JSON.parse(fs.readFileSync(path.join(root,'indoor/web/data/positioning/motion-models.json'),'utf8')).leftCorridorUpdate){
 throw new Error('Legacy manifest trainer cannot overwrite the surveyed left-corridor update. Use evaluate_left_magnetic_20260923.cjs --publish for that data; migrate legacy training before rebuilding all floors.');
}
const Cal=require('../web/src/positioning/calibration'),Seq=require('../web/src/positioning/sequence');
const {createPositionTracker,updatePositionAcceleration}=require('../../app/expo-sensor-collector/positionTracking');
const {FLOOR_MAPS}=require('../../app/expo-sensor-collector/routes');
const median=xs=>xs.length?[...xs].sort((a,b)=>a-b)[Math.floor(xs.length/2)]:null;
const sessions=[],skipped=[],templates=[],training=[],smoothed=[];
for(const name of ['manifest.json','ios_manifest.json']){
  const manifest=JSON.parse(fs.readFileSync(path.join(data,name),'utf8'));
  for(const item of manifest.sessions){
    if(item.include_in_analysis===false||!item.status.startsWith('accepted')){skipped.push({file:item.file,reason:'manifest_excluded'});continue;}
    if(!/^([2-9]|10)F_CORE_TO_(LEFT|RIGHT)_STAIRS$/.test(item.route_id)){skipped.push({file:item.file,reason:'no_verified_one_dimensional_route'});continue;}
    const bytes=fs.readFileSync(path.join(data,manifest.raw_directory,item.file)),sha=crypto.createHash('sha256').update(bytes).digest('hex');
    if(item.sha256&&item.sha256!==sha)throw Error(`Hash mismatch ${item.file}`);
    const records=bytes.toString('utf8').trim().split(/\r?\n/).map(JSON.parse),start=records[0],platform=start.platform||'android';
    const floor=Number(start.label.floor),direction=item.route_id.includes('RIGHT')?'right':'left',sign=direction==='right'?-1:1;
    const map=FLOOR_MAPS.find(m=>Number(m.floor)===floor),t0=start.wall_time_ms;
    const anchors=[{time:0,x:70.804,floor,label:'CORE'}];
    for(const r of records.filter(r=>r.kind==='label')){
      const label=r.label?.location||'',room=map.rooms.find(x=>label===x.id||label.startsWith(x.id+' '));
      const x=label.includes('오른쪽 계단')?0:label.includes('왼쪽 계단')?135.407:room?.front_x??room?.x;
      if(Number.isFinite(x))anchors.push({time:r.wall_time_ms-t0,x,floor,label});
    }
    if(anchors.length<4||anchors.some((a,i)=>i&&sign*(a.x-anchors[i-1].x)<-.01)){skipped.push({file:item.file,reason:'ambiguous_or_nonmonotonic_laps'});continue;}
    let tracker=createPositionTracker({floor,x:70.804,initialDirectionSign:sign}),lastAcc=-Infinity,mag=[];
    const steps=[];
    for(const r of records){const t=r.wall_time_ms-t0;
      if(r.sensor==='magnetic_field_ut')mag.push({time:t,value:Math.hypot(...r.values.slice(0,3))});
      if(r.sensor!=='accelerometer_mps2'||t-lastAcc<40)continue;lastAcc=t;
      const result=updatePositionAcceleration(tracker,t,r.values);tracker=result.state;
      if(result.detected)steps.push({time:t,progress:steps.length+1,peak:result.peak});
    }
    for(let i=1;i<anchors.length;i++){
      const a=anchors[i-1],b=anchors[i],part=steps.filter(s=>s.time>a.time&&s.time<=b.time),distance=Math.abs(b.x-a.x);
      if(part.length>=3&&b.time-a.time>1000&&distance>1){const stride=distance/part.length;
        if(stride>=.3&&stride<=1.6)training.push({source:item.file,platform,floor,cadence:part.length*1000/(b.time-a.time),peak:median(part.map(s=>s.peak)),stride,distance,steps:part.length});}
    }
    // Bracket each label with cumulative progress interpolated in time.
    function progressAt(t){let before={time:0,progress:0};for(const p of steps){if(p.time>=t)return before.progress+(p.progress-before.progress)*(t-before.time)/Math.max(1,p.time-before.time);before=p;}return before.progress;}
    const points=[...steps,...anchors.map(a=>({time:a.time,progress:progressAt(a.time)}))].sort((a,b)=>a.time-b.time);
    const result=Cal.smooth(points,anchors);smoothed.push({file:item.file,sha256:sha,anchors,...result});
    const getX=t=>{const p=result.points.find(p=>p.time===t);return p?.smoothedX;};
    let previous=0;
    const magneticSteps=steps.map(s=>{const v=median(mag.filter(m=>m.time>previous&&m.time<=s.time).map(m=>m.value));previous=s.time;return {...s,value:v,x:getX(s.time)};});
    for(let i=7;i<magneticSteps.length;i+=2){const window=magneticSteps.slice(i-7,i+1);if(window.every(p=>Number.isFinite(p.value)&&Number.isFinite(p.x))){templates.push({
      source:item.file,platform,floor,direction,device:start.device||start.device_model||null,
      values:window.map(p=>p.value),x:window.at(-1).x,y:0,weakLabel:true});}}
    sessions.push({file:item.file,sha256:sha,platform,floor,direction,steps:steps.length,lapCount:anchors.length-1});
  }
}
const strideModels={},strideValidation={};
for(const platform of ['ios','android']){
  const rows=training.filter(r=>r.platform===platform),sources=[...new Set(rows.map(r=>r.source))],folds=[];
  for(const source of sources){const train=rows.filter(r=>r.source!==source),test=rows.filter(r=>r.source===source),model=Cal.fit(train);
    const base=70.804/81;
    if(model&&test.length)folds.push({source,n:test.length,baselineMAE:test.reduce((s,r)=>s+Math.abs(base-r.stride),0)/test.length,
      modelMAE:test.reduce((s,r)=>s+Math.abs(Cal.predict(model,r,base)-r.stride),0)/test.length});}
  strideValidation[platform]={folds,reason:'map_lap_targets_not_surveyed_stride; segment_cadence_includes_stops'};
  strideModels[platform]=Cal.fit(rows);
}
const sequenceValidation=[];
for(const s of sessions){const query=templates.filter(t=>t.source===s.file),refs=templates.filter(t=>t.source!==s.file),errors=[];let accepted=0;
  for(const q of query){const match=Seq.match(q.values,refs,{platform:q.platform,floor:q.floor,direction:q.direction,device:q.device});
    if(match.reason==='sequence_candidate'){accepted++;errors.push(Math.abs(match.candidates[0].x-q.x));}}
  sequenceValidation.push({source:s.file,windows:query.length,accepted,medianMapError:median(errors),reason:'weak_lap_interpolated_targets'});
}
const directory=path.join(data,'analysis/motion-v2');fs.mkdirSync(directory,{recursive:true});
const report={version:2,sessions,skipped,strideValidation,sequenceValidation,limits:['No surveyed distances','Holdout is per session, not independent day/user','Android/iOS separate','Special routes excluded from 1D postprocessing']};
fs.writeFileSync(path.join(directory,'evaluation.json'),JSON.stringify(report,null,2)+'\n');
fs.writeFileSync(path.join(directory,'lap-smoothed.json'),JSON.stringify(smoothed,null,2)+'\n');
const modelDir=path.join(root,'indoor/web/data/positioning');fs.mkdirSync(modelDir,{recursive:true});
fs.writeFileSync(path.join(modelDir,'motion-models.json'),JSON.stringify({version:2,templates,strideModels,limits:report.limits},null,2)+'\n');
const legacy=require('../../app/expo-sensor-collector/referenceFingerprints.json');
const zones=require('../web/src/positioning/zone-classifier').fromLegacy(legacy);
fs.writeFileSync(path.join(modelDir,'zone-references.json'),JSON.stringify({version:1,references:zones},null,2)+'\n');
console.log(JSON.stringify({sessions:sessions.length,templates:templates.length,trainingRows:training.length,strideValidation,sequenceValidation},null,2));
