// Analysis-only replay of existing 4F right-corridor walks.
// Compares no magnetic input, 2 s magnetic zone observations, and zone + 8-step sequence.
const fs = require('fs');
const path = require('path');
const Runtime = require('../web/src/positioning/runtime');
const Zones = require('../web/src/positioning/zone-classifier');
const Nav = require('../web/src/positioning/navigation');
const maps = require('../web/data/navigation/areas-v1.json');
const models = require('../web/data/positioning/motion-models.json');
const fingerprints = require('../../app/expo-sensor-collector/referenceFingerprints.json');

const root = path.resolve(__dirname, '../..');
const inputRoot = path.join(root, 'indoor/data/raw/ios');
const outputDir = path.join(root, 'indoor/data/analysis/detailed-20260918/4f-magnetic-ablation');
const map = Nav.compile(maps, 4);
const mean = xs => xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : null;
const median = xs => { const a = [...xs].sort((x,y)=>x-y); return a.length ? (a[(a.length-1)>>1] + a[a.length>>1]) / 2 : null; };
const std = xs => xs.length ? Math.sqrt(mean(xs.map(x => (x - mean(xs)) ** 2))) : null;
const pearson = (a,b) => { const am=mean(a),bm=mean(b),as=std(a),bs=std(b); return !a.length||a.length!==b.length||as===0||bs===0?null:mean(a.map((x,i)=>(x-am)*(b[i]-bm)))/(as*bs); };
const metric = x => Nav.metricDistance(map, x);
const errorMeters = (x, truth) => Math.abs(metric(x) - metric(truth));

function files() {
  return ['2026-09-05','2026-09-08','2026-09-14'].flatMap(day => {
    const dir=path.join(inputRoot,day);
    return fs.existsSync(dir) ? fs.readdirSync(dir).filter(f=>f.endsWith('.jsonl')).map(f=>path.join(dir,f)) : [];
  });
}
function read(file){ return fs.readFileSync(file,'utf8').trim().split(/\r?\n/).map(JSON.parse); }
function route(rows){ return rows[0]?.label?.route_id; }
function heldOut(rows){
  // September 5 created the legacy iOS magnetic references/templates.
  // Evaluate only later days so the query walk is not its own reference.
  return !path.basename(rows.file||'').includes('20260905');
}
function startX(first){ return first.positioning_config?.start_map_x ?? (String(first.label?.location).includes('오른쪽 계단') ? map.distanceMetric.mapBreaks[0] : 70.804); }
function replay(session, mode){
  const first=session.rows[0], refs=Zones.fromLegacy(fingerprints);
  const runtime=Runtime.create(maps,models,refs,{floor:4,x:startX(first),y:0,platform:'ios',device:first.device_model,
    initialDirectionSign:first.positioning_config?.initial_direction_sign ?? -1,sequenceEnabled:mode==='zone_sequence'});
  const laps=[]; let zoneAccepted=0;
  for(const row of session.rows){ const t=row.wall_time_ms;
    if(row.sensor==='heading_degrees') Runtime.heading(runtime,t,row.values[0],row.accuracy);
    if(row.sensor==='magnetic_field_ut' && mode!=='none'){
      const before=runtime.engine.lastZoneTime; Runtime.magnetic(runtime,t,row.values);
      if(runtime.engine.lastZoneTime!==before) zoneAccepted++;
    }
    if(row.sensor==='pressure_hpa') Runtime.pressure(runtime,t,row.values[0]);
    if(row.kind==='derived_position') Runtime.step(runtime,t,row.acceleration_peak_mps2);
    if(row.kind==='label' && Number.isFinite(row.label?.map_x)){
      const snap=Runtime.snapshot(runtime,[]), truth=row.label.map_x;
      laps.push({lap:row.label.lap_index,label:row.label.location,truthMapX:truth,estimateMapX:snap.x,
        errorMapUnits:Math.abs(snap.x-truth),errorMeters:errorMeters(snap.x,truth),zone:snap.zone});
    }
  }
  const snap=Runtime.snapshot(runtime,[]);
  return {lapCount:laps.length,maeMapUnits:mean(laps.map(x=>x.errorMapUnits)),maeMeters:mean(laps.map(x=>x.errorMeters)),
    endpointErrorMeters:laps.length?laps.at(-1).errorMeters:null,zoneAccepted,sequenceStats:snap.sequenceStats,laps,final:snap};
}
function magneticProfile(session){
  const labels=session.rows.filter(r=>r.kind==='label'&&Number.isFinite(r.label?.map_x));
  const mags=session.rows.filter(r=>r.sensor==='magnetic_field_ut').map(r=>({t:r.wall_time_ms,v:Math.hypot(...r.values.slice(0,3))}));
  const profile={};
  for(const label of labels){
    const name=String(label.label.location).match(/42\d\d/)?.[0];
    // A centered window refers to the same physical room in both directions.
    // A preceding interval would describe opposite neighboring segments on reverse walks.
    const values=mags.filter(x=>Math.abs(x.t-label.wall_time_ms)<=900).map(x=>x.v);
    if(name&&values.length)profile[name]=median(values);
  }
  const keys=Object.keys(profile).sort(), vals=keys.map(k=>profile[k]), m=mean(vals),sd=std(vals);
  return {raw:profile,z:Object.fromEntries(keys.map(k=>[k,sd?((profile[k]-m)/sd):0]))};
}

