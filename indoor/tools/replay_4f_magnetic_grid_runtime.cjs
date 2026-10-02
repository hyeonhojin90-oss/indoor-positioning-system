// Replay the *actual* particle runtime with each query walk withheld from its
// magnetic map. This is an experiment; it never changes Android defaults.
const fs=require('node:fs');
const path=require('node:path');
const Runtime=require('../web/src/positioning/runtime');
const Nav=require('../web/src/positioning/navigation');
const navigation=require('../web/data/navigation/areas-v1.json');
const allModels=require('../web/data/positioning/motion-models.json');
const productionBleReferences=require('../web/data/positioning/ble-references.json').references;
const aligned=require('../data/analysis/magnetic-map-4f-20260921/aligned-sessions.json');
const ROOT=path.resolve(__dirname,'../..');
const OUTPUT=path.join(ROOT,'indoor/data/analysis/magnetic-map-4f-runtime-ab-20260921');
const MAP=Nav.compile(navigation,4);
const LENGTH=aligned.coordinate.lengthM,RIGHT=MAP.distanceMetric.mapBreaks[0],CORE=70.804;
const sameDayBle=process.env.BLE_REFERENCE_SET==='same-day';
const mean=a=>a.length?a.reduce((x,y)=>x+y,0)/a.length:null;
const median=a=>{const b=[...a].sort((x,y)=>x-y);return b.length?(b[(b.length-1)>>1]+b[b.length>>1])/2:null;};
const percentile=(a,p)=>{if(!a.length)return null;const b=[...a].sort((x,y)=>x-y);return b[Math.ceil(p*b.length)-1];};
const distanceFromCore=x=>LENGTH-Nav.metricDistance(MAP,x);
const yaw=v=>{const [x,y,z,w0]=v,w=Number.isFinite(w0)?w0:Math.sqrt(Math.max(0,1-x*x-y*y-z*z));
  return (Math.atan2(2*(w*z+x*y),1-2*(y*y+z*z))*180/Math.PI+360)%360;};
