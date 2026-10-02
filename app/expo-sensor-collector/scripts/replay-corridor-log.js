// Replay recorded detected steps and sensor chronology. Labels are evaluation only.
const fs=require('node:fs');
const R=require('../../../indoor/web/src/positioning/runtime');
const Z=require('../../../indoor/web/src/positioning/zone-classifier');
const data=require('../../../indoor/web/data/navigation/areas-v1.json');
const models=require('../../../indoor/web/data/positioning/motion-models.json');
const refs=Z.fromLegacy(require('../referenceFingerprints.json'));
const rows=fs.readFileSync(process.argv[2],'utf8').trim().split(/\r?\n/).map(JSON.parse);
const first=rows[0],report=[];
for(const enabled of [false,true]){
  const r=R.create(data,models,refs,{floor:first.start_floor,x:first.positioning_config.start_map_x,y:0,
    platform:'ios',device:first.device_model,sequenceEnabled:enabled});
  for(const row of rows){
    const t=row.wall_time_ms;
    if(row.sensor==='heading_degrees')R.heading(r,t,row.values[0],row.accuracy);
    if(row.sensor==='magnetic_field_ut')R.magnetic(r,t,row.values);
    if(row.sensor==='pressure_hpa')R.pressure(r,t,row.values[0]);
    if(row.kind==='derived_position')R.step(r,t,row.acceleration_peak_mps2);
    if(row.kind==='label'){
      const s=R.snapshot(r,require('../routes').FLOOR_MAPS);
      report.push({on:enabled,lap:row.label.lap_index,actual:row.label.location,zone:s.zone,x:s.x,y:s.y});
    }
  }
}
console.log(JSON.stringify(report,null,2));
