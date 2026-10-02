// Separate 4F right-corridor progress error from heading/particle rejection,
// and measure BLE identifier persistence across independently collected dates.
const fs=require('node:fs');
const path=require('node:path');
const crypto=require('node:crypto');
const Pdr=require('../../app/expo-sensor-collector/positionTracking');
const Runtime=require('../web/src/positioning/runtime');
const Nav=require('../web/src/positioning/navigation');
const navigation=require('../web/data/navigation/areas-v1.json');
const models=require('../web/data/positioning/motion-models.json');
const oldReferences=require('../web/data/positioning/ble-references.json').references.filter(r=>r.floor===4);
const ROOT=path.resolve(__dirname,'../..');
const OUTPUT=path.join(ROOT,'indoor/data/analysis/magnetic-map-4f-runtime-ab-20260921/progress-ble-audit.json');
const RAW='indoor/data/raw/android/2026-09-19/kakao-pull-4f';
const map=Nav.compile(navigation,4),coreX=70.804,rightX=map.distanceMetric.mapBreaks[0];
const corridorM=Nav.metricDistance(map,coreX)-Nav.metricDistance(map,rightX);
const strideM=corridorM/map.distanceMetric.calibrationSteps;
const oldIdUnion=new Set(oldReferences.flatMap(ref=>Object.keys(ref.ble||{})));
const read=relative=>fs.readFileSync(path.join(ROOT,relative),'utf8').trim().split(/\r?\n/).map(JSON.parse);
const sha=relative=>crypto.createHash('sha256').update(fs.readFileSync(path.join(ROOT,relative))).digest('hex');
const file=n=>`${RAW}/indoor_positioning_20260919_${n}.jsonl`;
const yaw=v=>{const [x,y,z,w0]=v,w=Number.isFinite(w0)?w0:Math.sqrt(Math.max(0,1-x*x-y*y-z*z));
  return (Math.atan2(2*(w*z+x*y),1-2*(y*y+z*z))*180/Math.PI+360)%360;};
const ids=(rows,minimum=1)=>{const counts=new Map();for(const r of rows)if(r.kind==='ble_observation')
  counts.set(r.anonymous_id,(counts.get(r.anonymous_id)||0)+1);
  return new Set([...counts].filter(([,count])=>count>=minimum).map(([id])=>id));};
const stationary={right:read(file('111618')),coreA:read(file('111758')),
  coreB:read(file('113013')),left:read(file('112827'))};
const anchorPairs=[['core_junction',[stationary.coreA,stationary.coreB]],
  ['stairs_right',[stationary.right]],['stairs_left',[stationary.left]]];
