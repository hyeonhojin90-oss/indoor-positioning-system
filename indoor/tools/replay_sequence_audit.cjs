// Same raw inputs for both branches; labels are evaluation only, never engine input.
const fs=require('fs'),path=require('path'),crypto=require('crypto');
const R=require('../web/src/positioning/runtime'),Z=require('../web/src/positioning/zone-classifier');
const data=require('../web/data/navigation/areas-v1.json'),models=require('../web/data/positioning/motion-models.json');
const refs=Z.fromLegacy(require('../../app/expo-sensor-collector/referenceFingerprints.json'));
const folder=path.resolve(__dirname,'../data/raw/ios/2026-09-08');
const quantile=(xs,p)=>{const a=[...xs].sort((a,b)=>a-b);return a.length?a[Math.ceil(p*a.length)-1]:null;};
const sessions=[];
for(const file of fs.readdirSync(folder).filter(f=>f.endsWith('.jsonl'))){
 const raw=fs.readFileSync(path.join(folder,file)),rows=raw.toString().trim().split(/\r?\n/).map(JSON.parse),first=rows[0];
 const variants={};
 for(const enabled of [false,true]){
  const r=R.create(data,models,refs,{floor:first.start_floor,x:first.positioning_config.start_map_x,y:0,
   platform:'ios',device:first.device_model,initialDirectionSign:first.positioning_config.initial_direction_sign,sequenceEnabled:enabled});
  const laps=[];let sampled=0,unknown=0;
  for(const row of rows){const t=row.wall_time_ms;
   if(row.sensor==='heading_degrees')R.heading(r,t,row.values[0],row.accuracy);
   if(row.sensor==='magnetic_field_ut')R.magnetic(r,t,row.values);
   if(row.sensor==='pressure_hpa')R.pressure(r,t,row.values[0]);
   if(row.kind==='derived_position'){R.step(r,t,row.acceleration_peak_mps2);sampled++;if(R.snapshot(r,[]).zone==='unknown')unknown++;}
   if(row.kind==='label'&&Number.isFinite(row.label?.map_x)){const v=R.snapshot(r,[]);laps.push({lap:row.label.lap_index,error:Math.hypot(v.x-row.label.map_x,v.y),floor:v.floor});}
  }
  const final=R.snapshot(r,[]),errors=laps.map(l=>l.error);
  variants[enabled?'on':'off']={mae:errors.reduce((a,b)=>a+b,0)/errors.length,median:quantile(errors,.5),p95:quantile(errors,.95),
   unknownStepFraction:sampled?unknown/sampled:null,laps,sequenceStats:final.sequenceStats,final};
 }
 sessions.push({file,sha256:crypto.createHash('sha256').update(raw).digest('hex'),direction:first.route_direction,...variants});
}
const report={engineVersion:sessions[0]?.on.final.version,mapVersion:data.version,
 limitations:['Existing tuning sessions, not independent validation','Map units, not meter accuracy','Both arms use magnetic zone observations','Unknown fraction is sampled at steps, not elapsed time','No raw or training data modified'],sessions};
const output=path.resolve(__dirname,'../data/analysis/sequence-audit-20260909.json');
fs.writeFileSync(output,JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify(sessions.map(s=>({file:s.file,off:s.off.mae,on:s.on.mae,stats:s.on.sequenceStats})),null,2));
