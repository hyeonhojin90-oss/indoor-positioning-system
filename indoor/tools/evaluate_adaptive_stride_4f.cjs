// Analysis-only 4F adaptive-stride replay.
// It never imports or changes the runtime model. Pass the directory that holds
// the four 2026-09-14 13xxxx external raw files as argv[2].
const fs=require('fs'),path=require('path');
const root=path.resolve(__dirname,'../..');
const {createPositionTracker,updatePositionAcceleration}=require('../../app/expo-sensor-collector/positionTracking');
const survey=require('../web/data/maps/floor-04-survey.json');

const distanceMeters=survey.core_center_to_right_end.reference_length_m;
const oldFixedMeters=distanceMeters/81;
const middle=a=>{const b=[...a].sort((x,y)=>x-y),n=b.length;return n%2?b[(n-1)/2]:(b[n/2-1]+b[n/2])/2;};
const mean=a=>a.reduce((s,x)=>s+x,0)/a.length;
const std=(a,m=mean(a))=>Math.sqrt(mean(a.map(x=>(x-m)**2)))||1;
const clamp=(x,lo,hi)=>Math.max(lo,Math.min(hi,x));

function files() {
  const external=process.argv[2];
  if(!external)throw new Error('Usage: node indoor/tools/evaluate_adaptive_stride_4f.cjs <external-jsonl-directory>');
  return [
    ...fs.readdirSync(path.join(root,'indoor/data/raw/ios/2026-09-05')).map(n=>path.join(root,'indoor/data/raw/ios/2026-09-05',n)),
    ...fs.readdirSync(path.join(root,'indoor/data/raw/ios/2026-09-08')).map(n=>path.join(root,'indoor/data/raw/ios/2026-09-08',n)),
    ...['133338','133534','133637','133734'].map(id=>path.join(external,`indoor_positioning_ios_20260914_${id}.jsonl`)),
    ...fs.readdirSync(path.join(root,'indoor/data/raw/ios/2026-09-14')).map(n=>path.join(root,'indoor/data/raw/ios/2026-09-14',n))
  ];
}

function load(file) {
  const rows=fs.readFileSync(file,'utf8').trim().split(/\r?\n/).map(JSON.parse);
  const route=rows[0]?.label?.route_id;
  if(!['4F_CORE_TO_RIGHT_STAIRS','4F_CORE_TO_RIGHT_STAIRS_REVERSE'].includes(route))return null;
  let state=createPositionTracker({floor:4,x:70.804,initialDirectionSign:-1});
  const steps=[];
  for(const row of rows)if(row.sensor==='accelerometer_mps2'){
    const result=updatePositionAcceleration(state,row.wall_time_ms,row.values);state=result.state;
    if(result.detected)steps.push({time:row.wall_time_ms,peak:result.peak});
  }
  return {file:path.basename(file),route,steps,effectiveStride:distanceMeters/steps.length};
}

// Endpoint error is |N*a-L|, so the robust MAE-optimal scalar is the
// weighted median of per-session effective strides, weighted by step count.
function weightedMedian(rows) {
  const ordered=[...rows].sort((a,b)=>a.effectiveStride-b.effectiveStride);
  const total=ordered.reduce((s,r)=>s+r.steps.length,0);let sum=0;
  for(const row of ordered){sum+=row.steps.length;if(sum>=total/2)return row.effectiveStride;}
  return ordered.at(-1).effectiveStride;
}

function windowFeatures(steps,index,width) {
  if(index<width-1)return null;
  const part=steps.slice(index-width+1,index+1);
  const intervals=[];
  for(let i=1;i<part.length;i++)intervals.push(part[i].time-part[i-1].time);
  if(!intervals.length||intervals.some(x=>x<=0))return null;
  return {cadence:1000/middle(intervals),peak:middle(part.map(x=>x.peak))};
}

function solve(matrix,vector) {
  const a=matrix.map((row,i)=>[...row,vector[i]]),n=vector.length;
  for(let col=0;col<n;col++){
    let pivot=col;for(let r=col+1;r<n;r++)if(Math.abs(a[r][col])>Math.abs(a[pivot][col]))pivot=r;
    if(Math.abs(a[pivot][col])<1e-10)return null;
    [a[col],a[pivot]]=[a[pivot],a[col]];const d=a[col][col];
    for(let c=col;c<=n;c++)a[col][c]/=d;
    for(let r=0;r<n;r++)if(r!==col){const f=a[r][col];for(let c=col;c<=n;c++)a[r][c]-=f*a[col][c];}
  }
  return a.map(row=>row[n]);
}

function fit(train,width) {
  const raw=[];
  for(const session of train){
    const rows=[];
    for(let i=0;i<session.steps.length;i++){const f=windowFeatures(session.steps,i,width);if(f)rows.push(f);}
    // Each walking session has equal total influence; its many overlapping
    // rolling windows must not outweigh another session.
    rows.forEach(f=>raw.push({...f,target:session.effectiveStride,weight:1/rows.length}));
  }
  const cadenceMean=raw.reduce((s,r)=>s+r.weight*r.cadence,0)/train.length;
  const peakMean=raw.reduce((s,r)=>s+r.weight*r.peak,0)/train.length;
  const cadenceStd=Math.sqrt(raw.reduce((s,r)=>s+r.weight*(r.cadence-cadenceMean)**2,0)/train.length)||1;
  const peakStd=Math.sqrt(raw.reduce((s,r)=>s+r.weight*(r.peak-peakMean)**2,0)/train.length)||1;
  const xtx=[[0,0,0],[0,0,0],[0,0,0]],xty=[0,0,0];
  for(const r of raw){const x=[1,(r.cadence-cadenceMean)/cadenceStd,(r.peak-peakMean)/peakStd];
    for(let i=0;i<3;i++){xty[i]+=r.weight*x[i]*r.target;for(let j=0;j<3;j++)xtx[i][j]+=r.weight*x[i]*x[j];}
  }
  // Small ridge penalty is fixed before holdout evaluation; it stabilizes two
  // correlated walking features without tuning on the held-out session.
  xtx[1][1]+=0.5;xtx[2][2]+=0.5;
  const coefficients=solve(xtx,xty);if(!coefficients)throw new Error('Singular adaptive-stride fit');
  return {coefficients,cadenceMean,cadenceStd,peakMean,peakStd};
}

