// Analysis-only comparison of fixed stride, constant Weinberg and cadence-
// adaptive Weinberg on complete Galaxy 4F right-corridor walks.
// No fitted coefficient is imported by the production runtime.
const fs=require('node:fs');
const path=require('node:path');
const Nav=require('../web/src/positioning/navigation');
const navigation=require('../web/data/navigation/areas-v1.json');

const ROOT=path.resolve(__dirname,'../..');
const LEFT=process.argv.includes('--left');
const COMBINED=process.argv.includes('--combined');
const INPUTS=[
  'indoor/data/raw/android/2026-09-19/kakao-pull-4f',
  'indoor/data/raw/android/2026-09-22/latest-four',
  'indoor/data/raw/android/2026-09-22/retest-2027',
  ...(LEFT||COMBINED?['indoor/data/raw/android/2026-09-22/post-grid-four']:[]),
];
const ROUTES=new Set(LEFT?['4F_CORE_TO_LEFT_STAIRS','4F_CORE_TO_LEFT_STAIRS_REVERSE']:['4F_CORE_TO_RIGHT_STAIRS','4F_CORE_TO_RIGHT_STAIRS_REVERSE']);
if(COMBINED)for(const r of ['4F_CORE_TO_LEFT_STAIRS','4F_CORE_TO_LEFT_STAIRS_REVERSE'])ROUTES.add(r);
const map=Nav.compile(navigation,4);
const DISTANCE=Math.abs(Nav.metricDistance(map,70.804)-Nav.metricDistance(map,LEFT?map.distanceMetric.mapBreaks.at(-1):map.distanceMetric.mapBreaks[0]));
const FIXED=Math.abs(Nav.metricDistance(map,70.804)-Nav.metricDistance(map,map.distanceMetric.mapBreaks[0]))/81;
const mean=a=>a.reduce((s,v)=>s+v,0)/a.length;
const median=a=>{const b=[...a].sort((x,y)=>x-y),n=b.length;return n?b.length%2?b[(n-1)/2]:(b[n/2-1]+b[n/2])/2:null;};
const clamp=(x,lo,hi)=>Math.max(lo,Math.min(hi,x));

function detect(rows,endTime){
  let gravity=null,lastTime=null,previous=0,rising=false,peak=0,peakTime=0,lastStep=-Infinity,valley=Infinity;
  const steps=[];
  for(const row of rows){
    if(row.sensor!=='accelerometer_mps2')continue;
    const time=Number.isFinite(row.sensor_wall_time_ms)?row.sensor_wall_time_ms:row.wall_time_ms;
    if(!Number.isFinite(time)||time>endTime)continue;
    const value=Math.hypot(...row.values.slice(0,3));
    if(!Number.isFinite(value))continue;
    if(gravity===null){gravity=value;lastTime=time;continue;}
    const dt=Math.max(.001,Math.min(.1,(time-lastTime)/1000));lastTime=time;gravity+=dt/.8*(value-gravity);
    const dynamic=value-gravity;valley=Math.min(valley,dynamic);
    if(dynamic>previous){if(!rising||dynamic>peak){peak=dynamic;peakTime=time;}rising=true;}
    else if(rising){
      if(peak>=1&&peakTime-lastStep>=280){
        const amplitude=Math.max(.01,peak-valley);
        steps.push({time:peakTime,q:amplitude**.25,peak,valley});lastStep=peakTime;valley=dynamic;
      }
      rising=false;
    }
    previous=dynamic;
  }
  for(let i=0;i<steps.length;i++)steps[i].frequency=i?1000/(steps[i].time-steps[i-1].time):null;
  return steps.filter(s=>Number.isFinite(s.q)&&s.q>0&&(s.frequency===null||s.frequency>0));
}

function load(file){
  const rows=fs.readFileSync(file,'utf8').trim().split(/\r?\n/).map(JSON.parse),route=rows[0]?.label?.route_id;
  if(!ROUTES.has(route))return null;
  const labels=rows.filter(r=>r.kind==='label'),last=labels.at(-1);
  const complete=labels.length>=10&&((route.includes('LEFT')?/왼쪽 계단 입구/:/오른쪽 계단 입구/).test(last?.label?.location||'')||/코어복도 출구 중앙점/.test(last?.label?.location||''));
  if(!complete||rows.at(-1)?.kind!=='session_end')return null;
  const steps=detect(rows,last.wall_time_ms);
  const distance=Math.abs(Nav.metricDistance(map,70.804)-Nav.metricDistance(map,route.includes('LEFT')?map.distanceMetric.mapBreaks.at(-1):map.distanceMetric.mapBreaks[0]));
  return {file:path.relative(ROOT,file).replaceAll('\\','/'),route,steps,distance};
}

