const fs=require('node:fs'),Nav=require('../web/src/positioning/navigation'),Runtime=require('../web/src/positioning/runtime');
const file='indoor/web/data/navigation/areas-v1.json',data=JSON.parse(fs.readFileSync(file,'utf8'));
const files=require('../data/analysis/weinberg-combined-20260923/results.json').folds.map(f=>f.file);
const values=new Map(),map=Nav.compile(data,4),core=Nav.metricDistance(map,70.804);
const diagnostics=[];
for(const file of files){
  const rows=fs.readFileSync(file,'utf8').trim().split(/\r?\n/).map(JSON.parse),route=rows[0].label.route_id;
  const reverse=/_REVERSE$/.test(route),right=route.includes('TO_RIGHT_STAIRS');
  const edge=right?map.distanceMetric.meterBreaks[0]:map.distanceMetric.meterBreaks.at(-1);
  const start=reverse?edge:core,end=reverse?core:edge;
  const labels=rows.filter(r=>r.kind==='label'),endTime=labels.at(-1)?.wall_time_ms;
  // Android's batched step_counter can remain at zero across several laps.
  // Re-detect steps from IMU samples; never turn those cached counts into room
  // positions. Endpoint alignment still assumes an average stride, not truth.
  const runtime=Runtime.create(data,{},[],{floor:4,x:70.804,y:0,count:1,magneticZoneEnabled:false,sequenceEnabled:false});
  const stepTimes=[];
  for(const row of rows){
    const time=Number.isFinite(row.sensor_wall_time_ms)?row.sensor_wall_time_ms:row.wall_time_ms;
    if(row.sensor==='accelerometer_mps2'&&time<=endTime&&Runtime.acceleration(runtime,time,row.values))stepTimes.push(time);
  }
  const endSteps=stepTimes.length;if(!(endSteps>0))continue;
  diagnostics.push({file,rawCounterEnd:labels.at(-1).steps_since_start,redetectedSteps:endSteps});
  for(const label of labels){
    const id=label.label.location?.match(/\b4\d{3}\b/)?.[0];if(!id)continue;
    // These are session-end aligned step fractions, not measured door positions.
    const lapSteps=stepTimes.filter(time=>time<=label.wall_time_ms).length;
    const xM=start+(end-start)*lapSteps/endSteps;
    if(!values.has(id))values.set(id,[]);values.get(id).push({xM,file});
  }
}
const median=a=>[...a].sort((a,b)=>a-b)[a.length>>1];
data.observedLandmarks={'4':[...values].filter(([,v])=>v.length>=2).map(([id,v])=>({id,label:`${id} 앞`,xM:median(v.map(p=>p.xM)),
  sources:v.length,spreadM:Math.max(...v.map(p=>p.xM))-Math.min(...v.map(p=>p.xM)),
  evidence:'endpoint_aligned_redetected_imu_step_fraction_not_surveyed_door',sourceFiles:v.map(p=>p.file)}))};
fs.writeFileSync(file,JSON.stringify(data,null,2)+'\n');
fs.mkdirSync('indoor/data/analysis/meters-20261002',{recursive:true});
fs.writeFileSync('indoor/data/analysis/meters-20261002/landmark-alignment.json',JSON.stringify({diagnostics,landmarks:data.observedLandmarks['4'],limitations:'Display candidates only. End-aligned average-stride fractions are not independent door surveys or correction ground truth.'},null,2));
console.log('Observed 4F landmarks:',data.observedLandmarks['4'].length);