const anchorPersistence=anchorPairs.map(([zone,sessions])=>{
  const reference=oldReferences.find(r=>r.zone===zone),old=new Set(Object.keys(reference.ble));
  const recent=new Set(sessions.flatMap(rows=>[...ids(rows,3)]));
  const shared=[...recent].filter(id=>old.has(id));
  return {zone,oldReferenceIds:old.size,recentStationaryIds:recent.size,crossDateIds:shared.length,
    uniqueToOldAnchor:shared.filter(id=>oldReferences.filter(r=>Object.hasOwn(r.ble,id)).length===1).length};
});
const pairedStableIds=new Set(anchorPairs.flatMap(([zone,sessions])=>{
  const old=new Set(Object.keys(oldReferences.find(r=>r.zone===zone).ble));
  return [...new Set(sessions.flatMap(rows=>[...ids(rows,3)]))].filter(id=>old.has(id));
}));
function bleWindows(rows,end){
  const observations=rows.filter(r=>r.kind==='ble_observation'&&r.wall_time_ms<=end);
  let buffer=[],last=-Infinity;const overlaps=[];
  for(const row of observations){const time=row.wall_time_ms;buffer.push(row);
    buffer=buffer.filter(r=>time-r.wall_time_ms<=5000);
    if(time-last<3000)continue;last=time;
    const counts=new Map();for(const r of buffer)counts.set(r.anonymous_id,(counts.get(r.anonymous_id)||0)+1);
    const eligible=new Set([...counts].filter(([,n])=>n>=2).map(([id])=>id));
    overlaps.push(Math.max(...oldReferences.map(ref=>Object.keys(ref.ble).filter(id=>eligible.has(id)).length)));
  }
  return {observations:observations.length,evaluated:overlaps.length,
    eligibleAtFive:overlaps.filter(n=>n>=5).length,eligibleAtThree:overlaps.filter(n=>n>=3).length,
    maxCommonPerWindow:overlaps};
}
function auditWalk(name,reverse){
  const relative=file(name),rows=read(relative),lastLabel=rows.filter(r=>r.kind==='label').at(-1);
  const endpointTime=lastLabel.wall_time_ms,initialX=reverse?rightX:coreX;
  let tracker=Pdr.createPositionTracker({floor:4,x:initialX,initialDirectionSign:reverse?1:-1});
  const rt=Runtime.create(navigation,models,[],{floor:4,x:initialX,platform:'android',device:rows[0].device,
    initialDirectionSign:reverse?1:-1,magneticZoneEnabled:false,bleEnabled:false,sequenceEnabled:false});
  let detected=0,hardware=rows[0].start_step_counter;const labels=[],reasons={};
  for(const row of rows){const t=row.wall_time_ms;if(!Number.isFinite(t)||t>endpointTime)continue;
    if(row.sensor==='step_counter')hardware=row.values[0];
    else if(row.sensor==='rotation_vector')Runtime.heading(rt,t,yaw(row.values),3);
    else if(row.sensor==='magnetic_field_ut')Runtime.magnetic(rt,t,row.values);
    else if(row.sensor==='accelerometer_mps2'){
      const update=Pdr.updatePositionAcceleration(tracker,t,row.values);tracker=update.state;
      if(update.detected)detected++;
      if(Runtime.acceleration(rt,t,row.values)){
        const reason=Runtime.snapshot(rt,[]).reason;reasons[reason]=(reasons[reason]||0)+1;
      }
    }
    if(row.kind==='label')labels.push({location:row.label.location,elapsedS:(t-rows[0].wall_time_ms)/1000,
      accelerometerSteps:detected,hardwareSteps:hardware-rows[0].start_step_counter});
  }
  const estimated=Runtime.snapshot(rt,[]),estimatedM=Nav.metricDistance(map,estimated.x);
  const expectedM=reverse?Nav.metricDistance(map,coreX):Nav.metricDistance(map,rightX);
  const completeIds=ids(rows.filter(r=>r.wall_time_ms<=endpointTime));
  return {file:relative,sha256:sha(relative),direction:reverse?'right_to_core':'core_to_right',
    corridorM,fixedStrideM:strideM,calibrationSteps:map.distanceMetric.calibrationSteps,
    accelerometerSteps:detected,hardwareStepsAtLastLabel:hardware-rows[0].start_step_counter,
    fixedStrideTravelM:detected*strideM,fixedStrideProgressErrorM:detected*strideM-corridorM,
    fusionEndpointErrorM:Math.abs(estimatedM-expectedM),fusionFinalZone:estimated.zone,
    fusionStepReasons:reasons,firstLabel:labels[0],lastLabel:labels.at(-1),labels,
    ble:{...bleWindows(rows,endpointTime),uniqueIds:completeIds.size,
      currentReferenceIdsSeen:[...completeIds].filter(id=>oldIdUnion.has(id)).length,
      crossDatePairedAnchorIdsSeen:[...completeIds].filter(id=>pairedStableIds.has(id)).length}};
}
const result={version:1,coordinate:'surveyed 4F core center <-> right stair entrance before stairs',
  interpretation:'Hardware step counter is independent corroboration, not manually counted ground truth. Mid-route room labels are approximate.',
  oldReferenceDate:'2026-09-17',newStationaryDate:'2026-09-19',
  oldReferenceIds:oldIdUnion.size,anchorPersistence,pairedStableIdPool:pairedStableIds.size,
  walks:[auditWalk('111300',true),auditWalk('111532',false)]};
fs.writeFileSync(OUTPUT,JSON.stringify(result,null,2)+'\n');
console.log(JSON.stringify({anchorPersistence,walks:result.walks.map(w=>({file:path.basename(w.file),
  accelerometerSteps:w.accelerometerSteps,hardwareStepsAtLastLabel:w.hardwareStepsAtLastLabel,
  fixedStrideProgressErrorM:w.fixedStrideProgressErrorM,fusionEndpointErrorM:w.fusionEndpointErrorM,
  firstLabel:w.firstLabel,ble:w.ble}))},null,2));