function buildSameDayBleReferences(){
  const dir=path.join(ROOT,'indoor/data/raw/android/2026-09-19/kakao-pull-4f');
  const anchors=[['111618','stairs_right',RIGHT],['111707','main_right',19.8471],
    ['111758','core_junction',CORE],['112827','stairs_left',135.407],
    ['112915','main_left',111.13],['113013','core_junction',CORE]];
  return anchors.map(([time,zone,x])=>{
    const source=`indoor_positioning_20260919_${time}.jsonl`;
    const rows=fs.readFileSync(path.join(dir,source),'utf8').trim().split(/\r?\n/).map(JSON.parse);
    const groups=new Map();for(const row of rows)if(row.kind==='ble_observation'){
      if(!groups.has(row.anonymous_id))groups.set(row.anonymous_id,[]);
      groups.get(row.anonymous_id).push(row.rssi_dbm);
    }
    const ble=Object.fromEntries([...groups].filter(([,v])=>v.length>=3).map(([id,v])=>[id,median(v)]));
    return {floor:4,platform:'android',device:rows[0].device,zone,ble,source,
      anchor:{id:`same_day_${time}`,x,y:0,sigma_m:6,verified:false,sources:1}};
  });
}
const bleReferences=sameDayBle?buildSameDayBleReferences():productionBleReferences;
function gridFor(query){
  const training=aligned.sessions.filter(s=>s.file!==query.file&&s.platform===query.platform);
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
function replay(session){
  const file=path.join(ROOT,session.file),rows=fs.readFileSync(file,'utf8').trim().split(/\r?\n/).map(JSON.parse);
  const hasHeading=rows.some(r=>r.sensor==='heading_degrees'||r.sensor==='rotation_vector');
  if(!hasHeading)return {file:session.file,platform:session.platform,direction:session.direction,excluded:'no_heading_samples'};
  const finalLabel=rows.filter(r=>r.kind==='label').at(-1),endTime=finalLabel.wall_time_ms;
  const bleObservations=rows.filter(r=>r.kind==='ble_observation'&&r.wall_time_ms<=endTime).length;
  if(session.file.includes('kakao-pull-4f')&&bleObservations===0)
    throw new Error(`Latest 4F walk lost its BLE observations: ${session.file}`);
  const initial= session.direction==='forward'?CORE:RIGHT,sign=session.direction==='forward'?-1:1;
  const models={...allModels,templates:(allModels.templates||[]).filter(t=>t.source!==path.basename(file))};
  const common={floor:4,x:initial,y:0,platform:session.platform,device:rows[0].device||rows[0].device_model,
    initialDirectionSign:sign,magneticZoneEnabled:false,bleEnabled:session.platform==='android'};
  const baseline=Runtime.create(navigation,models,bleReferences,{...common,sequenceEnabled:true});
  const candidate=Runtime.create(navigation,models,bleReferences,{...common,sequenceEnabled:false,magneticGridEnabled:true,magneticGrid:gridFor(session)});
  const traces=[[],[]],runtimes=[baseline,candidate];
  for(const row of rows){
    const t=row.wall_time_ms;if(!Number.isFinite(t)||t>endTime)continue;
    for(let i=0;i<2;i++){
      const r=runtimes[i];
      if(row.sensor==='heading_degrees')Runtime.heading(r,t,row.values?.[0],row.accuracy);
      else if(row.sensor==='rotation_vector'&&session.platform==='android')Runtime.heading(r,t,yaw(row.values),3);
      else if(row.sensor==='magnetic_field_ut')Runtime.magnetic(r,t,row.values);
      else if(row.sensor==='pressure_hpa')Runtime.pressure(r,t,row.values?.[0]);
      else if(row.kind==='ble_observation')Runtime.ble(r,t,row);
      else if(row.sensor==='accelerometer_mps2'&&Runtime.acceleration(r,t,row.values)){
        const snap=Runtime.snapshot(r,[]);
        traces[i].push({time:t,estimateM:distanceFromCore(snap.x),zone:snap.zone});
      }
    }
  }
  const expectedEnd=session.direction==='forward'?LENGTH:0;
  const variants=traces.map((trace,i)=>{
    const errors=trace.map((step,j)=>Math.abs(step.estimateM-(session.direction==='forward'?(j+1)/trace.length*LENGTH:(1-(j+1)/trace.length)*LENGTH)));
    const snap=Runtime.snapshot(runtimes[i],[]);
    return {detectedSteps:trace.length,alignedSteps:session.detectedSteps,
      intermediateWeakMeanM:mean(errors),intermediateWeakP90M:percentile(errors,.9),
      endpointErrorM:Math.abs(distanceFromCore(snap.x)-expectedEnd),endpointEstimateM:distanceFromCore(snap.x),
      finalZone:snap.zone,sequence:snap.sequenceStats,grid:snap.magneticGridStats,ble:snap.bleStats};
  });
  return {file:session.file,platform:session.platform,direction:session.direction,
    bleObservations,
    baseline:variants[0],gridCandidate:variants[1]};
}
const sourceSessions=sameDayBle?aligned.sessions.filter(s=>s.file.includes('2026-09-19/kakao-pull-4f')):aligned.sessions;
const sessions=sourceSessions.map(replay),eligible=sessions.filter(s=>!s.excluded);
const summarize=ss=>({sessions:ss.length,bleObservations:ss.reduce((n,s)=>n+s.bleObservations,0),
  weakMeanM:mean(ss.map(s=>s.baseline.intermediateWeakMeanM)),
  gridWeakMeanM:mean(ss.map(s=>s.gridCandidate.intermediateWeakMeanM)),
  endpointMeanM:mean(ss.map(s=>s.baseline.endpointErrorM)),gridEndpointMeanM:mean(ss.map(s=>s.gridCandidate.endpointErrorM)),
  weakWins:ss.filter(s=>s.gridCandidate.intermediateWeakMeanM<s.baseline.intermediateWeakMeanM).length,
  endpointWins:ss.filter(s=>s.gridCandidate.endpointErrorM<s.baseline.endpointErrorM).length,
  gridApplications:ss.reduce((n,s)=>n+s.gridCandidate.grid.applied,0),
  baselineBleApplications:ss.reduce((n,s)=>n+s.baseline.ble.applied,0),
  gridBleApplications:ss.reduce((n,s)=>n+s.gridCandidate.ble.applied,0),
  baselineBleWindows:ss.reduce((n,s)=>n+s.baseline.ble.evaluated,0),
  sequenceApplications:ss.reduce((n,s)=>n+s.baseline.sequence.applied,0)});
const report={version:sameDayBle?'runtime-ab-20260921-same-day-ble-diagnostic':'runtime-ab-20260921-ble-corrected',
  method:'4F right-corridor raw sensor replay through IndoorRuntime/IndoorFusion; query excluded from grid and sequence templates; baseline mode4 8-step norm plus available BLE versus optional guarded norm grid plus the same BLE. No AP in these walks.',
  bleReferenceSet:sameDayBle?'2026-09-19 stationary sessions collected after queried walks; retrospective diagnostic only':'app production 2026-09-17 stationary references',
  truth:'Endpoints confirmed. All intermediate truth is detected-step-linear interpolation, not surveyed position.',
  exclusions:sessions.filter(s=>s.excluded),summary:{overall:summarize(eligible),android:summarize(eligible.filter(s=>s.platform==='android')),
    ios:summarize(eligible.filter(s=>s.platform==='ios'))},sessions:eligible};
fs.mkdirSync(OUTPUT,{recursive:true});fs.writeFileSync(path.join(OUTPUT,sameDayBle?'diagnostic-same-day.json':'results.json'),JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify({summary:report.summary,exclusions:report.exclusions.length,
  sessions:eligible.map(s=>({name:path.basename(s.file),platform:s.platform,direction:s.direction,
    steps:s.baseline.detectedSteps,aligned:s.baseline.alignedSteps,baseline:s.baseline.intermediateWeakMeanM,
    grid:s.gridCandidate.intermediateWeakMeanM,gridApplied:s.gridCandidate.grid.applied}))},null,2));
