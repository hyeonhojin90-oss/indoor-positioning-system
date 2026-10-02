const fs=require('node:fs'),path=require('node:path');
const Z=require('../web/src/positioning/zone-classifier');
const root=path.resolve(__dirname,'../..'),dir=path.join(root,'indoor/data/curated/android/2026-09-18');
const anchors={
 'verified-f4-core':{id:'f4_core',zone:'core_junction',x:70.804},
 'verified-f4-main-left-4225':{id:'f4_4225',zone:'main_left',x:107.2535},
 'verified-f4-stairs-left':{id:'f4_stairs_left',zone:'stairs_left',x:135.407},
 'verified-f4-main-right-4209':{id:'f4_4209',zone:'main_right',x:38.0361},
 'corrected-f4-stairs-right':{id:'f4_stairs_right',zone:'stairs_right',x:3.3631}};
const median=a=>{const b=[...a].sort((x,y)=>x-y),n=b.length;return n%2?b[(n-1)/2]:(b[n/2-1]+b[n/2])/2;};
const sessions=fs.readdirSync(dir).filter(f=>f.endsWith('.jsonl')&&Object.keys(anchors).some(k=>f.includes(k))).map(file=>{
 const rows=fs.readFileSync(path.join(dir,file),'utf8').trim().split(/\r?\n/).map(JSON.parse),start=rows.find(r=>r.kind==='session_start'),key=Object.keys(anchors).find(k=>file.includes(k));
 const ble=rows.filter(r=>r.kind==='ble_observation'&&r.anonymous_id&&Number.isFinite(r.rssi_dbm));
 const min=Math.min(...ble.map(r=>r.wall_time_ms)),max=Math.max(...ble.map(r=>r.wall_time_ms)),split=(min+max)/2;
 return {file,start,a:anchors[key],ble,min,max,split};
});
const fingerprint=rows=>{const g=new Map();for(const r of rows){if(!g.has(r.anonymous_id))g.set(r.anonymous_id,[]);g.get(r.anonymous_id).push(r.rssi_dbm);}return Object.fromEntries([...g].filter(([,v])=>v.length>=2).map(([k,v])=>[k,median(v)]));};
const refs=sessions.map(s=>({floor:4,platform:'android',device:s.start.device,zone:s.a.zone,ble:fingerprint(s.ble.filter(r=>r.wall_time_ms<s.split)),anchor:{id:s.a.id,x:s.a.x,y:0,sigma_m:6}}));
const rows=[];for(const s of sessions){for(let t=s.split;t<s.max;t+=5000){const rssi=fingerprint(s.ble.filter(r=>r.wall_time_ms>=t&&r.wall_time_ms<t+5000));if(Object.keys(rssi).length<5)continue;const o=Z.classify({id:`${s.a.id}-${t}`,timestamp:t+5000,platform:'android',device:s.start.device,ble:{supported:true,timestamp:t+5000,rssi}},refs,t+5000);rows.push({truth:s.a.id,predicted:o.candidates[0]?.anchor?.id||null,reason:o.reason,signals:Object.keys(rssi).length,topWeight:o.candidates[0]?.weight||null,margin:o.candidates.length>1?o.candidates[0].weight-o.candidates[1].weight:o.candidates[0]?.weight||null});}}
const evaluated=rows.filter(r=>r.predicted),correct=rows.filter(r=>r.predicted===r.truth);
const report={createdAt:new Date().toISOString(),method:'First half of each stationary session builds one reference; disjoint 5 s windows from the second half are classified. Same-day, same-session split is not independent field validation.',references:refs.map(r=>({id:r.anchor.id,signals:Object.keys(r.ble).length})),windows:rows.length,evaluated:evaluated.length,correct:correct.length,top1:evaluated.length?correct.length/evaluated.length:null,rows};
const out=path.join(root,'indoor/data/analysis/detailed-20260918/4f-magnetic-ablation/ble-soft-reference-validation.json');fs.writeFileSync(out,JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify({...report,rows:undefined},null,2));
