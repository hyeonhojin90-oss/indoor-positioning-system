// Exploratory stationary-session discrimination, not independent positioning accuracy.
const fs = require('fs');
const path = require('path');
const base = 'indoor/data/curated/android/2026-09-18';
const out = 'indoor/data/analysis/detailed-20260918/f5-correction-feasibility';
const median = a => { a = [...a].sort((x,y)=>x-y); return a.length ? (a[(a.length-1)>>1]+a[a.length>>1])/2 : null; };
function fingerprint(rows, type, min=1) {
  const groups = new Map();
  for (const r of rows) for (const [id, v] of type==='wifi' ? (r.access_points||[]).map(a=>[a.bssid,a.rssi_dbm]) : [[r.anonymous_id,r.rssi_dbm]]) {
    if (id && Number.isFinite(v)) { if (!groups.has(id)) groups.set(id,[]); groups.get(id).push(v); }
  }
  return new Map([...groups].filter(([,v])=>v.length>=min).map(([k,v])=>[k,median(v)]));
}
function distance(a,b) {
  const common = [...a.keys()].filter(k=>b.has(k));
  return { shared:common.length, mad:median(common.map(k=>Math.abs(a.get(k)-b.get(k)))), jaccard:common.length/(a.size+b.size-common.length||1) };
}
const sessions = fs.readdirSync(base).filter(f=>f.includes('__corrected-f5-')).sort().map(file=>{
  const rows = fs.readFileSync(path.join(base,file),'utf8').trim().split(/\r?\n/).map(JSON.parse);
  return {file, name:rows[0].label.location, duration:rows.find(r=>r.kind==='session_end').session_elapsed_ms,
    wifi:rows.filter(r=>r.kind==='wifi_scan' && r.fresh_results), ble:rows.filter(r=>r.kind==='ble_observation')};
});
function rank(query, refs, own) {
  const ranked=refs.map((ref,i)=>({name:sessions[i].name,...distance(query,ref)})).filter(x=>x.shared>=5).sort((a,b)=>a.mad-b.mad);
  const self=ranked.find(x=>x.name===own), other=ranked.find(x=>x.name!==own);
  return {prediction:ranked[0]?.name||null, correct:ranked[0]?.name===own, self, other, margin:self&&other?other.mad-self.mad:null};
}
const fullWifi=sessions.map(s=>fingerprint(s.wifi,'wifi'));
const fullBle=sessions.map(s=>fingerprint(s.ble,'ble',3));
const report={limitations:['One stationary session per location; same-session holdout is optimistic, not walking or independent-session validation.', 'Common-ID median absolute RSSI difference; >=5 shared IDs required. No missing-ID penalty. Exploratory matching only.', '5F assignments user-supported but tentative; 5119 explicitly confirmed.'], sessions:[]};
sessions.forEach((s,i)=>{
  const wifiTests=s.wifi.length<2?[]:s.wifi.map((r,k)=>rank(fingerprint([r],'wifi'),fullWifi.map((ref,j)=>j===i?fingerprint(s.wifi.filter((_,n)=>n!==k),'wifi'):ref),s.name));
  const halves=[s.ble.filter(r=>r.session_elapsed_ms<s.duration/2),s.ble.filter(r=>r.session_elapsed_ms>=s.duration/2)];
  const halfTests=halves.map((rows,k)=>rank(fingerprint(rows,'ble',3),fullBle.map((ref,j)=>j===i?fingerprint(halves[1-k],'ble',3):ref),s.name));
  const windows=[];
  for(let start=0;start+5000<=s.duration;start+=5000){
    if(start<s.duration/2 && start+5000>s.duration/2)continue;
    const query=fingerprint(s.ble.filter(r=>r.session_elapsed_ms>=start&&r.session_elapsed_ms<start+5000),'ble',2);
    const result=rank(query,fullBle.map((ref,j)=>j===i?fingerprint(halves[start>=s.duration/2?0:1],'ble',3):ref),s.name);
    windows.push({start,identifiers:query.size,...result});
  }
  report.sessions.push({name:s.name,file:s.file,durationSeconds:s.duration/1000,freshWifi:s.wifi.length,wifiTests,halfTests,windows,
    windowSummary:{tested:windows.length,correct:windows.filter(w=>w.correct).length,noMatch:windows.filter(w=>!w.prediction).length,medianMargin:median(windows.map(w=>w.margin).filter(Number.isFinite))}});
});
report.pairs=[];
for(let i=0;i<sessions.length;i++)for(let j=i+1;j<sessions.length;j++)report.pairs.push({a:sessions[i].name,b:sessions[j].name,wifi:distance(fullWifi[i],fullWifi[j]),ble:distance(fullBle[i],fullBle[j])});
fs.mkdirSync(out,{recursive:true});
fs.writeFileSync(path.join(out,'report.json'),JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify({sessions:report.sessions.map(s=>({name:s.name,wifi:s.wifiTests,halves:s.halfTests,windows:s.windowSummary})),pairs:report.pairs},null,2));
