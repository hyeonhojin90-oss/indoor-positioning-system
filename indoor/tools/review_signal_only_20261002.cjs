const fs=require('node:fs'),path=require('node:path'),Z=require('../web/src/positioning/zone-classifier');
const files=require('../data/analysis/weinberg-combined-20260923/results.json').folds.map(f=>f.file);
const bleRefs=require('../web/data/positioning/ble-references.json').references;
const magRefs=require('../web/data/positioning/zone-references.json').references;
const median=a=>[...a].sort((a,b)=>a-b)[a.length>>1];
const results=[];
for(const file of files){
  const rows=fs.readFileSync(file,'utf8').trim().split(/\r?\n/).map(JSON.parse),start=rows[0];
  const day=path.basename(file).match(/\d{8}/)[0],device=start.device;
  const refs=[...bleRefs,...magRefs].filter(r=>r.floor===4&&(r.sources||[]).length
    &&!(r.sources||[]).some(s=>s.includes(day)));
  const endTime=rows.filter(r=>r.kind==='label').at(-1).wall_time_ms;
  let lastWindow=-Infinity,ble=[],mag=[];const observations=[];
  for(const row of rows){
    const time=row.wall_time_ms;if(time>endTime)break;
    if(row.kind==='ble_observation')ble.push({time,id:row.anonymous_id,rssi:row.rssi_dbm});
    if(row.sensor==='magnetic_field_ut')mag.push({time,value:Math.hypot(...row.values.slice(0,3))});
    ble=ble.filter(v=>time-v.time<=5000);mag=mag.filter(v=>time-v.time<=2000);
    if(time-lastWindow<3000)continue;lastWindow=time;
    const grouped={};for(const v of ble)(grouped[v.id]??=[]).push(v.rssi);
    const rssi=Object.fromEntries(Object.entries(grouped).filter(([,v])=>v.length>=2).map(([k,v])=>[k,median(v)]));
    const mags=mag.map(v=>v.value),magMedian=mags.length?median(mags):null;
    const std=mags.length?Math.sqrt(mags.reduce((s,v)=>s+(v-magMedian)**2,0)/mags.length):null;
    const common={id:`review-${time}`,timestamp:time,platform:'android',device,floors:[4],quality:1};
    for(const mode of ['ble','magnetic','joint']){
      const obs={...common,...(mode!=='magnetic'?{ble:{supported:true,timestamp:time,rssi}}:{}),
        ...(mode!=='ble'?{magnetic:magMedian,magneticStd:std}:{})};
      const match=Z.classify(obs,refs,time),best=match.candidates[0],second=match.candidates[1];
      const accepted=!!best&&best.score<=2&&(!second||second.score-best.score>=1);
      observations.push({time,mode,predictedZone:best?.zone||null,anchor:best?.anchor?.id||null,score:best?.score??null,
        accepted,features:match.features,reason:match.reason});
    }
  }
  results.push({file,corridor:start.label.route_id.includes('TO_RIGHT_STAIRS')?'main_right':'main_left',
    wifiScans:rows.filter(r=>r.kind==='wifi_scan').length,observations});
}
const summary={};for(const mode of ['ble','magnetic','joint']){
  const rows=results.flatMap(r=>r.observations.filter(o=>o.mode===mode).map(o=>({...o,corridor:r.corridor})));
  summary[mode]={windows:rows.length,candidates:rows.filter(r=>r.predictedZone).length,accepted:rows.filter(r=>r.accepted).length,
    oppositeCorridorCandidates:rows.filter(r=>r.predictedZone?.startsWith('main_')&&r.predictedZone!==r.corridor).length,
    oppositeCorridorAccepted:rows.filter(r=>r.accepted&&r.predictedZone?.startsWith('main_')&&r.predictedZone!==r.corridor).length};
  const countBy=key=>Object.fromEntries([...new Set(rows.filter(r=>r.accepted).map(key))].map(k=>[k,rows.filter(r=>r.accepted&&key(r)===k).length]));
  summary[mode].acceptedZones=countBy(r=>r.predictedZone);
  summary[mode].acceptedFeatures=countBy(r=>r.features.join('+'));
}
const report={method:'3-second disjoint query times with rolling 5-second BLE/2-second magnetic observations; no PDR position or heading gates. Known 4F, different-day fingerprint sources only. Raw candidates versus provisional score<=2 and margin>=1 abstention.',
  limitations:['No AP in these 11 moving recordings; AP signal-only/hybrid not evaluated','Adjacent windows share some data; windows are not independent sessions','Opposite corridor is a contradiction diagnostic, not precise coordinate accuracy','Stationary magnetic prototypes do not replace a moving-pattern map; new threshold not calibrated','No signal-first engine or beacon performance claim; review only'],summary,results};
const dir='indoor/data/analysis/meters-20261002';fs.mkdirSync(dir,{recursive:true});fs.writeFileSync(dir+'/signal-only-review.json',JSON.stringify(report,null,2));console.log(JSON.stringify(summary));
