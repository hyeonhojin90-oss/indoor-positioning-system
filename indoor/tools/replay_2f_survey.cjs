const fs=require('fs'),path=require('path'),Module=require('module');
const root=path.resolve(__dirname,'../..'),out=path.join(root,'indoor/data/analysis/2f-survey-apply-20260922');
const dir=path.join(root,'indoor/web/src/positioning');
function version(before){
 const cache={};function load(name){if(cache[name])return cache[name];
  const original=path.join(dir,name+'.js'),saved=path.join(out,'before/indoor/web/src/positioning',name+'.js');
  const file=before&&fs.existsSync(saved)?saved:original;
  const m=new Module(original,module);m.filename=original;m.paths=module.paths;
  const normal=m.require.bind(m);m.require=id=>id.startsWith('./')?load(id.slice(2)):normal(id);
  m._compile(fs.readFileSync(file,'utf8'),original);return cache[name]=m.exports;}
 return {R:load('runtime'),N:load('navigation'),data:JSON.parse(fs.readFileSync(path.join(before?out+'/before':root,'indoor/web/data/navigation/areas-v1.json'),'utf8'))};
}
const versions={before:version(true),after:version(false)},models=require('../web/data/positioning/motion-models.json');
const refs=require('../web/data/positioning/ble-references.json').references;
// Android SensorManager.getOrientation(R)[0] = atan2(R[1], R[4]).
const heading=v=>{const [x,y,z,w0]=v,w=w0??Math.sqrt(Math.max(0,1-x*x-y*y-z*z));return (Math.atan2(2*(x*y-z*w),1-2*(x*x+z*z))*180/Math.PI+360)%360;};
const inputs=require('../data/analysis/2f-survey-apply-20260922/sessions.json');
const results=[];
for(const s of inputs){
 if(!/CORE_TO|EXTENSION_V3/.test(s.route)){results.push({...s,excluded:'Legacy ambiguous branch labels or unsurveyed study endpoint; no fabricated start/end truth.'});continue;}
 const rows=fs.readFileSync(path.join(root,s.file),'utf8').trim().split(/\r?\n/).map(JSON.parse);
 const reversed=/_REVERSE$/.test(s.route),extension=/EXTENSION/.test(s.route),left=/LEFT/.test(s.route);
 const labels=rows.filter(r=>r.kind==='label'),destination=rows[0].label?.destination;
 const firstRepeatedStart=labels[0]?.label?.location===rows[0].label?.location ? labels[0].wall_time_ms : rows[0].wall_time_ms;
 const firstDestination=labels.find(r=>r.label?.location===destination);
 const startTime=extension?firstRepeatedStart:rows[0].wall_time_ms;
 const endTime=extension?(firstDestination?.wall_time_ms??labels.at(-1)?.wall_time_ms):labels.at(-1)?.wall_time_ms??rows.at(-1).wall_time_ms;
 const row={file:s.file,route:s.route,bleObservations:rows.filter(r=>r.kind==='ble_observation'&&r.wall_time_ms<=endTime).length};
 for(const [name,{R,N,data}] of Object.entries(versions)){
  const map=N.compile(data,2),a=map.areas.find(a=>a.id===(extension?(reversed?'extension':'entry'):reversed?(left?'stairs_left':'stairs_right'):'core_junction'));
  const ext=map.areas.find(a=>a.id==='extension');
  const start=extension?{x:(ext.rect[0]+ext.rect[2])/2,y:reversed?ext.rect[3]:1.18}:{x:(a.rect[0]+a.rect[2])/2,y:(a.rect[1]+a.rect[3])/2};
  const safeModels={...models,templates:(models.templates||[]).filter(t=>t.source!==path.basename(s.file))};
  const rt=R.create(data,safeModels,refs,{floor:2,...start,platform:'android',device:rows[0].device,sequenceEnabled:true,magneticZoneEnabled:false,bleEnabled:true});
  const laps=[];
  for(const r of rows){const t=r.wall_time_ms;if(t<startTime)continue;if(t>endTime)break;
   if(r.sensor==='rotation_vector')R.heading(rt,t,Math.round(heading(r.values)),3);
   else if(r.sensor==='heading_degrees')R.heading(rt,t,r.values[0],r.accuracy);
   else if(r.sensor==='accelerometer_mps2')R.acceleration(rt,t,r.values);
   else if(r.sensor==='magnetic_field_ut')R.magnetic(rt,t,r.values);
   else if(r.sensor==='pressure_hpa')R.pressure(rt,t,r.values[0]);
   else if(r.kind==='ble_observation')R.ble(rt,t,r);
   if(r.kind==='label'){const v=R.snapshot(rt,[]);laps.push({label:r.label.location,x:v.x,y:v.y,zone:v.zone,steps:v.steps});}
  }
  const v=R.snapshot(rt,[]);
  // Interpret the old display depth onto the SAME new boundary references.
  const oldEntry=1.17,oldNear=1.17+115*7.9/110,oldEnd=1.17+615*7.9/110;
  const survey=versions.after.data.floors['2'].survey;
  const physicalY=name==='after'?v.y:v.y<=oldEntry?v.y:v.y<=oldNear?oldEntry+(v.y-oldEntry)*survey.entry_to_straight_m/(oldNear-oldEntry):oldEntry+survey.entry_to_straight_m+(v.y-oldNear)*survey.straight_length_m/(oldEnd-oldNear);
  row[name]={start,final:{x:v.x,y:v.y,zone:v.zone},steps:v.steps,ble:v.bleStats,sequence:v.sequenceStats,laps,
   extensionAxisProxyResidualM:extension?physicalY-(reversed?0:1.17+survey.entry_to_end_m):null,
   extensionCrossAxisProxyResidualM:extension?(v.x-start.x)*versions.after.data.floors['2'].extensionMotionMetric.xMetersPerUnit:null};
 }
 results.push(row);
}
const report={method:'Same raw sensors, seed, mode4 and production references; query excluded from templates. Android rotation-vector heading follows SensorManager, not generic quaternion yaw.',
 limitations:['No production 2F BLE references: observations are delivered but cannot correct position.',
 'Extension endpoint residual is a longitudinal PROXY, not surveyed error: final stair-entry lap is not confirmed identical to scanned end wall; start label is main-corridor center.',
 'Only start coordinates used. Intermediate labels never reset particles; room door coordinates remain unmeasured.',
 'Both variants start at corresponding endpoint boundaries, not the old deployed area midpoint. Geometry/unit correction comparison; not an isolated sensor ablation.',
 'The after engine also shares one stride across all particles in a constrained extension axis; the before engine retains per-particle scale there.',
 'For duplicated start/destination labels, evaluation begins after the repeated start marker and ends at the first arrival marker.'],results};
fs.writeFileSync(path.join(out,'replay-results.json'),JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify(results.map(r=>({route:r.route,file:path.basename(r.file),excluded:r.excluded,before:r.before&&{...r.before.final,steps:r.before.steps,residual:r.before.extensionAxisProxyResidualM},after:r.after&&{...r.after.final,steps:r.after.steps,residual:r.after.extensionAxisProxyResidualM,ble:r.after.ble}})),null,2));
