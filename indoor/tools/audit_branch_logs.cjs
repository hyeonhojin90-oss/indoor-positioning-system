// Read-only raw audit; write a separate derived report, never alter labels/manifest.
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const root=path.resolve(__dirname,'..'),manifest=JSON.parse(fs.readFileSync(path.join(root,'data/manifest.json'),'utf8'));
const report=[];
for(const session of manifest.sessions.filter(s=>s.include_in_analysis!==false&&/^[23]F_(2107_OPEN|STUDY|EXTENSION|IT_HALL)$/.test(s.route_id))){
 const file=path.join(root,'data',manifest.raw_directory,session.file),buffer=fs.readFileSync(file);
 const rows=buffer.toString('utf8').trim().split(/\r?\n/).map(JSON.parse),sensors={},labels=[];
 let backwards=0,last=-Infinity;
 for(const r of rows){if(r.wall_time_ms<last)backwards++;last=r.wall_time_ms;
  if(r.sensor)sensors[r.sensor]=(sensors[r.sensor]||0)+1;
  if(r.label)labels.push({kind:r.kind,time:r.wall_time_ms-rows[0].wall_time_ms,label:r.label,steps:r.step_counter??r.steps_since_start??null});}
 const segments=labels.slice(1).map((label,i)=>{
  const start=labels[i].time+rows[0].wall_time_ms,end=label.time+rows[0].wall_time_ms;
  const samples=rows.filter(r=>r.kind==='sample'&&r.wall_time_ms>=start&&r.wall_time_ms<end);
  const values=sensor=>samples.filter(r=>r.sensor===sensor).map(r=>r.values);
  const mags=values('magnetic_field_ut').map(v=>Math.hypot(...v)),pressure=values('pressure_hpa').map(v=>v[0]);
  const steps=rows.filter(r=>r.sensor==='step_counter'&&r.wall_time_ms<=end),before=steps.filter(r=>r.wall_time_ms<=start).at(-1);
  const mean=mags.reduce((a,v)=>a+v,0)/mags.length;
  return {from:labels[i].label.location,to:label.label.location,durationMs:end-start,
   stepDelta:steps.length?(steps.at(-1).values[0]-(before?.values[0]??rows[0].start_step_counter)):null,
   magneticMean:mean,magneticSd:Math.sqrt(mags.reduce((a,v)=>a+(v-mean)**2,0)/mags.length),
   pressureDelta:pressure.length?pressure.at(-1)-pressure[0]:null};
 });
 report.push({file:session.file,route:session.route_id,sha256:crypto.createHash('sha256').update(buffer).digest('hex'),records:rows.length,segments,
  durationMs:rows.at(-1).wall_time_ms-rows[0].wall_time_ms,ended:rows.at(-1).kind==='session_end',backwards,sensors,labels,
  limitation:/2F_(STUDY|EXTENSION)/.test(session.route_id)?'Legacy 2107 start label differs from confirmed pillar/TDM entry; no coordinate truth or forced path replay.':
  'Single session; labels are event evidence, not surveyed continuous XY truth.'});
}
const dest=path.join(root,'data/analysis/branch-audit-20260908.json');
fs.writeFileSync(dest,JSON.stringify({date:'2026-09-08',sessions:report},null,2)+'\n');
console.log(JSON.stringify(report.map(({labels,...r})=>({...r,labels:labels.map(l=>({time:l.time,...l.label}))})),null,2));
