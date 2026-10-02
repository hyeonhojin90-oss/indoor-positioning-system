(function(root,factory){if(typeof module==='object'&&module.exports)module.exports=factory();else root.IndoorCalibration=factory();})(globalThis,function(){
  'use strict';
  function fit(rows,lambda=2){
    const usable=rows.filter(r=>[r.cadence,r.peak,r.stride].every(Number.isFinite)&&r.stride>0);
    if(usable.length<6)return null;
    const means=[0,1].map(i=>usable.reduce((s,r)=>s+[r.cadence,r.peak][i],0)/usable.length);
    const scales=means.map((m,i)=>Math.max(.1,Math.sqrt(usable.reduce((s,r)=>s+([r.cadence,r.peak][i]-m)**2,0)/usable.length)));
    const a=Array.from({length:3},()=>[0,0,0,0]);
    for(const r of usable){const x=[1,(r.cadence-means[0])/scales[0],(r.peak-means[1])/scales[1]];
      for(let i=0;i<3;i++){for(let j=0;j<3;j++)a[i][j]+=x[i]*x[j];a[i][3]+=x[i]*r.stride;}}
    a[1][1]+=lambda;a[2][2]+=lambda;
    for(let c=0;c<3;c++){let pivot=c;for(let r=c+1;r<3;r++)if(Math.abs(a[r][c])>Math.abs(a[pivot][c]))pivot=r;
      [a[c],a[pivot]]=[a[pivot],a[c]];if(Math.abs(a[c][c])<1e-10)return null;
      const v=a[c][c];for(let j=c;j<4;j++)a[c][j]/=v;
      for(let r=0;r<3;r++)if(r!==c){const q=a[r][c];for(let j=c;j<4;j++)a[r][j]-=q*a[c][j];}}
    const b=a[1][3]/scales[0],c=a[2][3]/scales[1];
    return {coefficients:[a[0][3]-b*means[0]-c*means[1],b,c],units:'map_units',validated:false,
      trainingRows:usable.length,lambda,reason:'requires_session_holdout_and_surveyed_distance'};
  }
  function predict(model,row,base){if(!model)return base;const [a,b,c]=model.coefficients;return Math.max(base*.8,Math.min(base*1.2,a+b*row.cadence+c*row.peak));}
  function smooth(points,anchors){
    const output=points.map(p=>({...p,smoothedX:null,method:null})),issues=[];
    const ordered=[...anchors].sort((a,b)=>a.time-b.time);
    for(let i=1;i<ordered.length;i++){
      const a=ordered[i-1],b=ordered[i];if(b.time<=a.time||a.floor!==b.floor||![a.x,b.x].every(Number.isFinite)){issues.push({index:i,reason:'invalid_anchor_interval'});continue;}
      const segment=output.filter(p=>p.time>=a.time&&p.time<=b.time);if(!segment.length)continue;
      const span=segment.at(-1).progress-segment[0].progress;
      if(!(span>0)){issues.push({index:i,reason:'no_motion_between_laps'});continue;}
      for(const p of segment){p.smoothedX=a.x+(b.x-a.x)*(p.progress-segment[0].progress)/span;p.method='offline_lap_constrained_not_ground_truth';}
    }
    return {points:output,issues};
  }
  return {fit,predict,smooth};
});
