// Deterministic held-out-session replay. Outputs are diagnostics, not surveyed accuracy.
const fs=require("node:fs"),path=require("node:path"),crypto=require("node:crypto");
const repo=path.resolve(__dirname,"../../..");
const Fusion=require(path.join(repo,"indoor/web/src/positioning/fusion-engine"));
const Zones=require(path.join(repo,"indoor/web/src/positioning/zone-classifier"));
const {createPositionTracker,updatePositionAcceleration}=require("../positionTracking");
const {FLOOR_MAPS}=require("../routes");
const data=require(path.join(repo,"indoor/web/data/navigation/areas-v1.json"));
const manifest=require(path.join(repo,"indoor/data/ios_manifest.json"));
const median=xs=>[...xs].sort((a,b)=>a-b)[Math.floor(xs.length/2)];
const sessions=manifest.sessions.filter(s=>s.status.startsWith("accepted")).map(s=>{
  const filename=path.join(repo,"indoor/data",manifest.raw_directory,s.file),buf=fs.readFileSync(filename);
  if(crypto.createHash("sha256").update(buf).digest("hex")!==s.sha256)throw new Error(`Raw checksum mismatch: ${s.file}`);
  return {...s,records:buf.toString("utf8").trim().split(/\r?\n/).map(JSON.parse)};
});
function labelReference(label) {
  const text=label.location || "",room=FLOOR_MAPS[3].rooms.find(r=>text.startsWith(`${r.id} `));
  if(text.includes("오른쪽 계단"))return {zone:"stairs_right",x:0};
  if(text.includes("코어"))return {zone:"core_junction",x:70.804};
  if(room && Number.isFinite(room.front_x ?? room.x))return {zone:"main_right",x:room.front_x ?? room.x};
  return null;
}
function windows(session) {
  const mag=session.records.filter(r=>r.sensor==="magnetic_field_ut");
  return session.records.filter(r=>["label","session_start"].includes(r.kind)&&r.label).flatMap(r=>{
    const node=labelReference(r.label);if(!node)return [];
    const t=r.session_elapsed_ms, start=r.kind==="session_start" ? t : t-900,end=r.kind==="session_start" ? t+900 : t;
    const values=mag.filter(m=>m.session_elapsed_ms>=start&&m.session_elapsed_ms<=end).map(m=>Math.hypot(...m.values));
    if(values.length<4)return [];
    const magnetic=median(values),spread=Math.sqrt(values.reduce((s,v)=>s+(v-magnetic)**2,0)/values.length);
    return [{floor:4,platform:"ios",zone:node.zone,magnetic,spread,source:session.file,time:t,label:r.label.location}];
  });
}
const examples=sessions.flatMap(windows),confusion={},results=[];
for(const session of sessions) {
  const training=examples.filter(r=>r.source!==session.file), evaluation=examples.filter(r=>r.source===session.file);
  for(const row of evaluation) {
    const result=Zones.classify({id:`label-${row.time}`,timestamp:row.time,platform:"ios",magnetic:row.magnetic,magneticStd:row.spread},training,row.time);
    const predicted=result.candidates[0]?.zone || "unavailable";
    confusion[row.zone] ||= {};confusion[row.zone][predicted]=(confusion[row.zone][predicted] || 0)+1;
  }
  let baseline=createPositionTracker({floor:4,x:70.804,initialDirectionSign:-1});
  const areaOnly=Fusion.create(data,{floor:4,x:70.804}),fused=Fusion.create(data,{floor:4,x:70.804});
  let mag=[],windowTime=0,updates=0;
  for(const r of session.records) {
    const t=r.session_elapsed_ms;
    if(r.sensor==="accelerometer_mps2") {
      const result=updatePositionAcceleration(baseline,t,r.values);baseline=result.state;
      if(result.detected) for(const engine of [areaOnly,fused]) {Fusion.heading(engine,355,t,3);Fusion.step(engine,t,result.peak);}
    } else if(r.sensor==="pressure_hpa") {
      Fusion.pressure(areaOnly,t,r.values[0]);Fusion.pressure(fused,t,r.values[0]);
    } else if(r.sensor==="magnetic_field_ut") {
      mag.push(Math.hypot(...r.values));
      if(t-windowTime>=2000) {
        if(mag.length>=8) {
          const magnetic=median(mag),magneticStd=Math.sqrt(mag.reduce((s,v)=>s+(v-magnetic)**2,0)/mag.length);
          const obs=Zones.classify({id:`mag-${t}`,timestamp:t,platform:"ios",magnetic,magneticStd},training,t);
          if(Fusion.observeZone(fused,obs,t))updates++;
        }
        mag=[];windowTime=t;
      }
    }
  }
  results.push({file:session.file,raw_sha256:session.sha256,heading_source:"route_assumption_355deg_not_recorded_sensor",
    held_out_training_windows:training.length,detected_steps:baseline.detectedSteps,zone_updates:updates,
    legacy_final_x:baseline.x,area_only:Fusion.snapshot(areaOnly),with_zone:Fusion.snapshot(fused)});
}
const labels=Object.keys(confusion),total=labels.reduce((s,l)=>s+Object.values(confusion[l]).reduce((a,b)=>a+b,0),0);
const accuracy=labels.reduce((s,l)=>s+(confusion[l][l]||0),0)/total;
const macroRecall=labels.reduce((s,l)=>s+(confusion[l][l]||0)/Object.values(confusion[l]).reduce((a,b)=>a+b,0),0)/labels.length;
const report={version:Fusion.VERSION,method:"leave-one-session-out, three same-day iOS 4F right runs",
  limitations:["900ms label windows are weak zone labels, not independently surveyed position truth",
    "No same-run training; raw hashes checked before replay",
    "Heading forced from known route because schema4 did not record absolute heading",
    "No independent metric position accuracy; no new Android AP anchor logs; no cross-device pooling",
    "Most label windows are main corridor; report macro recall as well as accuracy"],
  zone_evaluation:{windows:total,accuracy,macro_recall:macroRecall,confusion},sessions:results};
const output=process.env.FUSION_REPLAY_OUTPUT || path.join(repo,"indoor/data/analysis/fusion-v1");fs.mkdirSync(output,{recursive:true});
fs.writeFileSync(path.join(output,"replay.json"),JSON.stringify(report,null,2)+"\n");
console.log(JSON.stringify({output,zone_evaluation:report.zone_evaluation,
  sessions:results.map(r=>({file:r.file,steps:r.detected_steps,baseline_x:r.legacy_final_x,area_x:r.area_only.x,fused_x:r.with_zone.x,zone:r.with_zone.zone}))},null,2));
