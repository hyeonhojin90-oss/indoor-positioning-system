const fs=require('node:fs'),path=require('node:path'),Module=require('node:module');
const root=path.resolve(__dirname,'../..'),enginePath=path.join(root,'indoor/web/src/positioning/fusion-engine.js');
const old=new Module(enginePath,module);old.filename=enginePath;old.paths=module.paths;
old._compile(fs.readFileSync(path.join(root,'backups/20260908-corridor-branches/fusion-engine.js'),'utf8'),enginePath);
const engines={before:old.exports,after:require(enginePath)};
const data=require('../web/data/navigation/areas-v1.json');
const rows=fs.readFileSync(process.argv[2],'utf8').trim().split(/\r?\n/).map(JSON.parse),out={};
for(const [name,F] of Object.entries(engines)){
 const s=F.create(data,{floor:rows[0].start_floor,x:rows[0].positioning_config.start_map_x,y:0});
 const labels=[];
 for(const row of rows){const t=row.wall_time_ms;
  if(row.sensor==='heading_degrees')F.heading(s,row.values[0],t,row.accuracy);
  if(row.kind==='derived_position')F.step(s,t,row.acceleration_peak_mps2);
  if(row.kind==='label')labels.push({label:row.label.location,...F.snapshot(s)});
 }
 out[name]={version:F.VERSION,labels};
}
out.note='Same recorded heading/steps, no magnetic weighting, labels evaluate only. Not field accuracy.';
fs.writeFileSync(path.join(root,'indoor/data/analysis/corridor-before-after-20260908.json'),JSON.stringify(out,null,2)+'\n');
console.log(JSON.stringify(Object.fromEntries(Object.entries(out).map(([k,v])=>[k,v.labels?.at(-1)||v])),null,2));
