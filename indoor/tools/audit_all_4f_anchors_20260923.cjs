const fs=require('fs'),path=require('path'),Z=require('../web/src/positioning/zone-classifier');
const out='indoor/data/analysis/all-4f-anchors-20260923';fs.mkdirSync(out,{recursive:true});
const walk=d=>fs.readdirSync(d,{withFileTypes:true}).flatMap(e=>e.isDirectory()?walk(d+'/'+e.name):e.name.endsWith('.jsonl')?[d+'/'+e.name]:[]);
const seen=new Set(),sessions=[],duplicates=[];const median=a=>{a.sort((a,b)=>a-b);return a.length?(a[(a.length-1)>>1]+a[a.length>>1])/2:null};
for(const file of [...walk('indoor/data/curated'),...walk('indoor/data/raw')]){
 const lines=fs.readFileSync(file,'utf8').replace(/^\uFEFF/,'').trim().split(/\r?\n/);let s;try{s=JSON.parse(lines[0])}catch{continue}
 const l=s.label||{};if(String(l.floor)!=='4'||!/(ANCHOR|ZONE)/.test(l.route_id||''))continue;
 const key=s.device+':'+s.wall_time_ms;if(seen.has(key)){duplicates.push(file);continue}seen.add(key);
 const rows=[],quality=[];for(const line of lines){try{rows.push(JSON.parse(line))}catch{quality.push('invalid_json')}}
 const room=l.location?.match(/4\d{3}(?:-\d+)?/g),zone=l.zone_id||'unknown',anchor=zone+(/^main_/.test(zone)&&room?':'+room.at(-1):'');
 if(/^stairs_/.test(zone)&&room)quality.push('contradictory_label');if(rows.at(-1)?.kind!=='session_end')quality.push('incomplete');
 const scans=rows.filter(r=>r.kind==='wifi_scan'&&r.fresh_results).map(r=>Object.fromEntries((r.access_points||[]).map(a=>[a.bssid,a.rssi_dbm]))),aps={},bs={};
 for(const scan of scans)for(const [k,v] of Object.entries(scan))(aps[k]??=[]).push(v);
 for(const r of rows)if(r.kind==='ble_observation'&&r.wall_time_ms-s.wall_time_ms>=2000)(bs[r.anonymous_id]??=[]).push(r.rssi_dbm);
 const med=g=>Object.fromEntries(Object.entries(g).map(([k,v])=>[k,median(v)]));
 sessions.push({file,day:file.match(/indoor_positioning_(\d{8})/)[1],device:s.device,zone,anchor,quality,steps:rows.at(-1)?.steps_since_start,scans,wifi:med(aps),ble:med(Object.fromEntries(Object.entries(bs).filter(([,v])=>v.length>=3)))});
}
const usable=sessions.filter(s=>!s.quality.length),results=[];
for(const split of ['session','day'])for(const feature of ['wifi','ble','joint'])for(const q of usable){
 const train=usable.filter(s=>s!==q&&(split==='session'||s.day!==q.day));
 const refs=train.map(s=>({floor:4,platform:'android',device:s.device,zone:s.zone,anchor:{id:s.anchor},...(feature!=='ble'?{wifi:s.wifi}:{}),...(feature!=='wifi'?{ble:s.ble}:{})}));
 const obs={id:'test',timestamp:10000,platform:'android',device:q.device,quality:1,...(feature!=='ble'?{wifi:{supported:true,fresh:true,timestamp:10000,rssi:q.wifi}}:{}),...(feature!=='wifi'?{ble:{supported:true,timestamp:10000,rssi:q.ble}}:{})};
 const r=Z.classify(obs,refs,10000),best=r.candidates[0];results.push({split,feature,file:q.file,truth:q.anchor,represented:train.some(s=>s.anchor===q.anchor),prediction:best?.anchor?.id||null,reason:r.reason,correct:best?.anchor?.id===q.anchor});
}
const summary=[];for(const split of ['session','day'])for(const feature of ['wifi','ble','joint']){const a=results.filter(r=>r.split===split&&r.feature===feature&&r.represented);summary.push({split,feature,n:a.length,correct:a.filter(r=>r.correct).length,wrong:a.filter(r=>r.prediction&&!r.correct).length,noCandidate:a.filter(r=>!r.prediction).length})}
const pairs=[];for(const a of usable)for(const b of usable)if(a.day==='20260923'&&b.day!=='20260923'&&a.anchor===b.anchor){const common=Object.keys(a.ble).filter(k=>k in b.ble);pairs.push({today:a.anchor,reference:b.file,commonBle:common.length,medianDb:median(common.map(k=>Math.abs(a.ble[k]-b.ble[k])))})}
fs.writeFileSync(out+'/evaluation.json',JSON.stringify({method:'All local 4F stationary files, curated priority, device+start dedup; malformed/incomplete/conflicting labels excluded. Whole-session median fingerprint diagnostic using production classifier; LOSO and leave-day-out; exact classroom anchors distinct; not online 5-second window accuracy.',inventory:sessions.map(({wifi,ble,scans,...s})=>({...s,apIds:Object.keys(wifi).length,bleIds:Object.keys(ble).length,freshScans:scans.length})),duplicates,summary,pairs,results},null,2));console.log(JSON.stringify({files:sessions.length,usable:usable.length,duplicates:duplicates.length,excluded:sessions.filter(s=>s.quality.length).map(s=>({file:s.file,quality:s.quality})),summary,pairs},null,2));