const sessions=files().map(file=>({file,rows:read(file)})).filter(s=>['4F_CORE_TO_RIGHT_STAIRS','4F_CORE_TO_RIGHT_STAIRS_REVERSE'].includes(route(s.rows)));
sessions.forEach(s=>s.rows.file=s.file);
const evaluated=sessions.filter(s=>heldOut(s.rows));
const results=evaluated.map(s=>{
  const id=path.basename(s.file,'.jsonl'), variants={none:replay(s,'none'),zone:replay(s,'zone'),zone_sequence:replay(s,'zone_sequence')};
  const condition=['171021','171142'].some(x=>id.includes(x))?'intentional_angle':['170738','170901'].some(x=>id.includes(x))?'normal_control':'ordinary';
  return {file:path.basename(s.file),date:path.basename(path.dirname(s.file)),direction:route(s.rows).endsWith('REVERSE')?'right_to_core':'core_to_right',condition,variants,
    deltaMeters:{zoneVsNone:variants.zone.maeMeters-variants.none.maeMeters,sequenceVsZone:variants.zone_sequence.maeMeters-variants.zone.maeMeters}};
});
const modes=['none','zone','zone_sequence'];
const summary=Object.fromEntries(modes.map(mode=>[mode,{sessions:results.length,lapCount:results.reduce((a,r)=>a+r.variants[mode].lapCount,0),
  meanSessionMAEMeters:mean(results.map(r=>r.variants[mode].maeMeters)),meanEndpointErrorMeters:mean(results.map(r=>r.variants[mode].endpointErrorMeters)),
  wins:results.filter(r=>r.variants[mode].maeMeters===Math.min(...modes.map(m=>r.variants[m].maeMeters))).length,
  zoneAccepted:results.reduce((a,r)=>a+r.variants[mode].zoneAccepted,0),sequenceEvaluated:results.reduce((a,r)=>a+r.variants[mode].sequenceStats.evaluated,0),
  sequenceApplied:results.reduce((a,r)=>a+r.variants[mode].sequenceStats.applied,0)}]));
const byCondition={};
for(const condition of [...new Set(results.map(r=>r.condition))])byCondition[condition]=Object.fromEntries(modes.map(mode=>[mode,mean(results.filter(r=>r.condition===condition).map(r=>r.variants[mode].maeMeters))]));
const byLabel={};
for(const r of results)for(const mode of modes)for(const lap of r.variants[mode].laps){
  byLabel[lap.label]??={none:[],zone:[],zone_sequence:[]};byLabel[lap.label][mode].push(lap.errorMeters);
}
for(const row of Object.values(byLabel))for(const mode of modes)row[mode]=mean(row[mode]);

const profiles=evaluated.map(s=>({file:path.basename(s.file),profile:magneticProfile(s)}));
const correlations=[];
for(let i=0;i<profiles.length;i++)for(let j=i+1;j<profiles.length;j++){
  const keys=Object.keys(profiles[i].profile.z).filter(k=>k in profiles[j].profile.z).sort();
  if(keys.length>=6)correlations.push({a:profiles[i].file,b:profiles[j].file,sharedRooms:keys.length,
    r:pearson(keys.map(k=>profiles[i].profile.z[k]),keys.map(k=>profiles[j].profile.z[k]))});
}
const report={createdAt:new Date().toISOString(),purpose:'Existing-log magnetic ablation; no engine or model changes.',dataset:{allLocalRouteSessions:sessions.length,
  evaluatedHeldOutSessions:evaluated.length,trainingSessionsExcluded:sessions.length-evaluated.length,heldOutRule:'September 5 iOS sessions created the legacy magnetic references, so only later dates are scored.'},
  variants:{none:'No magnetic callbacks',zone:'2-second scalar magnetic zone observations; 8-step pattern disabled',zone_sequence:'Same zone observations plus 8-step sequence enabled'},
  summary,byCondition,byLabel,profileReproducibility:{pairCount:correlations.length,medianPearson:median(correlations.map(x=>x.r).filter(Number.isFinite)),
    positiveStrong:correlations.filter(x=>x.r>=.7).length,negativeOrWeak:correlations.filter(x=>x.r<.3).length,correlations},results,
  limitations:['Intermediate classroom x coordinates are map-derived, not surveyed physical positions; meter conversion is for arm-to-arm comparison, not field accuracy.',
    'The held-out walks are later dates but use the same user/device/building.','Magnetic zone references use scalar field magnitude and coarse zone labels; they do not identify each classroom.',
    'No AP input exists in these route logs, so this isolates PDR and magnetic behavior.']};
fs.mkdirSync(outputDir,{recursive:true});
fs.writeFileSync(path.join(outputDir,'report.json'),JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify({dataset:report.dataset,summary,byCondition,profileReproducibility:{...report.profileReproducibility,correlations:undefined},sessions:results.map(r=>({file:r.file,condition:r.condition,none:r.variants.none.maeMeters,zone:r.variants.zone.maeMeters,zone_sequence:r.variants.zone_sequence.maeMeters,delta:r.deltaMeters,sequence:r.variants.zone_sequence.sequenceStats}))},null,2));
