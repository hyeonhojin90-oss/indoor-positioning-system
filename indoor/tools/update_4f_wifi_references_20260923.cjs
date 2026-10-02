#!/usr/bin/env node
// Curated 4F core/stair AP references. Never import ambiguous room labels or stale scans.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const Z = require('../web/src/positioning/zone-classifier');
const ROOT = path.resolve(__dirname, '../..');
const INVENTORY = path.join(ROOT, 'indoor/data/analysis/all-4f-anchors-20260923/evaluation.json');
const OUTPUT = path.join(ROOT, 'indoor/web/data/positioning/wifi-references.json');
const REPORT = path.join(ROOT, 'indoor/data/analysis/all-4f-anchors-20260923/ap-reference-update.json');
const zones = {core_junction:'F4_CORE', stairs_left:'F4_LEFT_STAIRS', stairs_right:'F4_RIGHT_STAIRS'};
const median = xs => {const a=xs.slice().sort((x,y)=>x-y);return a.length ? (a[(a.length-1)>>1]+a[a.length>>1])/2 : null;};
const hash = bssid => `ap_${crypto.createHash('sha256').update(String(bssid)).digest('hex').slice(0,10)}`;
function parse(file) {
  const rows=[];
  for(const line of fs.readFileSync(file,'utf8').replace(/^\uFEFF/,'').split(/\r?\n/)) {
    if(!line.trim()) continue;
    try { rows.push(JSON.parse(line)); } catch { throw Error(`Malformed selected session: ${file}`); }
  }
  return rows;
}
const inventory=JSON.parse(fs.readFileSync(INVENTORY,'utf8')).inventory;
const sessions=inventory.filter(s=>zones[s.zone]&&s.anchor===s.zone&&s.quality.length===0&&s.steps===0&&s.freshScans>0).map(s=>{
  const file=path.join(ROOT,s.file), rows=parse(file), start=rows[0], end=rows.at(-1);
  if(start.kind!=='session_start'||end.kind!=='session_end'||Number(start.label.floor)!==4||start.label.zone_id!==s.zone) throw Error(`Selected session changed: ${s.file}`);
  const scans=rows.filter(r=>r.kind==='wifi_scan'&&r.fresh_results===true).map(r=>{
    const values=new Map();
    for(const ap of r.access_points||[]) if(ap.bssid&&Number.isFinite(ap.rssi_dbm)) {
      const id=hash(ap.bssid); if(!values.has(id)) values.set(id,[]);values.get(id).push(ap.rssi_dbm);
    }
    return Object.fromEntries([...values].map(([id,rs])=>[id,median(rs)]));
  });
  if(!scans.length) throw Error(`Missing fresh scan: ${s.file}`);
  const values=new Map();for(const scan of scans)for(const [id,rssi] of Object.entries(scan)){if(!values.has(id))values.set(id,[]);values.get(id).push(rssi);}
  return {...s,scans,wifi:Object.fromEntries([...values].map(([id,rs])=>[id,median(rs)]))};
});
const existing=JSON.parse(fs.readFileSync(OUTPUT,'utf8'));
function build(train, minimum=2) {
  return Object.entries(zones).map(([zone,id])=>{
    const group=train.filter(s=>s.zone===zone), old=existing.references.find(r=>r.floor===4&&r.anchor?.id===id);
    if(!old||group.length<2) return null;
    const values=new Map();
    for(const s of group)for(const [ap,rssi] of Object.entries(s.wifi)) {
      if(!values.has(ap))values.set(ap,[]);values.get(ap).push({day:s.day,rssi});
    }
    const wifi=Object.fromEntries([...values].filter(([,v])=>v.length>=minimum&&new Set(v.map(x=>x.day)).size>=2)
      .map(([ap,v])=>[ap,median(v.map(x=>x.rssi))]));
    if(Object.keys(wifi).length<4)return null;
    const days=new Set(group.map(s=>s.day)).size;
    return {...old,wifi,sources:group.map(s=>path.basename(s.file)).sort(),provenance:'curated-4f-fresh-stationary-multi-day-session-median-20260923',
      anchor:{...old.anchor,verified:group.length>=3&&days>=2,sources:group.length}};
  }).filter(Boolean);
}
function classify(scan, refs, device){
  const result=Z.classify({id:'held-out',timestamp:10000,platform:'android',device,floors:[4],quality:1,
    wifi:{supported:true,fresh:true,timestamp:10000,rssi:scan}},refs,10000);
  return {prediction:result.candidates[0]?.anchor?.id||null,accepted:result.wifiAbsoluteAccepted===true,reason:result.reason,
    score:result.candidates[0]?.wifiScore??null,margin:result.candidates.length>1?result.candidates[1].score-result.candidates[0].score:null};
}
const results=[];
for(const query of sessions){
  const train=sessions.filter(s=>s.day!==query.day), refs=build(train);
  if(!refs.some(r=>r.anchor.id===zones[query.zone]))continue;
  for(const scan of query.scans) results.push({day:query.day,file:query.file,truth:zones[query.zone],...classify(scan,refs,query.device)});
}
const today=sessions.filter(s=>s.day==='20260923').flatMap(query=>query.scans.map(scan=>({file:query.file,truth:zones[query.zone],...classify(scan,existing.references,query.device)})));
const summarize=rows=>({n:rows.length,correct:rows.filter(r=>r.accepted&&r.prediction===r.truth).length,
  wrong:rows.filter(r=>r.accepted&&r.prediction!==r.truth).length,hold:rows.filter(r=>!r.accepted).length});
