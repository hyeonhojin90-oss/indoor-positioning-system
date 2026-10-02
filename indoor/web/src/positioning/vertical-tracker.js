(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.IndoorVertical = factory();
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";
  const median = xs => [...xs].sort((a,b)=>a-b)[Math.floor(xs.length/2)];
  function create(floor) { return {floor,baseline:null,baselineSamples:[],samples:[],lastTime:-Infinity,
    candidate:null,candidateSince:null,status:"baseline",offset:0,transition:false}; }
  function update(previous, time, pressure, context={}) {
    if (!Number.isFinite(time) || time<=previous.lastTime || !Number.isFinite(pressure) || pressure<800 || pressure>1100) return previous;
    const s={...previous,lastTime:time,transition:false};
    s.samples=[...s.samples,{time,pressure}].filter(p=>time-p.time<=2500);
    if (s.baseline===null) {
      s.baselineSamples=[...s.baselineSamples,{time,pressure}].filter(p=>time-p.time<=4000);
      const values=s.baselineSamples.map(p=>p.pressure);
      if (values.length>=5 && time-s.baselineSamples[0].time>=1000 && Math.max(...values)-Math.min(...values)<0.08) {
        s.baseline=median(values); s.status="stable";
      }
      return s;
    }
    s.offset=(s.baseline-median(s.samples.map(p=>p.pressure)))/0.44;
    const delta=Math.round(s.offset);
    const spread=Math.max(...s.samples.map(p=>p.pressure))-Math.min(...s.samples.map(p=>p.pressure));
    const candidate=s.floor+delta;
    const reset=status=>({...s,status,candidate:null,candidateSince:null});
    if (context.withinFloor) return reset("within_floor_elevation");
    if (Math.abs(s.offset)<0.7) return reset("stable");
    if (!context.atConnector) return reset("unconfirmed_vertical_location");
    if (candidate<1 || candidate>10) return reset("outside_floor_range");
    if (s.candidate!==candidate) {s.candidate=candidate;s.candidateSince=time;}
    s.status=context.stepsRecent ? "stairs_candidate" : "elevator_or_pressure_candidate";
    // Require a stable landing interval, not a count of callbacks. No auto stop.
    if (time-s.candidateSince>=3000 && spread<0.10 && Math.abs(s.offset-delta)<0.20 && s.samples.length>=3) {
      s.floor=candidate; s.baseline=median(s.samples.map(p=>p.pressure)); s.offset=0;
      s.transition=true;s.status="floor_change_candidate_accepted";s.candidate=null;s.candidateSince=null;
    }
    return s;
  }
  return {create,update};
});
