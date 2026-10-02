// Exploratory scalar calibration; no production model updates.
const fs=require('fs'),path=require('path');
const ids=['133338','133534','133637','133734'];
const sessions=ids.map(id=>{
 const rows=fs.readFileSync(path.join(process.argv[2],`indoor_positioning_ios_20260914_${id}.jsonl`),'utf8').trim().split(/\r?\n/).map(JSON.parse);
 const x=rows[0].positioning_config.start_map_x;
 return {id,points:rows.filter(r=>r.kind==='label'&&r.comparison).map(r=>({label:r.label.location,n:rows.filter(s=>s.kind==='derived_position'&&s.wall_time_ms<=r.wall_time_ms).length,d:Math.abs(r.label.map_x-x)}))};
});
const mean=a=>a.reduce((x,y)=>x+y,0)/a.length;
const folds=sessions.map(test=>{
 const train=sessions.filter(s=>s!==test).flatMap(s=>s.points);
 const stride=train.reduce((s,p)=>s+p.n*p.d,0)/train.reduce((s,p)=>s+p.n*p.n,0);
 return {test:test.id,train:sessions.filter(s=>s!==test).map(s=>s.id),stride,n:test.points.length,fixed:mean(test.points.map(p=>Math.abs(p.n*70.804/81-p.d))),fitted:mean(test.points.map(p=>Math.abs(p.n*stride-p.d)))};
});
const out={note:'Leave-one-session-out scalar least squares on cumulative recorded steps and map lap distances. Motion-only, no particles; weak manual labels, same day/user. Not validated true stride.',folds,meanFixed:mean(folds.map(x=>x.fixed)),meanFitted:mean(folds.map(x=>x.fitted)),sessions};
fs.writeFileSync(path.resolve(__dirname,'../data/analysis/detailed-20260914/stride-scalar-holdout.json'),JSON.stringify(out,null,2));
console.log(JSON.stringify({...out,sessions:undefined},null,2));
