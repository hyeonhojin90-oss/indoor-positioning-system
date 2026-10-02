// Diagnostic only: vary BLE classifier minimum overlap; never mutate runtime assets.
const fs=require('fs'),path=require('path'),vm=require('vm');
const root=path.resolve(__dirname,'../..');
const refs=require('../web/data/positioning/ble-references.json').references;
const nav=require('../web/src/positioning/navigation');
const map=nav.compile(require('../web/data/navigation/areas-v1.json'),4);
const source=fs.readFileSync(path.join(__dirname,'../web/src/positioning/zone-classifier.js'),'utf8');
const median=a=>{const b=[...a].sort((x,y)=>x-y);return (b[(b.length-1)>>1]+b[b.length>>1])/2;};
const raw='indoor/data/raw/android/2026-09-22/post-grid-four/';
const files=[raw+'indoor_positioning_20260922_211406.jsonl',raw+'indoor_positioning_20260922_211528.jsonl',
 'indoor/data/curated/android/2026-09-22/post-grid-four/indoor_positioning_20260922_211714-left-stairs-corrected.jsonl',raw+'indoor_positioning_20260922_211757.jsonl'];
const results=[];
for(const file of files){
 const rows=fs.readFileSync(path.join(root,file),'utf8').trim().split(/\r?\n/).map(JSON.parse);
 const start=rows[0],truth=start.label.zone_id,ble=rows.filter(r=>r.kind==='ble_observation');
 for(const threshold of [5,4,3,2]){
  const bleGate=/if \(keys\.length>=\d+\) \{/;
  if(!bleGate.test(source))throw new Error('BLE overlap gate not found');
  const sandbox={module:{exports:{}}};vm.runInNewContext(source.replace(bleGate,`if (keys.length>=${threshold}) {`),sandbox);
  const classify=sandbox.module.exports.classify;
  let last=-Infinity,window=[],pred=null;const windows=[];
  for(const row of rows){
   if(row.kind==='derived_fusion')pred=row;
   if(row.kind!=='ble_observation')continue;
   const t=row.wall_time_ms;window.push(row);window=window.filter(r=>t-r.wall_time_ms<=5000);
   if(t-last<3000)continue;last=t;
   const g=new Map();for(const r of window){if(!g.has(r.anonymous_id))g.set(r.anonymous_id,[]);g.get(r.anonymous_id).push(r.rssi_dbm);}
   const rssi=Object.fromEntries([...g].filter(([,a])=>a.length>=2).map(([id,a])=>[id,median(a)]));
   const result=Object.keys(rssi).length>=threshold?classify({id:String(t),timestamp:t,platform:'android',device:start.device,ble:{supported:true,timestamp:t,rssi}},refs,t):{reason:'insufficient_ble_window',candidates:[]};
   const best=result.candidates[0];
   const gate=pred?result.candidates.filter(c=>Math.abs(nav.metricDistance(map,c.anchor.x)-nav.metricDistance(map,pred.x))<=12):[];
   windows.push({time:t-start.wall_time_ms,reason:result.reason,best:best?.zone||null,correct:truth&&best?best.zone===truth:null,gateCandidates:gate.map(c=>c.zone)});
  }
  results.push({file:path.basename(file),truth:truth||'moving-no-point-truth',threshold,windows:windows.length,classified:windows.filter(w=>w.best).length,correct:truth?windows.filter(w=>w.correct).length:null,pdrGateEligible:truth?null:windows.filter(w=>w.gateCandidates.length).length,topZones:windows.reduce((o,w)=>(o[w.best||'unavailable']=(o[w.best||'unavailable']||0)+1,o),{}),details:windows});
 }
}
const out=path.join(root,'indoor/data/analysis/radio-policy-20260923');fs.mkdirSync(out,{recursive:true});
fs.writeFileSync(path.join(out,'ble-threshold-diagnostic.json'),JSON.stringify({note:'Same overlapping 5s windows, production references; NOT independent accuracy or full particle replay. Movement gate uses saved predictions.',results},null,2)+'\n');
console.log(JSON.stringify(results.map(({details,...r})=>r),null,2));
