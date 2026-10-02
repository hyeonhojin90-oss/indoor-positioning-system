(function(root,factory){if(typeof module==='object'&&module.exports)module.exports=factory();else root.IndoorSequence=factory();})(globalThis,function(){
  'use strict';
  const mean=a=>a.reduce((s,v)=>s+v,0)/a.length;
  function normalize(a){const m=mean(a),sd=Math.sqrt(mean(a.map(v=>(v-m)**2)));return sd<.3?null:a.map(v=>(v-m)/sd);}
  function distance(a,b){
    if(a.length<5||b.length<5||![...a,...b].every(Number.isFinite))return Infinity;
    const x=normalize(a),y=normalize(b);if(!x||!y)return Infinity;
    let prev=Array(y.length+1).fill(Infinity);prev[0]=0;
    const band=Math.max(3,Math.abs(x.length-y.length)+2);
    for(let i=1;i<=x.length;i++){const cur=Array(y.length+1).fill(Infinity);
      for(let j=Math.max(1,i-band);j<=Math.min(y.length,i+band);j++)cur[j]=(x[i-1]-y[j-1])**2+Math.min(prev[j],cur[j-1],prev[j-1]);prev=cur;}
    return prev[y.length]/(x.length+y.length);
  }
  function match(values,references,context){
    const candidates=references.filter(r=>r.platform===context.platform&&r.floor===context.floor&&r.direction===context.direction
      &&(!r.device||r.device===context.device)
      &&(!context.corridor||(r.corridor||(r.x>70.804?'main_left':'main_right'))===context.corridor))
      .map(r=>({...r,score:context.verticalValues
        ? (distance(values,r.values)+distance(context.verticalValues,r.verticalValues||[]))/2
        : distance(values,r.values)}))
      .filter(r=>Number.isFinite(r.score)).sort((a,b)=>a.score-b.score);
    if(!candidates.length)return {reason:'no_sequence_reference',candidates:[]};
    const best=candidates[0],alternative=candidates.find(r=>Math.abs(r.x-best.x)>6);
    const margin=alternative?alternative.score-best.score:0;
    return {reason:best.score<=.5&&margin>=.08?'sequence_candidate':'ambiguous_sequence',
      candidates:candidates.slice(0,8),margin,quality:Math.max(0,1-best.score/.5),calibratedProbability:false};
  }
  return {distance,match};
});
