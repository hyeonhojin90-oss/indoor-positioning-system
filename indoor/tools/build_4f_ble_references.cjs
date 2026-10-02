const fs=require('node:fs');
const path=require('node:path');

const root=path.resolve(__dirname,'../..');
const sourceDir=path.join(root,'indoor/data/curated/android/2026-09-18');
const output=path.join(root,'indoor/web/data/positioning/ble-references.json');
const anchors={
  'verified-f4-core':{id:'f4_core',zone:'core_junction',x:70.804,y:0},
  'verified-f4-main-left-4225':{id:'f4_4225',zone:'main_left',x:107.2535,y:0},
  'verified-f4-stairs-left':{id:'f4_stairs_left',zone:'stairs_left',x:135.407,y:0},
  'verified-f4-main-right-4209':{id:'f4_4209',zone:'main_right',x:38.0361,y:0},
  'corrected-f4-stairs-right':{id:'f4_stairs_right',zone:'stairs_right',x:3.363100346020758,y:0}
};
const median=a=>{const b=[...a].sort((x,y)=>x-y);return b.length%2?b[(b.length-1)/2]:(b[b.length/2-1]+b[b.length/2])/2;};
const files=fs.readdirSync(sourceDir).filter(f=>f.endsWith('.jsonl')&&Object.keys(anchors).some(k=>f.includes(k)));
const references=files.map(file=>{
  const rows=fs.readFileSync(path.join(sourceDir,file),'utf8').trim().split(/\r?\n/).map(JSON.parse);
  const start=rows.find(r=>r.kind==='session_start');
  const grouped=new Map();
  for(const r of rows)if(r.kind==='ble_observation'&&r.anonymous_id&&Number.isFinite(r.rssi_dbm)){
    if(!grouped.has(r.anonymous_id))grouped.set(r.anonymous_id,[]);grouped.get(r.anonymous_id).push(r.rssi_dbm);
  }
  const ble=Object.fromEntries([...grouped].filter(([,v])=>v.length>=3).map(([id,v])=>[id,median(v)]));
  const key=Object.keys(anchors).find(k=>file.includes(k)),a=anchors[key];
  return {floor:4,platform:'android',device:start.device,zone:a.zone,label:start.label.location,
    ble,bleMinimumObservations:3,sources:[file],provenance:'single-stationary-session-soft-reference',
    anchor:{id:a.id,x:a.x,y:a.y,verified:false,sources:1,sigma_m:6}};
});
fs.mkdirSync(path.dirname(output),{recursive:true});
fs.writeFileSync(output,JSON.stringify({version:1,createdAt:new Date().toISOString(),
  policy:{window_ms:5000,evaluation_interval_ms:3000,min_common_signals:4,
    limitation:'Each anchor is one stationary session. Use only for soft A/B reweighting; never hard recovery.'},references},null,2)+'\n');
console.log(JSON.stringify(references.map(r=>({id:r.anchor.id,zone:r.zone,signals:Object.keys(r.ble).length})),null,2));