function predict(model,feature,base) {
  if(!feature)return base;
  const [a,b,c]=model.coefficients;
  const raw=a+b*(feature.cadence-model.cadenceMean)/model.cadenceStd+c*(feature.peak-model.peakMean)/model.peakStd;
  return clamp(raw,base*.90,base*1.10);
}

function replay(session,base,model,width) {
  let dynamic=base;const applied=[];
  for(let i=0;i<session.steps.length;i++){
    const target=predict(model,windowFeatures(session.steps,i,width),base);
    // First width-1 steps retain the common personal baseline. Later updates
    // are global and smoothed; no particle or map state participates here.
    if(i>=width-1)dynamic=.8*dynamic+.2*target;
    applied.push(dynamic);
  }
  // The sum, not just the last value, is the replayed distance.
  const estimatedMeters=applied.reduce((s,x)=>s+x,0);
  return {estimatedMeters,errorMeters:Math.abs(estimatedMeters-distanceMeters),finalStrideMeters:dynamic,
    meanStrideMeters:mean(applied),minStrideMeters:Math.min(...applied),maxStrideMeters:Math.max(...applied)};
}

const sessions=files().map(load).filter(Boolean);
if(sessions.length!==15)throw new Error(`Expected 15 accepted iPhone 4F corridor sessions, got ${sessions.length}`);
const windows=[3,6,8];
const folds=[];
for(const test of sessions){
  const train=sessions.filter(s=>s!==test),base=weightedMedian(train);
  const fixed={estimatedMeters:base*test.steps.length,errorMeters:Math.abs(base*test.steps.length-distanceMeters),finalStrideMeters:base};
  const result={file:test.file,route:test.route,steps:test.steps.length,effectiveStrideMeters:test.effectiveStride,baseStrideMeters:base,
    currentFixedErrorMeters:Math.abs(oldFixedMeters*test.steps.length-distanceMeters),fixedHoldoutErrorMeters:fixed.errorMeters,windows:{}};
  for(const width of windows){const model=fit(train,width);result.windows[width]={...replay(test,base,model,width),model};}
  folds.push(result);
}
const summary={};
for(const width of windows){
  const adaptive=folds.map(r=>r.windows[width].errorMeters),fixed=folds.map(r=>r.fixedHoldoutErrorMeters);
  summary[width]={adaptiveEndpointMAEMeters:mean(adaptive),fixedHoldoutEndpointMAEMeters:mean(fixed),changeMeters:mean(adaptive)-mean(fixed),betterSessions:adaptive.filter((x,i)=>x<fixed[i]).length,worseSessions:adaptive.filter((x,i)=>x>fixed[i]).length};
}
// A second split keeps the four newly added 17xxxx walks entirely unseen.
// It is closer to the decision we would make before deploying to the phone.
const fresh=sessions.filter(s=>/_(170738|170901|171021|171142)\.jsonl$/.test(s.file));
const earlier=sessions.filter(s=>!fresh.includes(s));
const chronologicalHoldout={trainingSessions:earlier.map(s=>s.file),testSessions:fresh.map(s=>s.file),baseStrideMeters:weightedMedian(earlier),windows:{}};
const chronologicalFixed=chronologicalHoldout.baseStrideMeters;
for(const width of windows){
  const model=fit(earlier,width),adaptive=fresh.map(s=>replay(s,chronologicalFixed,model,width));
  chronologicalHoldout.windows[width]={fixedEndpointMAEMeters:mean(fresh.map(s=>Math.abs(s.steps.length*chronologicalFixed-distanceMeters))),
    adaptiveEndpointMAEMeters:mean(adaptive.map(r=>r.errorMeters)),changeMeters:mean(adaptive.map(r=>r.errorMeters))-mean(fresh.map(s=>Math.abs(s.steps.length*chronologicalFixed-distanceMeters))),
    tests:fresh.map((s,i)=>({file:s.file,fixedErrorMeters:Math.abs(s.steps.length*chronologicalFixed-distanceMeters),...adaptive[i]})),model};
}
const out={
  purpose:'Analysis-only: leave-one-session-out replay of a single shared adaptive stride. It does not change the engine or learned model.',
  distanceMeters,oldFixedMeters,method:{
    base:'Training sessions only: step-count weighted median of total-distance/detected-steps.',
    adaptive:'After W detected steps, ridge regression uses rolling median cadence and acceleration peak. Prediction is clamped to base ±10% then updated by 0.8 previous + 0.2 prediction. All steps share one value; particles and map state are excluded.',
    validation:'One full session held out at a time. Endpoint labels only; room-front labels are not physical-distance truth.'
  },
  sessions:sessions.map(s=>({file:s.file,route:s.route,steps:s.steps.length,effectiveStrideMeters:s.effectiveStride})),
  summary,chronologicalHoldout,folds
};
const output=path.join(root,'indoor/data/analysis/detailed-20260914/adaptive-stride-exploratory-holdout.json');
fs.writeFileSync(output,JSON.stringify(out,null,2)+'\n');
console.log(JSON.stringify({sessions:sessions.length,distanceMeters,oldFixedMeters,summary},null,2));
