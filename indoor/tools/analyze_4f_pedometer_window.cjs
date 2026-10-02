// Analyze iOS Core Motion session-window counts against 4F PDR output.
// Analysis only: it never changes PDR, Fusion, stride values, or raw logs.
const crypto=require('crypto'),fs=require('fs'),path=require('path');
const root=path.resolve(__dirname,'../..');
const Navigation=require('../web/src/positioning/navigation');
const navigation=Navigation.compile(require('../web/data/navigation/areas-v1.json'),4);
const survey=require('../web/data/maps/floor-04-survey.json');
const ids=['200838','200949','201100'];
const source=path.join(root,'indoor/data/raw/ios/2026-09-14');
const referenceDistance=survey.core_center_to_right_end.reference_length_m;
const nominalSteps=81;
const rightX=navigation.distanceMetric.mapBreaks[0],coreX=70.804;
const mean=values=>values.reduce((sum,value)=>sum+value,0)/values.length;
const stdev=values=>Math.sqrt(mean(values.map(value=>(value-mean(values))**2)));
const summary=values=>({mean:mean(values),stdev:stdev(values),min:Math.min(...values),max:Math.max(...values)});
const read=file=>fs.readFileSync(file,'utf8').trim().split(/\r?\n/).map(JSON.parse);
const metric=x=>Navigation.metricDistance(navigation,x);
const rows=ids.map(id=>{
  const file=path.join(source,`indoor_positioning_ios_20260914_${id}.jsonl`),data=read(file);
  const start=data.find(row=>row.kind==='session_start'),end=[...data].reverse().find(row=>row.kind==='session_end');
  const forward=start.route_direction==='forward',truthX=forward?rightX:coreX;
  const audit=end.pedometer_audit||{};
  const position=end.final_position||{},off=end.final_fusion||{},on=end.final_fusion_sequence_on||{};
  const positionError=Math.abs(metric(position.map_x)-metric(truthX));
  const offError=Math.abs(metric(off.x)-metric(truthX));
  const onError=Math.abs(metric(on.x)-metric(truthX));
  return {
    file:path.basename(file),sha256:crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex'),
    route:forward?'core_to_right':'right_to_core',durationSeconds:(end.wall_time_ms-start.wall_time_ms)/1000,
    completed:end.completed===true,laps:{completed:end.completed_laps,expected:end.expected_laps},
    counts:{accelerometer_detector:position.detected_steps,watch_steps:audit.watch_steps,query_steps:audit.query_steps,
      detector_minus_query:position.detected_steps-audit.query_steps,query_supported:audit.query_supported,query_error:audit.query_error||null},
    endpoint:{truthMetricMeters:metric(truthX),legacyPdrErrorMeters:positionError,
      fusionOffErrorMeters:offError,fusionOnErrorMeters:onError,fusionOnMinusOffMapUnits:on.x-off.x,
      legacyZone:position.nearest_rooms?.[0]?.id||null,fusionZone:off.zone||null},
    // Counter-only thought experiment, not a runtime replay: it assumes every
    // native count represents the 81-step reference route with a fixed stride.
    queryCountOnlyReferenceErrorMeters:Math.abs(audit.query_steps-nominalSteps)*referenceDistance/nominalSteps
  };
});
const output={
  purpose:'Compare the new iOS session-window Pedometer count with the current accelerometer PDR on the same user-confirmed 4F route. Analysis only.',
  routeReference:{meters:referenceDistance,nominalDetectorSteps:nominalSteps,start:'core center or right stair entry main-corridor line',end:'opposite endpoint'},
  sessions:rows,
  summary:{
    accelerometerDetector:summary(rows.map(row=>row.counts.accelerometer_detector)),
    watch:summary(rows.map(row=>row.counts.watch_steps)),
    query:summary(rows.map(row=>row.counts.query_steps)),
    legacyPdrEndpointErrorMeters:summary(rows.map(row=>row.endpoint.legacyPdrErrorMeters)),
    fusionOffEndpointErrorMeters:summary(rows.map(row=>row.endpoint.fusionOffErrorMeters)),
    fusionOnEndpointErrorMeters:summary(rows.map(row=>row.endpoint.fusionOnErrorMeters)),
    queryCountOnlyReferenceErrorMeters:summary(rows.map(row=>row.queryCountOnlyReferenceErrorMeters))
  },
  conclusion:'query_steps is more stable in these three runs, but substituting it blindly would improve one forward run and worsen the reverse run. Keep it diagnostic until an independent holdout confirms a direction-independent rule.'
};
// A prospective personal-stride check: learn one shared stride from the other
// completed routes, then apply it to the held-out route. The native query is
// intentionally only a training target; runtime still receives detector steps.
output.queryStrideLearningLeaveOneOut=rows.map((test,index)=>{
  const train=rows.filter((_,candidate)=>candidate!==index);
  const stride=train.length*referenceDistance/train.reduce((sum,row)=>sum+row.counts.query_steps,0);
  const errorFor=count=>Math.abs(count*stride-referenceDistance);
  return {file:test.file,learnedStrideMeters:stride,
    heldOutDetectorSteps:test.counts.accelerometer_detector,heldOutQuerySteps:test.counts.query_steps,
    detectorRuntimeEndpointErrorMeters:errorFor(test.counts.accelerometer_detector),
    queryCountReferenceErrorMeters:errorFor(test.counts.query_steps)};
});
output.queryStrideLearningLeaveOneOutSummary={
  detectorRuntimeEndpointMAEMeters:mean(output.queryStrideLearningLeaveOneOut.map(row=>row.detectorRuntimeEndpointErrorMeters)),
  queryCountReferenceMAEMeters:mean(output.queryStrideLearningLeaveOneOut.map(row=>row.queryCountReferenceErrorMeters)),
  currentFixedDetectorEndpointMAEMeters:mean(rows.map(row=>row.endpoint.legacyPdrErrorMeters))
};
const destination=path.join(root,'indoor/data/analysis/detailed-20260914/4f-pedometer-window-new3.json');
fs.writeFileSync(destination,JSON.stringify(output,null,2)+'\n');
console.log(JSON.stringify(output,null,2));
