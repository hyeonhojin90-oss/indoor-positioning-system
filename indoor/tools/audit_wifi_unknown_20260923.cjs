// Query session excluded, every fresh scan is classified separately; no runtime DB rewrite.
const fs=require('fs'),path=require('path'),crypto=require('crypto'),Z=require('../web/src/positioning/zone-classifier');
const root=path.resolve(__dirname,'../..');
const input=require('../data/analysis/stationary-magnetic-20260923/evaluation.json').sessions;
const id=b=>'ap_'+crypto.createHash('sha256').update(String(b)).digest('hex').slice(0,10);
const median=a=>{const b=[...a].sort((x,y)=>x-y);return (b[(b.length-1)>>1]+b[b.length>>1])/2;};
const sessions=input.map(s=>{const rows=fs.readFileSync(path.join(root,s.file),'utf8').trim().split(/\r?\n/).map(JSON.parse),scans=rows.filter(r=>r.kind==='wifi_scan'&&r.fresh_results===true);const groups={};
 for(const scan of scans)for(const ap of scan.access_points||[])if(ap.bssid&&Number.isFinite(ap.rssi_dbm))(groups[id(ap.bssid)]??=[]).push(ap.rssi_dbm);
 return {...s,scans,wifi:Object.fromEntries(Object.entries(groups).map(([k,v])=>[k,median(v)]))};});
const results=[];
for(const s of sessions){const refs=sessions.filter(r=>r.file!==s.file).map(r=>({floor:4,platform:'android',device:r.device,zone:r.zone,wifi:r.wifi,anchor:{id:r.zone}}));
 for(const scan of s.scans){const t=scan.wall_time_ms,rssi=Object.fromEntries((scan.access_points||[]).filter(a=>a.bssid&&Number.isFinite(a.rssi_dbm)).map(a=>[id(a.bssid),a.rssi_dbm]));
 const obs=Z.classify({id:String(t),timestamp:t,platform:'android',device:s.device,quality:1,wifi:{supported:true,fresh:true,timestamp:t,rssi}},refs,t);
 results.push({file:s.file,truth:s.zone,time:t,prediction:obs.candidates[0]?.zone??null,accepted:obs.wifiAbsoluteAccepted===true,score:obs.candidates[0]?.wifiScore??null,reason:obs.reason});}}
const report={method:'Six corrected stationary sessions; leave whole query session out, use each fresh scan separately. Known anchor tests only, no real unmeasured-area negatives. Correlated scans are not independent trials.',policy:{minimumCommonAP:4,minReferenceCoverage:.1,maxRmsDb:16,scoreMax:4,validatedUnknownRejection:false},summary:{scans:results.length,accepted:results.filter(r=>r.accepted).length,correct:results.filter(r=>r.accepted&&r.prediction===r.truth).length,wrong:results.filter(r=>r.accepted&&r.prediction!==r.truth).length},results};
const out=path.join(root,'indoor/data/analysis/radio-fix-20260923');fs.mkdirSync(out,{recursive:true});fs.writeFileSync(path.join(out,'wifi-evaluation.json'),JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report,null,2));
