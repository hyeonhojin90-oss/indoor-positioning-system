// Diagnostic instrumentation in memory only; production engine is not edited.
const fs=require('fs'),path=require('path'),Module=require('module');
const root=path.resolve(__dirname,'../..'),dir=path.join(root,'indoor/web/src/positioning');
const source=fs.readFileSync(path.join(dir,'fusion-engine.js'),'utf8');
function engine(){const m=new Module(path.join(dir,'fusion-engine.js'),module);m.filename=path.join(dir,'fusion-engine.js');m.paths=module.paths;
 m._compile(source.replace('const to=branch ? branch.to : aligned.to;',`const to=branch ? branch.to : aligned.to;
 if(!s.diag)s.diag=[]; s.diag.push({step:s.steps,time,heading:s.heading.value,offset:s.corridorHeadingOffset,area:Nav.areaAt(getMap(s,p.floor),p)?.id||'unknown',aligned:aligned.aligned,weight:p.weight,dx:to.x-p.x,dy:to.y-p.y,length});`),m.filename);return m.exports;}
const data=require('../web/data/navigation/areas-v1.json');const F=engine();
const Q=require('../web/src/positioning/quality');
const folder=path.join(root,'indoor/data/raw/ios/2026-09-08'),output=[];
for(const file of fs.readdirSync(folder).filter(f=>f.endsWith('.jsonl'))){const rows=fs.readFileSync(path.join(folder,file),'utf8').trim().split(/\r?\n/).map(JSON.parse),first=rows[0];
 const scenarios=[];
 for(const fixed of [false,true]){const s=F.create(data,{floor:4,x:first.positioning_config.start_map_x,y:0});const trace=[];let last=null,intervals=[];
 for(const r of rows){const t=r.wall_time_ms;
 if(r.sensor==='heading_degrees')F.heading(s,fixed?(first.route_direction==='reverse'?175:355):r.values[0],t,r.accuracy);
 if(r.kind==='derived_position'){
 if(last!==null)intervals.push(t-last);intervals=intervals.slice(-8);last=t;
 const before=F.snapshot(s);s.diag=[];F.step(s,t,r.acceleration_peak_mps2,Q.gait(intervals,r.acceleration_peak_mps2).weight);const after=F.snapshot(s);
 const d=s.diag,w=d.reduce((a,v)=>a+v.weight,0);trace.push({step:s.steps,seconds:(t-first.wall_time_ms)/1000,heading:s.heading?.value,
 alignedMass:d.filter(v=>v.aligned).reduce((a,v)=>a+v.weight,0),dx:w?d.reduce((a,v)=>a+v.dx*v.weight,0)/w:0,
 before:[before.x,before.y,before.zone],after:[after.x,after.y,after.zone],reason:s.reason});
 }}
 scenarios.push({fixed_axis:fixed,note:'No magnetic/sequence weighting; same detected steps and gait quality. Counterfactual fixed heading is not a deployable correction.',
 final:F.snapshot(s),weightedX:s.particles.reduce((a,p)=>a+p.x*p.weight,0),weightedScale:s.particles.reduce((a,p)=>a+p.scale*p.weight,0),groups:Object.values(s.particles.reduce((a,p)=>{const N=require('../web/src/positioning/navigation'),key=N.areaAt(N.compile(data,4),p)?.id||'unknown';a[key]??={zone:key,weight:0,scaleSum:0};a[key].weight+=p.weight;a[key].scaleSum+=p.weight*p.scale;return a},{})).map(g=>({...g,meanScale:g.scaleSum/g.weight})),firstUnknown:trace.find(v=>v.after[2]==='unknown'),nonAlignedSteps:trace.filter(v=>v.alignedMass<.5),trace});}
 const end=rows.at(-1),labels=rows.filter(r=>r.kind==='label');
 output.push({file,condition:file.includes('132920')||file.includes('133049')?'normal':'deliberate_phone_angle',direction:first.route_direction,
 recordedFinal:end.final_fusion,recordedSteps:end.final_position.detected_steps,
 fixedStrideDistance:end.final_position.detected_steps*70.804/81,recordedLastLap:labels.at(-1),scenarios});
}
fs.writeFileSync(path.join(root,'indoor/data/analysis/angle-trials-20260908.json'),JSON.stringify(output,null,2)+'\n');
console.log(JSON.stringify(output.map(r=>({file:r.file,condition:r.condition,steps:r.recordedSteps,distance:r.fixedStrideDistance,
 scenarios:r.scenarios.map(s=>({fixed:s.fixed_axis,final:[s.final.x,s.final.y,s.final.zone],firstUnknown:s.firstUnknown,
 nonAligned:s.nonAlignedSteps.map(t=>({step:t.step,t:t.seconds,h:t.heading,dx:t.dx,before:t.before,after:t.after})).slice(0,12)}))})),null,2));
