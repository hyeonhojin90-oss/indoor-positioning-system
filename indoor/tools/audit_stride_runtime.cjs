// Read-only runtime replay. Experimental enablement exists only in memory.
const fs=require('fs'),path=require('path');
const R=require('../web/src/positioning/runtime'),Z=require('../web/src/positioning/zone-classifier');
const data=require('../web/data/navigation/areas-v1.json'),models=require('../web/data/positioning/motion-models.json');
const refs=Z.fromLegacy(require('../../app/expo-sensor-collector/referenceFingerprints.json'));
const train=require('../data/analysis/motion-v2/evaluation.json').sessions.map(s=>s.file);
const result=[];
for(const id of ['133338','133534','133637','133734','133851']){
 const file=`indoor_positioning_ios_20260914_${id}.jsonl`;
 if(train.includes(file))throw Error('Training/evaluation overlap');
 const rows=fs.readFileSync(path.join(process.argv[2],file),'utf8').trim().split(/\r?\n/).map(JSON.parse),start=rows[0],c=start.positioning_config;
 const entry={file,variants:{}};
 for(const name of ['fixed','learned']){
  const mm=JSON.parse(JSON.stringify(models));if(name==='learned')mm.strideModels.ios.validated=true;
  const r=R.create(data,mm,refs,{floor:start.start_floor,x:c.start_map_x,y:0,platform:'ios',device:start.device_model,initialDirectionSign:c.initial_direction_sign,sequenceEnabled:false});
  const errors=[],reproduction=[],labels=[],lengths=[];
  let previous=null;
  for(const row of rows){const t=row.wall_time_ms;
   if(row.sensor==='heading_degrees')R.heading(r,t,row.values[0],row.accuracy);
   if(row.sensor==='magnetic_field_ut')R.magnetic(r,t,row.values);
   if(row.sensor==='pressure_hpa')R.pressure(r,t,row.values[0]);
   if(row.kind==='derived_position'){
    const F=require('../web/src/positioning/fusion-engine');lengths.push(F.stride(r.engine.baseStride,previous===null?null:1000/(t-previous),row.acceleration_peak_mps2,r.engine.model).length);previous=t;
    R.step(r,t,row.acceleration_peak_mps2);
   }
   if(row.kind==='label'&&row.comparison){const v=R.snapshot(r,[]),truth=row.label.map_x;errors.push(Math.abs(v.x-truth));reproduction.push(Math.abs(v.x-row.comparison.map_constraints_sequence_off.x));labels.push({label:row.label.location,truth,x:v.x,error:Math.abs(v.x-truth)});}
  }
  entry.variants[name]={n:errors.length,mean:errors.reduce((a,b)=>a+b,0)/errors.length,max:Math.max(...errors),meanRecordedDifference:reproduction.reduce((a,b)=>a+b,0)/reproduction.length,meanStride:lengths.reduce((a,b)=>a+b,0)/lengths.length,minStride:Math.min(...lengths),maxStride:Math.max(...lengths),labels};
 }
 result.push(entry);
}
const out={note:'September 5 model evaluated on September 14 logs; same recorded step events and sensor samples, zone magnetic enabled, sequence disabled. Logged callback time may differ from original processing time. Missing reference labels excluded. Models remain unvalidated on disk.',result};
fs.writeFileSync(path.resolve(__dirname,'../data/analysis/detailed-20260914/stride-runtime.json'),JSON.stringify(out,null,2));
console.log(JSON.stringify(result.map(r=>({file:r.file,...Object.fromEntries(Object.entries(r.variants).map(([k,v])=>[k,{...v,labels:undefined}]))})),null,2));
