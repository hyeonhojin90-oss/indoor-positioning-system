const fs=require('fs'),path=require('path'),Module=require('module');
const root=path.resolve(__dirname,'../..'),dir=path.join(root,'indoor/web/src/positioning');
const R=require('../web/src/positioning/runtime'),Z=require('../web/src/positioning/zone-classifier');
const old=new Module(path.join(dir,'fusion-engine.js'),module);old.filename=path.join(dir,'fusion-engine.js');old.paths=module.paths;
old._compile(fs.readFileSync(path.join(root,'backups/20260908-entry-display/fusion-engine.js'),'utf8'),old.filename);
const rm=new Module(path.join(dir,'runtime.js'),module);rm.filename=path.join(dir,'runtime.js');rm.paths=module.paths;
const req=rm.require.bind(rm);rm.require=id=>id==='./fusion-engine'?old.exports:req(id);rm._compile(fs.readFileSync(rm.filename,'utf8'),rm.filename);
const data=require('../web/data/navigation/areas-v1.json'),models=require('../web/data/positioning/motion-models.json');
const refs=Z.fromLegacy(require('../../app/expo-sensor-collector/referenceFingerprints.json')),out=[];
for(const f of fs.readdirSync(path.join(root,'indoor/data/raw/ios/2026-09-08'))){if(!f.endsWith('.jsonl'))continue;
 const rows=fs.readFileSync(path.join(root,'indoor/data/raw/ios/2026-09-08',f),'utf8').trim().split(/\r?\n/).map(JSON.parse),first=rows[0],results={};
 for(const [name,rt,sequenceEnabled] of [['before',rm.exports,false],['after_off',R,false],['after_on',R,true]]){
 const s=rt.create(data,models,refs,{floor:4,x:first.positioning_config.start_map_x,y:0,platform:'ios',device:first.device_model,
  initialDirectionSign:first.positioning_config.initial_direction_sign,sequenceEnabled}),laps=[];
 for(const r of rows){const t=r.wall_time_ms;if(r.sensor==='heading_degrees')rt.heading(s,t,r.values[0],r.accuracy);
 if(r.sensor==='magnetic_field_ut')rt.magnetic(s,t,r.values);if(r.sensor==='pressure_hpa')rt.pressure(s,t,r.values[0]);
 if(r.kind==='derived_position')rt.step(s,t,r.acceleration_peak_mps2);
 if(r.kind==='label'){const v=rt.snapshot(s,[]);laps.push({lap:r.label.lap_index,x:v.x,y:v.y,zone:v.zone,error:Math.hypot(v.x-r.label.map_x,v.y)});}}
 const v=rt.snapshot(s,[]);results[name]={final:[v.x,v.y,v.zone],mae:laps.reduce((a,l)=>a+l.error,0)/laps.length,laps};}
 out.push({file:f,...results});}
fs.writeFileSync(path.join(root,'indoor/data/analysis/entry-fix-20260908.json'),JSON.stringify(out,null,2)+'\n');
console.log(JSON.stringify(out.map(({file,before,after_off,after_on})=>({file,
 before:{final:before.final,mae:before.mae},after_off:{final:after_off.final,mae:after_off.mae},after_on:{final:after_on.final,mae:after_on.mae}})),null,2));
