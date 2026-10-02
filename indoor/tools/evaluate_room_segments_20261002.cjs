// Offline feasibility study. Labels are evaluation anchors, never metric door truth.
// Does not modify production models, the map, Android, or the saved raw recordings.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const Runtime = require('../web/src/positioning/runtime');
const Sequence = require('../web/src/positioning/sequence');
const data = require('../web/data/navigation/areas-v1.json');
const ROOT = path.resolve(__dirname, '../..');
const OUT = path.join(ROOT, 'indoor/data/analysis/room-segments-20261002');
fs.mkdirSync(OUT, {recursive:true});
const mean = a => a.length ? a.reduce((s,v)=>s+v,0)/a.length : null;
const quantile = (a,q) => {a=a.filter(Number.isFinite).sort((x,y)=>x-y);if(!a.length)return null;const i=(a.length-1)*q;return a[Math.floor(i)]+(a[Math.ceil(i)]-a[Math.floor(i)])*(i%1);};
const median = a => quantile(a,.5);
const sd = a => a.length>1 ? Math.sqrt(mean(a.map(v=>(v-mean(a))**2))) : 0;
const rel = f => path.relative(ROOT,f).replaceAll('\\','/');
const room = r => r.label?.location?.match(/\b42\d{2}\b/)?.[0] || null;
const summarize = a => ({n:a.length,mean:mean(a),median:median(a),min:a.length?Math.min(...a):null,max:a.length?Math.max(...a):null,sd:sd(a)});
function walk(p){return fs.readdirSync(p,{withFileTypes:true}).flatMap(e=>e.isDirectory()?walk(path.join(p,e.name)):e.name.endsWith('.jsonl')?[path.join(p,e.name)]:[]);}
function interpolate(a,n=16){if(!a.length)return [];return Array.from({length:n},(_,i)=>{const x=i*(a.length-1)/(n-1),j=Math.floor(x);return a[j]+((a[j+1]??a[j])-a[j])*(x-j);});}
function detect(events,start,end){
  const r=Runtime.create(data,{},[],{floor:4,x:70.804,y:0,count:1,magneticZoneEnabled:false,sequenceEnabled:false});
  return events.filter(e=>e.sensor==='accelerometer_mps2'&&e.time>=start&&e.time<=end&&Runtime.acceleration(r,e.time,e.values)).map(e=>e.time);
}
const manifest=[],sessions=[],seen=new Set();
for(const file of walk(path.join(ROOT,'indoor/data/raw'))){
  const fd=fs.openSync(file,'r'),buffer=Buffer.alloc(20000),n=fs.readSync(fd,buffer,0,buffer.length,0);fs.closeSync(fd);
  let first;try{first=JSON.parse(buffer.toString('utf8',0,n).split(/\r?\n/)[0]);}catch{continue;}
  const route=first.label?.route_id;
  if(!['4F_CORE_TO_RIGHT_STAIRS','4F_CORE_TO_RIGHT_STAIRS_REVERSE'].includes(route))continue;
  const text=fs.readFileSync(file,'utf8'),sha=crypto.createHash('sha256').update(text).digest('hex');
  const m={file:rel(file),sha256:sha,route,platform:first.platform||'android',device:first.device||'ios_unknown'};manifest.push(m);
  if(seen.has(sha)){m.excluded='duplicate_hash';continue;}seen.add(sha);
  let rows;try{rows=text.trim().split(/\r?\n/).map(JSON.parse);}catch{m.excluded='parse_error';continue;}
  const labels=[first,...rows.filter(r=>r.kind==='label')].map(r=>({time:r.wall_time_ms,room:room(r),location:r.label?.location,rawSteps:r.steps_since_start??0}));
  const roomLabels=labels.filter(l=>l.room),end=labels.at(-1).time;
  if(rows.at(-1).kind!=='session_end'||roomLabels.length<8){m.excluded='incomplete_or_less_than_8_room_labels';continue;}
  const reverse=route.endsWith('_REVERSE');
  if(!(reverse?labels.at(-1).location.includes('코어'):labels.at(-1).location.includes('오른쪽 계단'))){m.excluded='endpoint_label_mismatch';continue;}
  const samples=rows.filter(r=>r.kind==='sample'&&Array.isArray(r.values));
  // Android callback wall times can be batched. Recover the common monotonic
  // sensor clock from the fifth percentile of callback-wall minus sensor time.
  // No query labels or magnetic features enter this clock estimate.
  const offsets=samples.filter(r=>Number.isFinite(r.sensor_timestamp_ns)).map(r=>r.wall_time_ms-r.sensor_timestamp_ns/1e6);
  const offset=quantile(offsets,.05);
  const events=samples.map(r=>({...r,time:Number.isFinite(r.sensor_wall_time_ms)?r.sensor_wall_time_ms:Number.isFinite(r.sensor_timestamp_ns)&&offset!==null?r.sensor_timestamp_ns/1e6+offset:r.wall_time_ms})).sort((a,b)=>a.time-b.time);
  const callbacks=samples.map(r=>({...r,time:Number.isFinite(r.sensor_wall_time_ms)?r.sensor_wall_time_ms:r.wall_time_ms}));
  const stepTimes=detect(events,first.wall_time_ms,end),callbackSteps=detect(callbacks,first.wall_time_ms,end);
  let gravity=null,gTime=null;
  const magnetic=[];
  for(const e of events){
    if(e.sensor==='accelerometer_mps2'){
      if(gravity===null)gravity=e.values.slice(0,3);
      else {const dt=Math.max(.001,Math.min(.2,(e.time-gTime)/1000)),a=1-Math.exp(-dt);gravity=gravity.map((v,i)=>v+a*(e.values[i]-v));}gTime=e.time;
    } else if(e.sensor==='magnetic_field_ut'){
      const norm=Math.hypot(...e.values.slice(0,3)),gNorm=gravity?Math.hypot(...gravity):0;
      const mv=gNorm>1&&e.time-gTime<=250?e.values.slice(0,3).reduce((s,v,i)=>s+v*gravity[i]/gNorm,0):null;
      if(e.time>=first.wall_time_ms&&e.time<=end)magnetic.push({time:e.time,norm,mv});
    }
  }
  // One median per detected step; thousands of callback samples are not counted
  // as independent walking observations.
  let cursor=0,previous=first.wall_time_ms;
  const points=stepTimes.map((time,index)=>{const bin=[];while(cursor<magnetic.length&&magnetic[cursor].time<=time){if(magnetic[cursor].time>previous)bin.push(magnetic[cursor]);cursor++;}previous=time;return {time,ordinal:index+1,norm:median(bin.map(p=>p.norm)),mv:median(bin.map(p=>p.mv)),samples:bin.length};});
  for(const l of labels){l.steps=stepTimes.filter(t=>t<=l.time).length;l.callbackSteps=callbackSteps.filter(t=>t<=l.time).length;}
  const id=path.basename(file,'.jsonl'),date=new Date(first.wall_time_ms+9*3600000).toISOString().slice(0,10);
  const segments=[];
  for(let i=0;i<labels.length-1;i++){
    const a=labels[i],b=labels[i+1];if(!a.room||!b.room||Math.abs(Number(a.room)-Number(b.room))!==1)continue;
    const p=points.filter(p=>p.time>a.time&&p.time<=b.time),mag=magnetic.filter(p=>p.time>a.time&&p.time<=b.time);
    const norm=p.map(p=>p.norm).filter(Number.isFinite),mv=p.map(p=>p.mv).filter(Number.isFinite);
    if(p.length<2||norm.length<2){m.skippedSegments=(m.skippedSegments||[]).concat(`${a.room}->${b.room}:insufficient_steps_or_magnetic`);continue;}
    segments.push({session:id,date,platform:m.platform,direction:reverse?'reverse':'forward',from:a.room,to:b.room,pair:[a.room,b.room].sort().join('~'),
      startTime:a.time,endTime:b.time,durationS:(b.time-a.time)/1000,steps:b.steps-a.steps,callbackSteps:b.callbackSteps-a.callbackSteps,rawCounterSteps:b.rawSteps-a.rawSteps,
      tapTimingSensitivityHalfSecond:{min:stepTimes.filter(t=>t>a.time+500&&t<=b.time-500).length,max:stepTimes.filter(t=>t>a.time-500&&t<=b.time+500).length},
      magneticSamples:mag.length,mvCoverage:mv.length/p.length,magnetic:summarize(norm),vertical:summarize(mv),startMag:median(norm.slice(0,2)),endMag:median(norm.slice(-2)),deltaMag:median(norm.slice(-2))-median(norm.slice(0,2)),
      canonicalNorm:interpolate(reverse?[...norm].reverse():norm),canonicalMv:mv.length===p.length?interpolate(reverse?[...mv].reverse():mv):[],points:p});
  }
  m.included=true;m.steps=stepTimes.length;m.callbackSteps=callbackSteps.length;m.segments=segments.length;
  m.clock={method:'sensor_wall_else_monotonic_offset_p05_else_callback',callbackLagMs:{median:median(offsets.map(v=>v-offset)),p95:quantile(offsets.map(v=>v-offset),.95),max:Math.max(...offsets.map(v=>v-offset))},offsetMs:offset};
  sessions.push({...m,id,date,direction:reverse?'reverse':'forward',labels,points,magnetic,segments});
}
function rms(a,b,center=false){if(a.length!==b.length||a.length<2)return null;const am=center?mean(a):0,bm=center?mean(b):0;return Math.sqrt(mean(a.map((v,i)=>((v-am)-(b[i]-bm))**2)));}
const methods=['steps','mag_shape','mag_shape_mv','mag_norm','mag_norm_mv','mag_shape_steps','mag_shape_mv_steps','mag_norm_steps','mag_norm_mv_steps','mag_dtw','mag_dtw_mv','mag_dtw_steps','mag_dtw_mv_steps'];
function score(q,r,method){
  const step=((q.steps-r.steps)/1.5)**2;
  if(method.startsWith('mag_dtw')){
    const norm=Sequence.distance(q.canonicalNorm,r.canonicalNorm)/.5;
    const vertical=q.canonicalMv.length&&r.canonicalMv.length?Sequence.distance(q.canonicalMv,r.canonicalMv)/.5:Infinity;
    const magnetic=method.includes('_mv')&&Number.isFinite(vertical)?.5*(norm+vertical):norm;
    return method.endsWith('_steps')?.7*magnetic+.3*step:magnetic;
  }
  const norm=(rms(q.canonicalNorm,r.canonicalNorm)/5)**2;
  const mv=rms(q.canonicalMv,r.canonicalMv),both=mv===null?norm:.5*norm+.5*(mv/8)**2;
  const shape=(rms(q.canonicalNorm,r.canonicalNorm,true)/3)**2;
  const mvShape=rms(q.canonicalMv,r.canonicalMv,true),bothShape=mvShape===null?shape:.5*shape+.5*(mvShape/5)**2;
  if(method==='steps')return step;
  if(method==='mag_shape')return shape;
  if(method==='mag_shape_mv')return bothShape;
  if(method==='mag_norm')return norm;
  if(method==='mag_norm_mv')return both;
  return .7*({mag_norm_mv_steps:both,mag_norm_steps:norm,mag_shape_steps:shape,mag_shape_mv_steps:bothShape}[method])+.3*step;
}
const evaluations=[];
for(const platform of ['android','ios'])for(const fold of ['session','day'])for(const directionPolicy of ['same','both']){
  const all=sessions.filter(s=>s.platform===platform).flatMap(s=>s.segments);
  for(const method of methods){
    const predictions=[];
    for(const q of all){
      const train=all.filter(r=>r.session!==q.session&&(fold!=='day'||r.date!==q.date)&&(directionPolicy==='both'||r.direction===q.direction));
      const grouped=new Map();for(const r of train){if(!grouped.has(r.pair))grouped.set(r.pair,[]);grouped.get(r.pair).push(r);}
      if(!grouped.has(q.pair)||grouped.size<2)continue;
      const ranked=[...grouped].map(([pair,refs])=>({pair,score:median(refs.map(r=>score(q,r,method))),references:refs.length})).filter(r=>Number.isFinite(r.score)).sort((a,b)=>a.score-b.score||a.pair.localeCompare(b.pair));
      if(!ranked.length){predictions.push({session:q.session,pair:q.pair,from:q.from,to:q.to,predicted:null,correct:false,tied:[],credit:0,reason:'no_finite_pattern_score',trainingSessions:[...new Set(train.map(r=>r.session))]});continue;}
      const tied=ranked.filter(r=>Math.abs(r.score-ranked[0].score)<1e-10).map(r=>r.pair);
      predictions.push({session:q.session,pair:q.pair,from:q.from,to:q.to,steps:q.steps,predicted:ranked[0].pair,correct:ranked[0].pair===q.pair,tied,credit:tied.includes(q.pair)?1/tied.length:0,score:ranked[0].score,margin:ranked[1]?ranked[1].score-ranked[0].score:null,alternatives:ranked.slice(0,3),trainingSessions:[...new Set(train.map(r=>r.session))]});
    }
    const target=predictions.filter(p=>p.pair==='4212~4213');
    const sum=a=>a.reduce((s,p)=>s+p.credit,0);
    evaluations.push({platform,fold,directionPolicy,method,total:predictions.length,correct:predictions.filter(p=>p.correct).length,accuracy:predictions.length?sum(predictions)/predictions.length:null,
      target:{total:target.length,correct:target.filter(p=>p.correct).length,tieAdjustedCorrect:sum(target),accuracy:target.length?sum(target)/target.length:null},predictions});
  }
}
// Longer context: join two or three consecutive lap intervals. Boundaries are
// still given, so this measures pattern distinctiveness, not a live locator.
const contextEvaluations=[];
for(const width of [2,3])for(const fold of ['session','day']){
  const all=[];
  for(const s of sessions.filter(s=>s.platform==='android'))for(let i=0;i+width<=s.segments.length;i++){
    const part=s.segments.slice(i,i+width);if(part.some((p,j)=>j&&p.startTime!==part[j-1].endTime))continue;
    const points=part.flatMap(p=>p.points),norm=points.map(p=>p.norm).filter(Number.isFinite),mv=points.map(p=>p.mv).filter(Number.isFinite),reverse=s.direction==='reverse';
    all.push({session:s.id,date:s.date,direction:s.direction,from:part[0].from,to:part.at(-1).to,pair:[part[0].from,part.at(-1).to].sort().join('~'),steps:part.reduce((sum,p)=>sum+p.steps,0),
      canonicalNorm:interpolate(reverse?[...norm].reverse():norm),canonicalMv:mv.length===points.length?interpolate(reverse?[...mv].reverse():mv):[]});
  }
  for(const method of methods){
    const predictions=[];
    for(const q of all){
      const train=all.filter(r=>r.session!==q.session&&r.direction===q.direction&&(fold!=='day'||r.date!==q.date)),grouped=new Map();
      for(const r of train){if(!grouped.has(r.pair))grouped.set(r.pair,[]);grouped.get(r.pair).push(r);}
      if(!grouped.has(q.pair)||grouped.size<2)continue;
      const ranked=[...grouped].map(([pair,refs])=>({pair,score:median(refs.map(r=>score(q,r,method)))})).filter(r=>Number.isFinite(r.score)).sort((a,b)=>a.score-b.score||a.pair.localeCompare(b.pair)),tied=ranked.length?ranked.filter(r=>Math.abs(r.score-ranked[0].score)<1e-10).map(r=>r.pair):[];
      predictions.push({session:q.session,pair:q.pair,predicted:ranked[0]?.pair??null,correct:ranked[0]?.pair===q.pair,credit:tied.includes(q.pair)?1/tied.length:0,trainingSessions:[...new Set(train.map(r=>r.session))]});
    }
    contextEvaluations.push({width,fold,method,total:predictions.length,correct:predictions.filter(p=>p.correct).length,accuracy:mean(predictions.map(p=>p.credit)),predictions});
  }
}
// Causal known-start test: only the first lap (4213 forward, 4212 reverse)
// starts tracking. The target lap and following lap are read only for scoring.
// Reference coordinates are room intervals, not metres or diagram ratios.
function stretch(source,startRoom){
  const idx=source.labels.findIndex(l=>l.room===startRoom),labels=source.labels.slice(idx,idx+3);
  if(idx<0||labels.length<3)return null;
  const pts=source.points.filter(p=>p.time>labels[0].time&&p.time<=labels[2].time);
  if(labels[1].steps-labels[0].steps<2||labels[2].steps-labels[1].steps<2)return null;
  return {session:source.id,date:source.date,n1:labels[1].steps-labels[0].steps,n2:labels[2].steps-labels[1].steps,labels,points:pts.map(p=>({...p,progress:p.ordinal<=labels[1].steps?(p.ordinal-labels[0].steps)/(labels[1].steps-labels[0].steps):1+(p.ordinal-labels[1].steps)/(labels[2].steps-labels[1].steps)}))};
}
function valueAt(points,x,key){const finite=points.filter(p=>Number.isFinite(p[key]));if(!finite.length)return null;const a=[...finite].reverse().find(p=>p.progress<=x)||finite[0],b=finite.find(p=>p.progress>=x)||finite.at(-1);return b.progress>a.progress?a[key]+(b[key]-a[key])*(x-a.progress)/(b.progress-a.progress):a[key];}
const arrivals=[];
const arrivalMethods=['steps','mag_norm','mag_norm_mv','mag_norm_steps','mag_norm_mv_steps','mag_relative_steps','mag_relative_mv_steps','mag_dtw_steps','mag_dtw_mv_steps'];
for(const platform of ['android','ios'])for(const fold of ['session','day'])for(const s of sessions.filter(s=>s.platform===platform)){
  const startRoom=s.direction==='forward'?'4213':'4212',q=stretch(s,startRoom);if(!q)continue;
  const refs=sessions.filter(r=>r.platform===platform&&r.direction===s.direction&&r.id!==s.id&&(fold!=='day'||r.date!==s.date)).map(r=>stretch(r,startRoom)).filter(Boolean);
  if(!refs.length)continue;
  const n1=median(refs.map(r=>r.n1)),n2=median(refs.map(r=>r.n2)),xs=Array.from({length:81},(_,i)=>i/40);
  const makeGrid=relative=>xs.map(x=>Object.fromEntries(['norm','mv'].map(key=>{const v=refs.map(r=>{const value=valueAt(r.points,x,key),origin=relative?valueAt(r.points,0,key):0;return value===null||origin===null?null:value-origin;}).filter(Number.isFinite);return [key,{mean:mean(v),variance:sd(v)**2}];})));
  const absoluteGrid=makeGrid(false),relativeGrid=makeGrid(true);
  for(const method of arrivalMethods){
    const relative=method.includes('relative'),grid=relative?relativeGrid:absoluteGrid;
    let weights=xs.map((_,i)=>i===0?1:0),arrival=null,history=[],consecutive=0;
    for(let i=0;i<q.points.length;i++){
      const p=q.points[i];let estimate;
      const magneticCost=j=>{
        if(method.includes('dtw')){
          const window=q.points.slice(Math.max(0,i-7),i+1);if(window.length<5)return {sum:0,n:0};
          const end=xs[j],span=(window.length-1)/(end<1?n1:n2),start=Math.max(0,end-span);
          const costs=refs.map(ref=>{
            const positions=window.map((_,k)=>start+(end-start)*k/(window.length-1));
            const norm=Sequence.distance(window.map(v=>v.norm),positions.map(x=>valueAt(ref.points,x,'norm')));
            const mv=method.includes('mv')?Sequence.distance(window.map(v=>v.mv),positions.map(x=>valueAt(ref.points,x,'mv'))):Infinity;
            return Number.isFinite(norm)&&Number.isFinite(mv)?(norm+mv)/2:norm;
          }).filter(Number.isFinite);
          return {sum:costs.length?Math.min(20,median(costs)/.5):20,n:1};
        }
        return ['norm',...(method.includes('mv')?['mv']:[])].reduce((acc,key)=>{const model=grid[j][key],value=relative?p[key]-q.points[0][key]:p[key];if(!Number.isFinite(value)||model.mean===null)return acc;const variance=(key==='norm'?25:64)+model.variance;return {sum:acc.sum+(value-model.mean)**2/variance,n:acc.n+1};},{sum:0,n:0});
      };
      if(method==='steps')estimate=(i+1)/n1;
      else if(!method.endsWith('steps')){
        let best=Infinity,bestIndex=0;for(let j=0;j<xs.length;j++){const c=magneticCost(j),v=c.n?c.sum/c.n:Infinity;if(v<best){best=v;bestIndex=j;}}estimate=xs[bestIndex];
      }else{
        const predicted=xs.map(()=>0);
        for(let j=0;j<xs.length;j++)if(weights[j]>1e-9){const expected=Math.min(2,xs[j]+1/(xs[j]<1?n1:n2));let total=0;const local=[];for(let k=Math.max(0,Math.floor((expected-.24)*40));k<=Math.min(80,Math.ceil((expected+.24)*40));k++){const v=Math.exp(-.5*((xs[k]-expected)/.08)**2);local.push([k,v]);total+=v;}for(const [k,v] of local)predicted[k]+=weights[j]*v/total;}
        weights=predicted.map((v,j)=>{const c=magneticCost(j);return v*Math.exp(-.5*(c.n?c.sum/c.n:0));});const total=weights.reduce((a,b)=>a+b,0);weights=weights.map(v=>total?v/total:1/weights.length);
        let cumulative=0;estimate=2;for(let j=0;j<xs.length;j++){cumulative+=weights[j];if(cumulative>=.5){estimate=xs[j];break;}}
      }
      consecutive=estimate>=1?consecutive+1:0;if(arrival===null&&consecutive>=2)arrival=i; // first crossing step, confirmed on next observation
      history.push({step:i+1,progress:estimate,norm:p.norm,mv:p.mv});
    }
    arrivals.push({platform,fold,session:s.id,date:s.date,direction:s.direction,method,startRoom,target:s.direction==='forward'?'4212':'4213',references:refs.length,referenceSessions:refs.map(r=>r.session),
      actualSteps:q.n1,predictedSteps:arrival,signedStepError:arrival===null?null:arrival-q.n1,absoluteStepError:arrival===null?null:Math.abs(arrival-q.n1),history});
  }
}
const arrivalSummary=[];
for(const platform of ['android','ios'])for(const fold of ['session','day'])for(const method of arrivalMethods){
  const a=arrivals.filter(r=>r.platform===platform&&r.fold===fold&&r.method===method),valid=a.filter(r=>r.absoluteStepError!==null);
  arrivalSummary.push({platform,fold,method,total:a.length,detected:valid.length,missedBeforeNextLap:a.length-valid.length,maeSteps:mean(valid.map(r=>r.absoluteStepError)),maxErrorSteps:valid.length?Math.max(...valid.map(r=>r.absoluteStepError)):null,meanSignedErrorSteps:mean(valid.map(r=>r.signedStepError))});
}
const targets=sessions.flatMap(s=>s.segments.filter(r=>r.pair==='4212~4213').map(r=>({...r,file:s.file})));
const result={version:'room-segments-feasibility-v1',generatedAt:new Date().toISOString(),analysisCodeSha256:crypto.createHash('sha256').update(fs.readFileSync(__filename)).digest('hex'),runtimeCodeSha256:crypto.createHash('sha256').update(fs.readFileSync(path.join(ROOT,'indoor/web/src/positioning/runtime.js'))).digest('hex'),manifest,
  protocol:{labels:'manual lap events, uncertain tap delay and front-of-door position; no independent surveyed door distance',units:'microtesla, seconds, redetected steps, room intervals; no metre accuracy claim',clock:'monotonic sensor clock with file-level p05 wall offset; callback-clock sensitivity also saved',training:'same platform; held-out session and held-out date; same and both travel directions',segmentTest:'optimistic boundary-known classification of nine adjacent-room pairs, not live room recognition',arrivalTest:'known first room only; subsequent target labels only score output; two consecutive observations confirm crossing; no yaw, AP, BLE or production correction'},
  targets,stepSummary:['android','ios'].map(platform=>({platform,forward:summarize(targets.filter(r=>r.platform===platform&&r.direction==='forward').map(r=>r.steps)),reverse:summarize(targets.filter(r=>r.platform===platform&&r.direction==='reverse').map(r=>r.steps))})),
  evaluations,contextEvaluations,arrivalSummary,arrivals,sessions:sessions.map(({magnetic,...s})=>s)};
fs.writeFileSync(path.join(OUT,'results.json'),JSON.stringify(result,null,2)+'\n');
fs.writeFileSync(path.join(OUT,'target-segments.csv'),'session,platform,direction,seconds,steps,callback_steps,raw_counter_steps,mag_start_uT,mag_end_uT,mag_delta_uT,mv_mean_uT\n'+targets.map(r=>[r.session,r.platform,r.direction,r.durationS,r.steps,r.callbackSteps,r.rawCounterSteps,r.startMag,r.endMag,r.deltaMag,r.vertical.mean].join(',')).join('\n')+'\n');
console.log(JSON.stringify({included:sessions.length,excluded:manifest.filter(m=>!m.included),stepSummary:result.stepSummary,targets:targets.map(({points,canonicalNorm,canonicalMv,...r})=>r),classification:evaluations.filter(e=>e.directionPolicy==='same').map(({predictions,...e})=>e),arrivalSummary},null,2));
