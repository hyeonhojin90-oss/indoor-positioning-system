(function(root,factory){if(typeof module==='object'&&module.exports)module.exports=factory();else root.IndoorQuality=factory();})(globalThis,function(){
  'use strict';
  const clamp=v=>Math.max(0,Math.min(1,v));
  function magnetic(values){
    const clean=values.filter(Number.isFinite);if(clean.length<5)return {weight:0,reason:'insufficient_magnetic_samples'};
    const sorted=[...clean].sort((a,b)=>a-b),median=sorted[Math.floor(sorted.length/2)];
    const std=Math.sqrt(clean.reduce((s,v)=>s+(v-median)**2,0)/clean.length);
    const jump=Math.max(...clean.slice(1).map((v,i)=>Math.abs(v-clean[i])));
    const weight=median<10||median>120?0:clamp(1-std/15)*clamp(1-jump/35);
    return {median,std,jump,weight,reason:weight<.2?'magnetic_disturbance':'usable'};
  }
  function gait(intervals,peak){
    if(!Number.isFinite(peak)||peak<.8||peak>35)return {weight:0,reason:'invalid_step_peak'};
    if(!intervals.length)return {weight:.6,reason:'gait_warmup'};
    const last=intervals.at(-1);if(last<280)return {weight:0,reason:'duplicate_step'};
    const active=intervals.filter(v=>v>=280&&v<1800);
    if(active.length<3)return {weight:.6,reason:'gait_warmup'};
    const mean=active.reduce((s,v)=>s+v,0)/active.length;
    const cv=Math.sqrt(active.reduce((s,v)=>s+(v-mean)**2,0)/active.length)/mean;
    return {weight:Math.max(.25,1-cv),reason:cv>.35?'irregular_gait':'usable'};
  }
  return {magnetic,gait};
});