const refs=build(sessions), report={method:'Fresh single AP scans; leave-one-day-out. Unknown locations and phone variability not validated. No query-day leakage.',
  selection:'4F core/stairs, valid complete label, zero steps, fresh AP result. 4122 and non-fresh scans excluded.',
  selected:sessions.map(s=>({file:s.file,day:s.day,zone:s.zone,scans:s.scans.length})),
  references:refs.map(r=>({id:r.anchor.id,sessions:r.anchor.sources,days:new Set(sessions.filter(s=>zones[s.zone]===r.anchor.id).map(s=>s.day)).size,apIds:Object.keys(r.wifi).length,verified:r.anchor.verified})),
  leaveDayOut:summarize(results),currentProductionToday:summarize(today),leaveDayOutResults:results,currentProductionTodayResults:today};
// These classroom-front scans are out of the three anchor classes. They diagnose
// false anchor matches, but are too few to validate general unknown rejection.
const nonAnchor=inventory.filter(s=>s.anchor==='main_right:4209'&&s.quality.length===0&&s.steps===0&&s.freshScans>0)
  .flatMap(s=>parse(path.join(ROOT,s.file)).filter(r=>r.kind==='wifi_scan'&&r.fresh_results===true).map(r=>{
    const wifi=Object.fromEntries((r.access_points||[]).filter(ap=>ap.bssid&&Number.isFinite(ap.rssi_dbm)).map(ap=>[hash(ap.bssid),ap.rssi_dbm]));
    return {file:s.file,...classify(wifi,refs,s.device)};
  }));
report.nonAnchor4209={scans:nonAnchor.length,acceptedAsAnchor:nonAnchor.filter(r=>r.accepted).length,results:nonAnchor};
fs.writeFileSync(REPORT,JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify({selected:sessions.length,references:report.references,leaveDayOut:report.leaveDayOut,currentProductionToday:report.currentProductionToday},null,2));
if(process.argv.includes('--write')){
  if(report.leaveDayOut.wrong||report.leaveDayOut.hold||report.nonAnchor4209.acceptedAsAnchor)
    throw Error('Refusing to publish failed held-out anchor or 4209 negative classifications');
  existing.references=existing.references.filter(r=>r.floor!==4).concat(refs).sort((a,b)=>a.floor-b.floor||a.anchor.id.localeCompare(b.anchor.id));
  existing.generated_at=new Date().toISOString();
  existing.policy='4F curated multi-day fresh stationary AP; minimum two sessions on distinct days per AP ID. Other floors unchanged. Strong recovery still requires independent accepted scans.';
  fs.writeFileSync(OUTPUT,JSON.stringify(existing,null,2)+'\n');
  console.log(`updated ${OUTPUT}`);
}