function solve(matrix,vector){
  const a=matrix.map((r,i)=>[...r,vector[i]]),n=vector.length;
  for(let c=0;c<n;c++){
    let p=c;for(let r=c+1;r<n;r++)if(Math.abs(a[r][c])>Math.abs(a[p][c]))p=r;
    if(Math.abs(a[p][c])<1e-10)return null;
    [a[c],a[p]]=[a[p],a[c]];const d=a[c][c];for(let j=c;j<=n;j++)a[c][j]/=d;
    for(let r=0;r<n;r++)if(r!==c){const f=a[r][c];for(let j=c;j<=n;j++)a[r][j]-=f*a[c][j];}
  }
  return a.map(r=>r[n]);
}

function features(session,degree,defaultF){
  const sums=Array(degree+1).fill(0);
  for(const step of session.steps){const f=step.frequency??defaultF;for(let d=0;d<=degree;d++)sums[d]+=step.q*f**d;}
  return sums;
}
function fit(train,degree){
  const defaultF=median(train.flatMap(s=>s.steps.map(x=>x.frequency).filter(Number.isFinite)));
  const xs=train.map(s=>features(s,degree,defaultF)),n=degree+1,xtx=Array.from({length:n},()=>Array(n).fill(0)),xty=Array(n).fill(0);
  for(let row=0;row<xs.length;row++){const x=xs[row];for(let i=0;i<n;i++){xty[i]+=x[i]*train[row].distance;for(let j=0;j<n;j++)xtx[i][j]+=x[i]*x[j];}}
  // A small fixed ridge on cadence terms limits unstable coefficients in this small dataset.
  for(let i=1;i<n;i++)xtx[i][i]+=1e-3;
  return {degree,defaultF,coefficients:solve(xtx,xty)};
}
function predict(session,model){
  const raw=session.steps.map(s=>{const f=s.frequency??model.defaultF,k=model.coefficients.reduce((v,c,i)=>v+c*f**i,0);return k*s.q;});
  const bounded=raw.map(v=>clamp(v,FIXED*.65,FIXED*1.35));
  const distance=bounded.reduce((a,b)=>a+b,0);
  return {distance,error:Math.abs(distance-session.distance),meanStride:mean(bounded),minStride:Math.min(...bounded),maxStride:Math.max(...bounded)};
}

const sessions=INPUTS.flatMap(dir=>fs.readdirSync(path.join(ROOT,dir)).filter(n=>n.endsWith('.jsonl')).map(n=>load(path.join(ROOT,dir,n)))).filter(Boolean);
if(sessions.length<5)throw new Error(`Need at least five complete walks, got ${sessions.length}`);
const folds=sessions.map(test=>{
  const train=sessions.filter(s=>s!==test),models={constant:fit(train,0),linear:fit(train,1),quadratic:fit(train,2)};
  return {file:test.file,route:test.route,distanceM:test.distance,steps:test.steps.length,fixedError:Math.abs(test.steps.length*FIXED-test.distance),
    constant:{...predict(test,models.constant),model:models.constant},linear:{...predict(test,models.linear),model:models.linear},quadratic:{...predict(test,models.quadratic),model:models.quadratic}};
});
const summarize=key=>({mae:mean(folds.map(f=>key==='fixed'?f.fixedError:f[key].error)),
  betterThanFixed:key==='fixed'?null:folds.filter(f=>f[key].error<f.fixedError).length,
  worst:Math.max(...folds.map(f=>key==='fixed'?f.fixedError:f[key].error))});
const result={purpose:'Analysis only. Session-level LOSO comparison; no production update.',distanceMeters:COMBINED?null:DISTANCE,fixedStrideMeters:FIXED,combinedCorridors:COMBINED,fullTrainingConstant:fit(sessions,0),
  limitations:['One user and one Galaxy model.','Only endpoint distance is physical truth; per-step ground truth is unavailable.',
    'Acceleration magnitude residual is used because phone-frame vertical acceleration is not logged.','Quadratic K(f) is high overfit risk with this session count.'],
  method:'Current detector thresholds; per-step q=(peak-valley)^0.25; K(f) fitted from training-session aggregate distance only; predicted strides bounded to fixed 65-135%.',
  sessions:sessions.map(s=>({file:s.file,route:s.route,steps:s.steps.length,medianFrequencyHz:median(s.steps.map(x=>x.frequency).filter(Number.isFinite))})),
  summary:{fixed:summarize('fixed'),constantWeinberg:summarize('constant'),adaptiveLinear:summarize('linear'),adaptiveQuadratic:summarize('quadratic')},folds};
const outDir=path.join(ROOT,COMBINED?'indoor/data/analysis/weinberg-combined-20260923':LEFT?'indoor/data/analysis/adaptive-weinberg-left-20260923':'indoor/data/analysis/adaptive-weinberg-4f-20260922');fs.mkdirSync(outDir,{recursive:true});
fs.writeFileSync(path.join(outDir,'results.json'),JSON.stringify(result,null,2)+'\n');
console.log(JSON.stringify({sessions:sessions.length,...result.summary},null,2));
