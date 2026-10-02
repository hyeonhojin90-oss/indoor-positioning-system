// Leave-one-session-out magnetic sequence localization on existing 4F corridor walks.
// Labels are evaluation truth only. No engine/model changes.
const fs=require('fs'),path=require('path');
const Runtime=require('../web/src/positioning/runtime');
const Sequence=require('../web/src/positioning/sequence');
const Nav=require('../web/src/positioning/navigation');
const maps=require('../web/data/navigation/areas-v1.json');
const models=require('../web/data/positioning/motion-models.json');
const root=path.resolve(__dirname,'../..'),raw=path.join(root,'indoor/data/raw/ios'),map=Nav.compile(maps,4);
const mean=a=>a.length?a.reduce((s,v)=>s+v,0)/a.length:null;
const median=a=>{a=[...a].sort((x,y)=>x-y);return a.length?(a[(a.length-1)>>1]+a[a.length>>1])/2:null;};
const metric=x=>Nav.metricDistance(map,x), err=(a,b)=>Math.abs(metric(a)-metric(b));
function distanceN(a,b){
 if(a.length>=5)return Sequence.distance(a,b);
 const normalize=x=>{const m=mean(x),s=Math.sqrt(mean(x.map(v=>(v-m)**2)));return s<.3?null:x.map(v=>(v-m)/s);};
 const x=normalize(a),y=normalize(b);return !x||!y||x.length!==y.length?Infinity:mean(x.map((v,i)=>(v-y[i])**2))/2;
}
function list(){return ['2026-09-05','2026-09-08','2026-09-14'].flatMap(day=>fs.readdirSync(path.join(raw,day)).filter(f=>f.endsWith('.jsonl')).map(f=>path.join(raw,day,f)));}
function labelX(label){const name=String(label?.location||'');if(name.includes('오른쪽 계단'))return map.distanceMetric.mapBreaks[0];if(name.includes('코어'))return 70.804;return label?.map_x;}
function interp(anchors,t){let b=anchors[0],a=anchors.at(-1);for(let i=1;i<anchors.length;i++)if(t<=anchors[i].t){b=anchors[i-1];a=anchors[i];break;}const q=a.t===b.t?0:Math.max(0,Math.min(1,(t-b.t)/(a.t-b.t)));return b.x+(a.x-b.x)*q;}
function parse(file){
 const rows=fs.readFileSync(file,'utf8').trim().split(/\r?\n/).map(JSON.parse),first=rows[0],route=first.label?.route_id;
 if(!['4F_CORE_TO_RIGHT_STAIRS','4F_CORE_TO_RIGHT_STAIRS_REVERSE'].includes(route))return null;
 const startX=first.positioning_config?.start_map_x??(route.endsWith('REVERSE')?map.distanceMetric.mapBreaks[0]:70.804);
 const anchors=[{t:first.wall_time_ms,x:startX},...rows.filter(r=>r.kind==='label'&&Number.isFinite(labelX(r.label))).map(r=>({t:r.wall_time_ms,x:labelX(r.label)}))];
 const runtime=Runtime.create(maps,models,[],{floor:4,x:startX,y:0,platform:'ios',device:first.device_model,initialDirectionSign:first.positioning_config?.initial_direction_sign??-1,sequenceEnabled:false});
 const mags=[],steps=[];let previous=first.wall_time_ms;
 for(const r of rows){const t=r.wall_time_ms;
  if(r.sensor==='heading_degrees')Runtime.heading(runtime,t,r.values[0],r.accuracy);
  if(r.sensor==='magnetic_field_ut')mags.push({t,v:Math.hypot(...r.values.slice(0,3))});
  if(r.kind==='derived_position'){
   Runtime.step(runtime,t,r.acceleration_peak_mps2);const values=mags.filter(x=>x.t>previous&&x.t<=t).map(x=>x.v);previous=t;
   if(values.length)steps.push({t,value:median(values),truthX:interp(anchors,t),pdrX:Runtime.snapshot(runtime,[]).x});
  }
 }
 return {file:path.basename(file),direction:route.endsWith('REVERSE')?'reverse':'forward',steps};
}
const sessions=list().map(parse).filter(Boolean),queries=sessions.filter(s=>!s.file.includes('20260905'));
function queryWindows(steps,n){const out=[];let current=[];
 for(const step of steps){if(current.length&&step.t-current.at(-1).t>3000)current=[];current.push(step);if(current.length===n){out.push(current);current=[];}}
 return out;
}
function trainingWindows(steps,n){const out=[];let start=0;
 for(let end=0;end<steps.length;end++){if(end>0&&steps[end].t-steps[end-1].t>3000)start=end;if(end-start+1>=n&&(end-start-(n-1))%2===0)out.push(steps.slice(end-n+1,end+1));}
 return out;
}
function evaluate(n){const rows=[];
 for(const q of queries)for(const window of queryWindows(q.steps,n)){
  const current=window.at(-1),candidates=[];
  for(const train of sessions)if(train.file!==q.file&&train.direction===q.direction)for(const trainWindow of trainingWindows(train.steps,n)){
   const target=trainWindow.at(-1),distanceFromPdr=err(target.truthX,current.pdrX);if(distanceFromPdr>12)continue;
   const score=distanceN(window.map(x=>x.value),trainWindow.map(x=>x.value));
   if(Number.isFinite(score))candidates.push({score,x:target.truthX,file:train.file});
  }
  candidates.sort((a,b)=>a.score-b.score);const best=candidates[0],alternative=candidates.find(x=>err(x.x,best?.x)>4);
  if(!best)continue;const margin=alternative?alternative.score-best.score:0,accepted=best.score<=.5&&margin>=.08;
  const pdrError=err(current.pdrX,current.truthX),candidateError=err(best.x,current.truthX),blendX=current.pdrX+.25*(best.x-current.pdrX);
  rows.push({file:q.file,direction:q.direction,t:current.t,score:best.score,margin,accepted,pdrError,candidateError,
   localCandidateMedianError:median(candidates.map(c=>err(c.x,current.truthX))),blendError:err(blendX,current.truthX),improved:candidateError<pdrError});
 }
 const accepted=rows.filter(r=>r.accepted);return {windowSteps:n,queries:rows.length,accepted:accepted.length,acceptanceRate:accepted.length/rows.length,
  allBestMedianErrorMeters:median(rows.map(r=>r.candidateError)),allLocalBaselineMedianErrorMeters:median(rows.map(r=>r.localCandidateMedianError)),acceptedMedianCandidateErrorMeters:median(accepted.map(r=>r.candidateError)),
  acceptedMedianPdrErrorMeters:median(accepted.map(r=>r.pdrError)),acceptedMedianBlend25ErrorMeters:median(accepted.map(r=>r.blendError)),
  acceptedCandidateImproved:accepted.filter(r=>r.improved).length,acceptedWithin2m:accepted.filter(r=>r.candidateError<=2).length,
  byDirection:Object.fromEntries(['forward','reverse'].map(d=>{const a=accepted.filter(r=>r.direction===d);return[d,{accepted:a.length,medianCandidateErrorMeters:median(a.map(r=>r.candidateError)),medianPdrErrorMeters:median(a.map(r=>r.pdrError))}]})),
  bySession:Object.fromEntries(queries.map(q=>{const a=accepted.filter(r=>r.file===q.file);return[q.file,{queries:rows.filter(r=>r.file===q.file).length,accepted:a.length,medianCandidateErrorMeters:median(a.map(r=>r.candidateError))}]})),rows};
}
const evaluations=[3,6,8].map(evaluate),report={createdAt:new Date().toISOString(),purpose:'Leave-one-session-out magnetic sequence localization; labels never enter matching.',
 dataset:{sessions:sessions.length,heldOutQueries:queries.length,directions:Object.fromEntries(['forward','reverse'].map(d=>[d,sessions.filter(s=>s.direction===d).length]))},
 method:['Per detected step, median magnetic magnitude since the previous step.','Query windows are disjoint and reset after a gap over 3 seconds; training windows advance by 2 steps.','Train candidates come only from other sessions in the same direction.','Candidates are limited to 12 m around current PDR, because magnetic correction is local support rather than global positioning.','Acceptance uses the existing score <= 0.5 and alternative-location margin >= 0.08 thresholds.','For 3 steps only, the same z-normalized squared distance is used without DTW because the current matcher rejects windows shorter than 5.','A 25% move toward the accepted candidate is a diagnostic thought experiment, not current particle behavior.'],
 evaluations,limitations:['Step truth is linearly interpolated between manually pressed room labels; it is weak timing truth, not surveyed foot position.','The same user/device/building is used across folds.','Multiple overlapping windows from one walk are correlated and must not be read as independent trials.','Thresholds were not retuned on these results.']};
const out=path.join(root,'indoor/data/analysis/detailed-20260918/4f-magnetic-ablation');fs.mkdirSync(out,{recursive:true});fs.writeFileSync(path.join(out,'sequence-cv.json'),JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify({dataset:report.dataset,evaluations:evaluations.map(({rows,...x})=>x)},null,2));
