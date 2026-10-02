// Replays raw 4F right-corridor records against the confirmed 2026-09-14 distance metric.
// Endpoint only: classroom fronts have no surveyed physical coordinate yet.
const fs=require('fs'),path=require('path');
const root=path.resolve(__dirname,'../..');
const Runtime=require('../web/src/positioning/runtime');
const Nav=require('../web/src/positioning/navigation');
const Zones=require('../web/src/positioning/zone-classifier');
const {createPositionTracker,updatePositionAcceleration}=require('../../app/expo-sensor-collector/positionTracking');
const maps=require('../web/data/navigation/areas-v1.json');
const models=require('../web/data/positioning/motion-models.json');
const references=Zones.fromLegacy(require('../../app/expo-sensor-collector/referenceFingerprints.json'));
const map=Nav.compile(maps,4);
// User-confirmed truth: stop on the main-corridor line just before entering
// the right stairs, not inside the stairs at legacy map x=0.
const rightEndpointX=map.distanceMetric.mapBreaks[0];
const expected={right:Nav.metricDistance(map,rightEndpointX),core:Nav.metricDistance(map,70.804)};
const sources=[
  ...['151808','153038'].map(id=>path.join(root,'indoor/data/raw/2026-09-01',`indoor_positioning_20260901_${id}.jsonl`)),
  ...fs.readdirSync(path.join(root,'indoor/data/raw/ios/2026-09-05')).map(n=>path.join(root,'indoor/data/raw/ios/2026-09-05',n)),
  ...fs.readdirSync(path.join(root,'indoor/data/raw/ios/2026-09-08')).map(n=>path.join(root,'indoor/data/raw/ios/2026-09-08',n)),
  ...['133338','133534','133637','133734'].map(id=>path.join(process.argv[2],`indoor_positioning_ios_20260914_${id}.jsonl`)),
  ...['170738','170901','171021','171142'].map(id=>path.join(root,'indoor/data/raw/ios/2026-09-14',`indoor_positioning_ios_20260914_${id}.jsonl`))
];
const rows=sources.map(file=>({file,rows:fs.readFileSync(file,'utf8').trim().split(/\r?\n/).map(JSON.parse)})).filter(s=>s.rows[0].label?.route_id==='4F_CORE_TO_RIGHT_STAIRS'||s.rows[0].label?.route_id==='4F_CORE_TO_RIGHT_STAIRS_REVERSE');
function endpoint(label){const x=label?.location||'';return x.includes('오른쪽 계단')?'right':x.includes('코어')?'core':null;}
const sessions=[];
for(const session of rows){
 const start=session.rows[0],config=start.positioning_config||{};
 const direction=config.initial_direction_sign ?? -1;
 const startX=endpoint(start.label)==='right' ? map.distanceMetric.mapBreaks[0]
   : endpoint(start.label)==='core' ? 70.804 : (config.start_map_x ?? 70.804);
 let legacy=createPositionTracker({floor:4,x:startX,initialDirectionSign:direction});
 const fusion=Runtime.create(maps,models,references,{floor:4,x:startX,y:0,platform:start.platform||'ios',device:start.device_model,initialDirectionSign:direction,sequenceEnabled:false});
 const endpoints=[],hasHeading=session.rows.some(r=>r.sensor==='heading_degrees');
 for(const r of session.rows){const t=r.wall_time_ms;
  if(r.sensor==='heading_degrees')Runtime.heading(fusion,t,r.values[0],r.accuracy);
  if(r.sensor==='magnetic_field_ut')Runtime.magnetic(fusion,t,r.values);
  if(r.sensor==='pressure_hpa')Runtime.pressure(fusion,t,r.values[0]);
  if(r.sensor==='accelerometer_mps2'){const step=updatePositionAcceleration(legacy,t,r.values);legacy=step.state;if(step.detected)Runtime.step(fusion,t,step.peak);}
  if(r.kind==='label'){const target=endpoint(r.label);if(target){const snap=Runtime.snapshot(fusion,[]),truth=expected[target];
   const startMeters=Nav.metricDistance(map,startX),signed=direction<0?-1:1,stepMeters=expected.core/81;
   const deadReckoningMeters=startMeters+signed*legacy.detectedSteps*stepMeters;
   const actualTravel=Math.abs(truth-startMeters);
   const progressError=value=>Number.isFinite(value)?((direction<0?startMeters-value:value-startMeters)-actualTravel):null;
   const recorded=r.comparison, recordedMeters=x=>Number.isFinite(x)?Nav.metricDistance(map,x):null;
   const recordedError=x=>Number.isFinite(x)?Math.abs(recordedMeters(x)-truth):null;
   const legacyMeters=Nav.metricDistance(map,legacy.x),fusionMeters=hasHeading?Nav.metricDistance(map,snap.x):null;
   endpoints.push({label:r.label.location,steps:legacy.detectedSteps,truthMeters:truth,legacyMeters,legacyClamped:legacy.x===0||legacy.x===135.407,deadReckoningMeters,deadReckoningErrorMeters:Math.abs(deadReckoningMeters-truth),deadReckoningProgressErrorMeters:progressError(deadReckoningMeters),fusionEligible:hasHeading,fusionMeters,fusionErrorMeters:hasHeading?Math.abs(fusionMeters-truth):null,fusionProgressErrorMeters:hasHeading?progressError(fusionMeters):null,fusionZone:hasHeading?snap.zone:null,recordedComparison:recorded?{legacyErrorMeters:recordedError(recorded.legacy_pdr?.x),legacyProgressErrorMeters:progressError(recordedMeters(recorded.legacy_pdr?.x)),sequenceOffErrorMeters:recordedError(recorded.map_constraints_sequence_off?.x),sequenceOffProgressErrorMeters:progressError(recordedMeters(recorded.map_constraints_sequence_off?.x)),sequenceOnErrorMeters:recordedError(recorded.map_constraints_sequence_on?.x),sequenceOnProgressErrorMeters:progressError(recordedMeters(recorded.map_constraints_sequence_on?.x)),sequenceOnMinusOffMapUnits:(recorded.map_constraints_sequence_on?.x??NaN)-(recorded.map_constraints_sequence_off?.x??NaN)}:null,sequence:r.sequenceStats||snap.sequenceStats||null});}}
 }
 const end=endpoints.at(-1);sessions.push({file:path.basename(session.file),direction:direction<0?'core_to_right':'right_to_core',hasHeading,endpoint:end,allEndpointLabels:endpoints});
}
const valid=sessions.filter(s=>s.endpoint),mean=k=>valid.reduce((a,s)=>a+s.endpoint[k],0)/valid.length;
const fusionValid=valid.filter(s=>s.endpoint.fusionEligible),fusionMean=fusionValid.reduce((a,s)=>a+s.endpoint.fusionErrorMeters,0)/fusionValid.length;
const report={metric:{rightCorridorMeters:48.68545341491699,coreWallCenterMeters:3.0156809091567993,coreCenterToRightEndMeters:expected.core,rightEndpointMapX:rightEndpointX,rightEndpointMeaning:'main corridor line immediately before entering the right stairs',source:'floor-04-survey.json user-confirmed 2026-09-14'},method:'Raw accelerometer/heading/magnetic/pressure replay through current Expo PDR and fusion runtime. Endpoint labels only.',limitations:['The physical scan-boundary registration is user-confirmed but classroom front distances remain unmeasured.','Older September 5 files have no heading sensor samples: fusion cannot be evaluated from them.','PDR map boundary clamping hides overshoot; deadReckoningErrorMeters reports the unbounded step-distance error.','This is a replay, not a new phone walk.','Sequence correction is disabled to isolate distance update.'],sessions,summary:{allEndpointRuns:valid.length,deadReckoningEndpointMAEMeters:mean('deadReckoningErrorMeters'),fusionEligibleRuns:fusionValid.length,fusionEndpointMAEMeters:fusionMean}};
const output=path.join(root,'indoor/data/analysis/detailed-20260914/survey-runtime-replay.json');fs.writeFileSync(output,JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report.summary,null,2));
