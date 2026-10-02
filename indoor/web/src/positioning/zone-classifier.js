(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.IndoorZones = factory();
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";
  const finite = Number.isFinite;
  function fromLegacy(data) {
    // Keep platforms apart. Do not invent fingerprints for unknown stair interiors.
    return data.fingerprints.filter(r => finite(r.map_x)).map(r => ({
      floor:r.floor, platform:r.platform, device:r.device || null,
      zone: r.node_id === "CORE" ? "core_junction" : r.node_id === "RIGHT_STAIRS" ? "stairs_right"
        : r.node_id === "LEFT_STAIRS" ? "stairs_left" : r.map_x < 70.804 ? "main_right" : "main_left",
      magnetic:r.magnetic_median_ut, spread:Math.max(3,r.magnetic_within_window_std_ut || 0),
      wifi:null, sources:r.sources, provenance:"legacy-stationary-window", position:{x:r.map_x,y:0}
    }));
  }
  function classify(observation, references, now) {
    const empty = reason => ({id:observation?.id, timestamp:observation?.timestamp, candidates:[], reason,
      confidence:"unavailable", calibratedProbability:false, features:[]});
    if (!observation || !finite(observation.timestamp) || now-observation.timestamp > 5000 || observation.timestamp > now+100) return empty("stale_observation");
    const mag = finite(observation.magnetic) && (!finite(observation.magneticStd) || observation.magneticStd <= 8);
    const radio = observation.wifi?.supported === true && observation.wifi.fresh === true
      && finite(observation.wifi.timestamp) && now-observation.wifi.timestamp <= 5000 && observation.wifi.timestamp <= now+100;
    const ble = observation.ble?.supported === true && finite(observation.ble.timestamp)
      && now-observation.ble.timestamp <= 5000 && observation.ble.timestamp <= now+100;
    const refs = references.filter(r => r.platform === observation.platform
      && (!r.device || r.device === observation.device)
      && (!observation.floors || observation.floors.includes(r.floor)));
    if (!refs.length) return empty("no_reference_data");
    const groups = new Map();
    for (const r of refs) {
      const terms=[];
      if (mag && finite(r.magnetic)) terms.push({feature:"magnetic",score:((observation.magnetic-r.magnetic)/Math.max(3,r.spread || 3))**2});
      if (radio && r.wifi) {
        const readings=observation.wifi.rssi || {};
        const keys=Object.keys(r.wifi).filter(k=>finite(readings[k]) && finite(r.wifi[k]));
        const coverage=keys.length/Math.max(1,Object.keys(r.wifi).length);
        if (keys.length>=4&&coverage>=.1) terms.push({feature:"wifi",score:keys.reduce((s,k)=>s+((readings[k]-r.wifi[k])/8)**2,0)/keys.length});
      }
      if (ble && r.ble) {
        const readings=observation.ble.rssi || {};
        const keys=Object.keys(r.ble).filter(k=>finite(readings[k]) && finite(r.ble[k]));
        if (keys.length>=4) {
          const mae=keys.reduce((s,k)=>s+Math.abs(readings[k]-r.ble[k]),0)/keys.length;
          const coverage=Math.min(1,keys.length/Math.min(20,Object.keys(r.ble).length));
          terms.push({feature:"ble",score:(mae/8)**2+2*(1-coverage)});
        }
      }
      if (!terms.length) continue;
      const key=terms.some(t=>t.feature==="ble"||t.feature==="wifi")&&r.anchor?.id?`${r.floor}:${r.zone}:${r.anchor.id}`:`${r.floor}:${r.zone}`;
      const score=terms.reduce((s,t)=>s+t.score,0)/terms.length;
      if (!groups.has(key)) groups.set(key,[]);
      groups.get(key).push({floor:r.floor,zone:r.zone,score,wifiScore:terms.find(t=>t.feature==='wifi')?.score,anchor:r.anchor,position:r.position,features:terms.map(t=>t.feature)});
    }
    // Equal contribution per zone, not proportional to number of classroom labels.
    const candidates=[...groups.values()].map(rows=>{
      rows.sort((a,b)=>a.score-b.score);
      const k=rows.slice(0,Math.min(3,rows.length));
      return {...k[0],score:k.reduce((s,r)=>s+r.score,0)/k.length,
        wifiScore:k.every(r=>finite(r.wifiScore))?k.reduce((s,r)=>s+r.wifiScore,0)/k.length:null};
    }).sort((a,b)=>a.score-b.score);
    if (!candidates.length) return empty("no_usable_features");
    if (candidates[0].score>9) return empty("out_of_distribution");
    // Provisional open-set gate: two-AP overlap and relative rank alone are insufficient.
    // Score=4 corresponds to 16dB RMS for Wi-Fi-only observations; not calibrated probability.
    // On 4F a classroom-front scan (4209) can resemble both core and stairs.
    // The surveyed core/stair scans have a clear second-place gap; reject a
    // single ambiguous AP match before it reaches either soft or hard fusion.
    const wifiDistinctive=candidates[0].floor!==4||(
      candidates[0].wifiScore<=2&&(!candidates[1]||candidates[1].score-candidates[0].score>=1));
    const wifiAbsoluteAccepted=radio&&finite(candidates[0].wifiScore)&&candidates[0].wifiScore<=4&&wifiDistinctive;
    if(radio&&!mag&&!ble&&!wifiAbsoluteAccepted)return empty('wifi_unknown_or_unqualified');
    const sum=candidates.reduce((s,c)=>s+Math.exp(-c.score/2),0);
    candidates.forEach(c=>{c.weight=Math.exp(-c.score/2)/sum;});
    const features=[...new Set(candidates.flatMap(c=>c.features))];
    return {id:observation.id,timestamp:observation.timestamp,candidates,
      confidence:"experimental",calibratedProbability:false,reason:"relative_zone_scores",
      features,wifiAbsoluteAccepted,quality:Math.max(0,Math.min(1,observation.quality??1)),featureTimes:Object.fromEntries(features.map(f=>[f,f==="wifi" ? observation.wifi.timestamp:f==="ble"?observation.ble.timestamp:observation.timestamp]))};
  }
  return {fromLegacy,classify};
});
