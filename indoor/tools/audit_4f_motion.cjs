// Diagnostic replay only; never edits engine, raw measurements or training data.
const fs=require('fs'),path=require('path');
const F=require('../web/src/positioning/fusion-engine');
const N=require('../web/src/positioning/navigation');
const data=require('../web/data/navigation/areas-v1.json');
const branch=N.branchMoves;
const results=[];
for(const id of ['133338','133534','133637','133734']){
 const rows=fs.readFileSync(path.join(process.argv[2],`indoor_positioning_ios_20260914_${id}.jsonl`),'utf8').trim().split(/\r?\n/).map(JSON.parse);
 const c=rows[0].positioning_config,out={id};
 for(const variant of ['map_only','no_branches','no_branches_unit_scale']){
  N.branchMoves=variant==='map_only'?branch:()=>[];
  const s=F.create(data,{floor:4,x:c.start_map_x,y:0,initialDirectionSign:c.initial_direction_sign});
  if(variant==='no_branches_unit_scale')s.particles.forEach(p=>p.scale=1);
  let skipped=0,steps=0;const errors=[],bounds={0.5:[],1:[],2:[]};
  for(const r of rows){const t=r.wall_time_ms;
   if(r.sensor==='heading_degrees')F.heading(s,r.values[0],t,r.accuracy);
   if(r.kind==='derived_position'){F.step(s,t,r.acceleration_peak_mps2);steps++;if(s.reason==='heading_unavailable')skipped++;}
   if(r.kind==='label'&&r.comparison){const v=F.snapshot(s),pdr=r.comparison.legacy_pdr.x;errors.push(Math.abs(v.x-r.label.map_x));
    for(const [limit,es] of Object.entries(bounds)){const x=['main_left','main_right'].includes(v.zone)?Math.max(pdr-Number(limit),Math.min(pdr+Number(limit),v.x)):v.x;es.push(Math.abs(x-r.label.map_x));}}
  }
  out[variant]={n:errors.length,mean:errors.reduce((a,b)=>a+b,0)/errors.length,steps,skippedHeading:skipped,final:F.snapshot(s).x,displayBoundMAE:Object.fromEntries(Object.entries(bounds).map(([k,v])=>[k,v.reduce((a,b)=>a+b,0)/v.length]))};
 }
 results.push(out);
}
N.branchMoves=branch;
const output={note:'Controlled motion-only replay of recorded legacy step events; no magnetic/quality weighting. Not exact live runtime reproduction. Unit scale isolates persistent particle stride variability, not all particle effects.',results};
fs.writeFileSync(path.join(__dirname,'../data/analysis/detailed-20260914/motion-ablation.json'),JSON.stringify(output,null,2));
console.log(JSON.stringify(output,null,2));
