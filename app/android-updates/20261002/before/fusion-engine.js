(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory(require("./navigation"),require("./vertical-tracker"));
  else root.IndoorFusion = factory(root.IndoorNavigation,root.IndoorVertical);
})(typeof globalThis !== "undefined" ? globalThis : this, function (Nav,Vertical) {
  "use strict";
  const VERSION="fusion-v3-scope-meters-20261002";
  const coordX=(map,x)=>map.coordinateSystem==='meters'?Nav.metricDistance(map.sourceMap,x):x;
  const coreX=map=>coordX(map,70.804);
  const oldLength=(map,value)=>value*(map.coordinateSystem==='meters'?map.legacyScale:1);
  function physicalGap(map,a,b){
    const point=p=>map.coordinateSystem==='meters'?{x:p.x,y:p.y||0}:Nav.toMeters(map,{x:p.x,y:p.y||0});
    const p=point(a),q=point(b);return Math.hypot(p.x-q.x,p.y-q.y);
  }
  // The 4F surveyed endpoint is the main-corridor line immediately before the
  // stair entrance.  Keep a safe fallback because landmarks are also rendered
  // by diagnostic callers which intentionally pass no display-map list.
  const rightStairX=map=>map?.distanceMetric?.mapBreaks?.[0] ?? map?.right_stair_entry_map_x ?? 0;
  const leftStairX=map=>map?.distanceMetric?.mapBreaks?.at(-1) ?? 135.407;
  // A local walking-direction prior, not a global wall or a forced route.
  // Perpendicular turns and mapped open/extension areas retain full 2D motion.
  function corridorAxis(heading) {
    const delta=((heading-355+540)%360)-180;
    return {delta,deviation:Math.min(Math.abs(delta),180-Math.abs(delta)),direction:Math.cos(delta*Math.PI/180)>=0?-1:1};
  }
  function corridorMotion(map, from, to, heading, direction=null) {
    const ids=["main_right","main_left","core_junction","stairs_right","stairs_left"];
    const area=Nav.areaAt(map,from);
    // Only explicitly marked straight segments; open connectors retain 2D motion.
    // Direction is local to this axis, never inherited from the main corridor.
    if(area?.motion_axis==='y') {
      const angle=(heading-355)*Math.PI/180, along=-Math.sin(angle);
      if(Math.abs(along)<.5)return {to,aligned:false};
      const metric=map.extensionMotionMetric;
      const length=Math.hypot((to.x-from.x)*(metric?.xMetersPerUnit||1),(to.y-from.y)*(metric?.yMetersPerUnit||1))/(metric?.yMetersPerUnit||1);
      const center=(area.rect[0]+area.rect[2])/2;
      return {to:{x:center+(from.x-center)*.5,y:from.y+Math.sign(along)*length},aligned:true};
    }
    if(area && !ids.includes(area.id))return {to,aligned:false};
    const corridor=area || map.areas.find(a=>ids.includes(a.id)
      &&from.x>=a.rect[0]&&from.x<=a.rect[2]
      &&from.y>=a.rect[1]-1.5&&from.y<=a.rect[3]+1.5);
    const axis=corridorAxis(heading),delta=axis.delta;
    const main=area && ["main_left","main_right"].includes(area.id);
    // A confirmed main-corridor direction is a route-state signal. Phone yaw
    // must not turn that state into lateral map motion. Registered portals can
    // still create branch particles before this proposal is selected.
    if(!corridor || (!main && axis.deviation>35) || (main && direction===null && axis.deviation>85))return {to,aligned:false};
    const length=Math.hypot(to.x-from.x,to.y-from.y);
    return {to:{x:Nav.advanceDistance(map,from.x,(direction ?? axis.direction)*length),y:from.y*.5},aligned:true};
  }
  function stride(base, cadence, peak, model,units='map_units') {
    // No fitted/validated personal model yet: never assume faster means longer.
    if (!model?.validated || model.units!==units || !Array.isArray(model.coefficients)
      || model.coefficients.length!==3 || !model.coefficients.every(Number.isFinite)
      || !Number.isFinite(cadence) || !Number.isFinite(peak)) return {length:base,mode:"fixed_baseline_untrained"};
    const [a,b,c]=model.coefficients;
    const prediction=a+b*cadence+c*peak;
    return {length:Math.max(base*.8,Math.min(base*1.2,prediction)),mode:"personal_regression_capped_20pct"};
  }
  function create(data, options={}) {
    const hypotheses=options.hypotheses || [{floor:options.floor,x:options.x,y:options.y || 0,weight:1}];
    if (!hypotheses.length || hypotheses.some(h=>!Number.isInteger(h.floor) || h.floor<1 || h.floor>10 || !Number.isFinite(h.x) || !Number.isFinite(h.y) || !(h.weight>0))) throw new Error("Invalid initial hypotheses");
    const coordinateSystem=options.coordinateSystem || 'legacy';
    const initialMap=Nav.compile(data,hypotheses[0].floor,coordinateSystem);
    const s={version:VERSION,data,maps:{},particles:[],seed:options.seed ?? 173,steps:0,lastStepTime:null,
      coordinateSystem,trackingState:'tracking',pendingFloor:null,stairId:null,lastVerticalEvidence:-Infinity,
      lastZoneTime:-Infinity,lastZoneId:null,lastRadioTime:-Infinity,lastRadioId:null,featureTimes:{},zoneObservation:null,radioObservation:null,reason:"initialized",baseStride:options.baseStride || oldLength(initialMap,70.804/81),
      strideMode:"fixed_baseline_untrained",heading:null,model:options.strideModel || null,
      quality:1,recoveryCandidate:null,lastRecovery:-Infinity,recoveryCount:0,lastSequenceTime:-Infinity,corridorHeadingOffset:0,
      corridorDirection:Number(options.initialDirectionSign)===-1?-1:Number(options.initialDirectionSign)===1?1:null,
      directionCandidate:null,directionCandidateSteps:0,directionCandidateDistance:0};
    const sum=hypotheses.reduce((a,h)=>a+h.weight,0), count=options.count || 160;
    for (let i=0;i<count;i++) {
      const target=(i+.5)/count*sum;let acc=0;
      const h=hypotheses.find(h=>{acc+=h.weight;return acc>=target;}) || hypotheses.at(-1);
      const floorMap=getMap(s,h.floor);
      const proposal={x:h.x+(random(s)-.5)*oldLength(floorMap,1.6),y:h.y+(random(s)-.5)*.5};
      const safe=Nav.transition(floorMap,h,proposal).allowed ? proposal : h;
      s.particles.push({floor:h.floor,x:safe.x,y:safe.y,weight:1/count,scale:.85+random(s)*.3,
        headingBias:(random(s)-.5)*12});
    }
    s.vertical=Vertical.create(hypotheses[0].floor);
    s.verticalFloorKnown=new Set(hypotheses.map(h=>h.floor)).size===1;
    return s;
  }
  function random(s) {s.seed=(Math.imul(s.seed,1664525)+1013904223)>>>0;return s.seed/4294967296;}
  function getMap(s,floor) {return s.maps[floor] || (s.maps[floor]=Nav.compile(s.data,floor,s.coordinateSystem));}
  function normalize(s) {
    const total=s.particles.reduce((a,p)=>a+p.weight,0);
    if (!Number.isFinite(total) || total<=0) throw new Error("Invalid particle weights");
    s.particles.forEach(p=>{p.weight/=total;});
    s.ess=1/s.particles.reduce((a,p)=>a+p.weight*p.weight,0);
  }
  function resample(s) {
    normalize(s);
    if (s.ess>s.particles.length/2) return;
    // Reserve one representative per occupied mapped zone, preserving group mass.
    // This prevents a newly entered branch disappearing in one resampling draw.
    const groups=new Map();
    for(const p of s.particles){const id=`${p.floor}:${Nav.areaAt(getMap(s,p.floor),p)?.id||'unknown'}`;
      if(!groups.has(id))groups.set(id,[]);groups.get(id).push(p);}
    if(groups.size>1 && groups.size<=s.particles.length){
      const n=s.particles.length,entries=[...groups.values()].map(ps=>({ps,mass:ps.reduce((a,p)=>a+p.weight,0),count:1}));
      for(let i=entries.length;i<n;i++)entries.reduce((a,b)=>a.mass/a.count>b.mass/b.count?a:b).count++;
      const out=[];
      for(const g of entries){let j=0,cumulative=g.ps[0].weight;const start=random(s)*g.mass/g.count;
        for(let i=0;i<g.count;i++){while(start+i*g.mass/g.count>cumulative&&j<g.ps.length-1)cumulative+=g.ps[++j].weight;
          out.push({...g.ps[j],weight:g.mass/g.count});}}
      s.particles=out;return;
    }
    const n=s.particles.length, start=random(s)/n, out=[];
    let j=0, cumulative=s.particles[0].weight;
    for (let i=0;i<n;i++) {
      while (start+i/n>cumulative && j<n-1) cumulative+=s.particles[++j].weight;
      out.push({...s.particles[j],weight:1/n});
    }
    s.particles=out;
  }
  function heading(s,value,time,accuracy) {
    if (Number.isFinite(value) && value>=0 && Number.isFinite(time) && (accuracy==null || accuracy>0)) s.heading={value,time};
  }
  function step(s,time,peak,quality=1,strideRatio=null) {
    if (!Number.isFinite(time) || (s.lastStepTime!==null && time<=s.lastStepTime)) return;
    const cadence=s.lastStepTime===null ? null : 1000/(time-s.lastStepTime);
    s.steps++;s.lastStepTime=time;
    if(s.trackingState!=='tracking'){
      s.reason='vertical_tracking_planar_paused';return;
    }
    s.quality=Math.max(0,Math.min(1,quality));
    if(s.quality===0){s.reason="rejected_step_quality";return;}
    // Android forwards accelerometer sample time and heading callback time through
    // separate queues. A heading a few milliseconds newer than the step is still
    // the same walking direction; reject only a material future mismatch.
    if (!s.heading || time-s.heading.time>4000 || s.heading.time-time>250) {s.reason="heading_unavailable";return;}
    const estimate=Number.isFinite(strideRatio)&&strideRatio>0
      ?{length:s.baseStride*Math.max(.65,Math.min(1.35,strideRatio)),mode:'weinberg_experimental'}
      :stride(s.baseStride,cadence,peak,s.model,s.coordinateSystem==='meters'?'meters':'map_units');s.strideMode=estimate.mode;
    // Learn only small, near-axis bias while most mass is in a mapped main corridor.
    // Do not learn a perpendicular turn as a new corridor direction.
    const axisError=(((s.heading.value-355+90)%180+180)%180)-90;
    const corridorMass=s.particles.filter(p=>["main_left","main_right"].includes(Nav.areaAt(getMap(s,p.floor),p)?.id))
      .reduce((sum,p)=>sum+p.weight,0);
    if(corridorMass>.65 && Math.abs(axisError)<=35)
      s.corridorHeadingOffset=.85*s.corridorHeadingOffset+.15*axisError;
    const axis=corridorAxis(s.heading.value-s.corridorHeadingOffset);
    let movementLength=estimate.length;
    if(corridorMass>.35 && axis.deviation<=45){
      if(s.corridorDirection===null)s.corridorDirection=axis.direction;
      else if(axis.direction===s.corridorDirection){
        movementLength+=s.directionCandidateDistance;
        s.directionCandidate=null;s.directionCandidateSteps=0;s.directionCandidateDistance=0;
      }
      else {
        if(s.directionCandidate===axis.direction){s.directionCandidateSteps++;s.directionCandidateDistance+=estimate.length;}
        else {s.directionCandidate=axis.direction;s.directionCandidateSteps=1;s.directionCandidateDistance=estimate.length;}
        // Require a sustained, near-axis reversal. A tilted phone alone does
        // not reverse the corridor progress state. Candidate steps are held so
        // they cannot first move in the old direction and then be counted again.
        if(s.directionCandidateSteps>=3){
          s.corridorDirection=axis.direction;movementLength=s.directionCandidateDistance;
          s.directionCandidate=null;s.directionCandidateSteps=0;s.directionCandidateDistance=0;
        } else {s.reason="direction_change_pending";return;}
      }
    } else if(s.directionCandidateSteps>0){
      // A candidate that is not sustained is treated as phone yaw. Restore its
      // held distance on the already confirmed corridor direction.
      movementLength+=s.directionCandidateDistance;
      s.directionCandidate=null;s.directionCandidateSteps=0;s.directionCandidateDistance=0;
    }
    let blockedMass=0,unknownMass=0,scopeMass=0,branchProposals=0;
    for (const [index,p] of s.particles.entries()) {
      const angle=(s.heading.value-355+p.headingBias+(random(s)-.5)*(10+20*(1-s.quality)))*Math.PI/180;
      const map=getMap(s,p.floor),area=Nav.areaAt(map,p);
      // In a confirmed straight corridor, uncertainty in position must not
      // silently turn into a different stride for each particle.
      const mainCorridor=area && ["main_left","main_right"].includes(area.id);
      const constrainedAxis=mainCorridor || area?.motion_axis;
      const length=movementLength*(constrainedAxis ? 1 : p.scale);
      const metric=map.extensionMotionMetric;
      const upperMotion=metric && p.y>=1.17;
      const raw={x:p.x-Math.cos(angle)*length*(upperMotion?metric.legacyStepMeters/metric.xMetersPerUnit:1),
        y:p.y-Math.sin(angle)*length*(upperMotion?metric.legacyStepMeters/metric.yMetersPerUnit:1)};
      const aligned=corridorMotion(getMap(s,p.floor),p,raw,s.heading.value-s.corridorHeadingOffset,s.corridorDirection);
      const branches=Nav.branchMoves(getMap(s,p.floor),p,length,s.heading.value);
      const branch=branches.length && index%3===0 ? branches[Math.floor(index/3)%branches.length] : null;
      // Retain a corridor hypothesis at connectors without suppressing genuine turns.
      const axisDelta=(((s.heading.value-355+90)%180+180)%180)-90;
      const connector=area && ["stairs_right","stairs_left","core_junction"].includes(area.id);
      const entryDirection=s.corridorDirection ?? (Math.cos(angle)>=0?-1:1);
      const towardCorridor=area?.id==='stairs_right'?entryDirection===1:area?.id==='stairs_left'?entryDirection===-1:true;
      const keepEntry=!aligned.aligned && connector && towardCorridor
        && (s.corridorDirection!==null || Math.abs(axisDelta)<=70) && index%3!==0;
      const entryTo={x:Nav.advanceDistance(map,p.x,entryDirection*length),y:p.y*.5};
      const to=branch ? branch.to : keepEntry ? entryTo : aligned.to;
      if(branch){branchProposals++;p.weight*=branch.weight;}
      const verdict=Nav.transition(getMap(s,p.floor),p,to);
      if (!verdict.allowed) {
        if(verdict.reason==='outside_tracking_scope')scopeMass+=p.weight;
        else blockedMass+=p.weight;
        p.weight*=.15;continue;
      }
      if (verdict.reason.startsWith("unverified")) unknownMass+=p.weight;
      p.x=to.x;p.y=to.y;p.weight*=verdict.weight;
    }
    s.scopeMass=scopeMass;
    s.reason=scopeMass>.5?'outside_tracking_scope':blockedMass>.8 ? "recovery_required_wall" : unknownMass>.5 ? "unverified_area" : "tracking";
    s.branchProposals=branchProposals;s.blockedMass=blockedMass;resample(s);
  }
  function observeZone(s,observation,now) {
    if(s.trackingState!=='tracking')return false;
    if (!observation?.candidates?.length || !Number.isFinite(observation.timestamp)
      || observation.timestamp<=s.lastZoneTime || observation.id===s.lastZoneId
      || now-observation.timestamp>5000 || observation.timestamp>now) return false;
    // Conservatively skip a mixed observation if one modality was already consumed.
    // A cached WiFi scan must not become multiple independent votes via new event IDs.
    const times=observation.featureTimes || {};
    if (Object.entries(times).some(([feature,time])=>time <= (s.featureTimes[feature] ?? -Infinity))) return false;
    Object.assign(s.featureTimes,times);
    s.lastZoneTime=observation.timestamp;s.lastZoneId=observation.id;s.zoneObservation=observation;
    const weights=new Map(observation.candidates.map(c=>[`${c.floor}:${c.zone}`,c.weight]));
    for (const p of s.particles) {
      const area=Nav.areaAt(getMap(s,p.floor),p);
      // Relative zone score is used ONCE. No second magnetic likelihood on the same window.
      // Unobserved zones remain possible; absence of iOS AP access is not negative evidence.
      const w=weights.get(`${p.floor}:${area?.id}`);
      p.weight*=Math.pow(.25+.75*(Number.isFinite(w) ? w : 1/weights.size),.3*(observation.quality??1));
    }
    resample(s);return true;
  }
  function corridorCompatible(current,candidate) {
    if(current==='main_right')return ['main_right','core_junction','stairs_right'].includes(candidate);
    if(current==='main_left')return ['main_left','core_junction','stairs_left'].includes(candidate);
    return true;
  }
  function observeRadio(s,observation,now) {
    if(s.trackingState!=='tracking')return false;
    if(!observation?.features?.includes('ble')||!observation.candidates?.length||!Number.isFinite(observation.timestamp)
      ||observation.timestamp<=s.lastRadioTime||observation.id===s.lastRadioId
      ||now-observation.timestamp>5000||observation.timestamp>now)return false;
    const scan=observation.featureTimes?.ble;
    if(!Number.isFinite(scan)||scan<=(s.featureTimes.ble??-Infinity))return false;
    const view=snapshot(s),map=getMap(s,view.floor);
    const candidates=observation.candidates.filter(c=>c.floor===view.floor&&corridorCompatible(view.zone,c.zone)&&Number.isFinite(c.anchor?.x)
      &&physicalGap(map,c.anchor,view)<=12);
    if(!candidates.length){s.observationReason='ble_outside_pdr_gate';return false;}
    s.featureTimes.ble=scan;s.lastRadioTime=observation.timestamp;s.lastRadioId=observation.id;
    s.radioObservation={...observation,candidates};
    // BLE fingerprint similarity is area evidence, not an exact-position fix.
    // A sole candidate's normalized weight=1 must never create new positions.
    for(const p of s.particles){
      if(p.floor!==view.floor)continue;
      const likelihood=candidates.reduce((sum,c)=>{
        const sigma=Math.max(4,c.anchor.sigma_m||6);
        return sum+c.weight*Math.exp(-.5*(physicalGap(map,p,c.anchor)/sigma)**2);
      },0);
      p.weight*=Math.pow(.2+.8*likelihood,.35*(observation.quality??1));
    }
    resample(s);s.reason='tracking_ble_soft';return true;
  }
  function observeWifi(s,observation,now) {
    if(s.trackingState!=='tracking')return false;
    if(!observation?.features?.includes('wifi')||!observation.candidates?.length||!Number.isFinite(observation.timestamp)
      ||observation.timestamp<=s.lastZoneTime||observation.id===s.lastZoneId
      ||now-observation.timestamp>5000||observation.timestamp>now)return false;
    if(observation.wifiAbsoluteAccepted!==true){s.observationReason='wifi_unknown_or_unqualified';return false;}
    const scan=observation.featureTimes?.wifi;
    if(!Number.isFinite(scan)||scan<=(s.featureTimes.wifi??-Infinity))return false;
    const view=snapshot(s),map=getMap(s,view.floor);
    const candidates=observation.candidates.filter(c=>c.floor===view.floor&&corridorCompatible(view.zone,c.zone)&&Number.isFinite(c.anchor?.x)
      &&Number.isFinite(c.wifiScore)&&c.wifiScore<=4&&physicalGap(map,c.anchor,view)<=15);
    if(!candidates.length){s.zoneObservation=null;s.observationReason='wifi_outside_pdr_gate';return false;}
    s.featureTimes.wifi=scan;s.lastZoneTime=observation.timestamp;s.lastZoneId=observation.id;
    s.zoneObservation={...observation,candidates};
    // A single scan only reweights existing support. It does not reseed a point.
    // Unknown/unmeasured areas are neutral, not negative AP evidence.
    for(const p of s.particles){
      if(p.floor!==view.floor)continue;
      if(!candidates.some(c=>physicalGap(map,p,c.anchor)<=15))continue;
      const likelihood=candidates.reduce((sum,c)=>{
        const sigma=Math.max(4,c.anchor.sigma_m||6);
        return sum+c.weight*Math.exp(-.5*(physicalGap(map,p,c.anchor)/sigma)**2);
      },0);
      p.weight*=1+.2*likelihood*Math.max(0,Math.min(1,observation.quality??1));
    }
    normalize(s);s.reason='tracking_wifi_anchor_soft';return true;
  }
  function recover(s,observation,now){
    if(s.trackingState!=='tracking')return false;
    if(observation?.wifiAbsoluteAccepted!==true){s.recoveryCandidate=null;return false;}
    const c=observation?.candidates?.[0],second=observation?.candidates?.[1];
    const current=snapshot(s);
    // Only surveyed anchor area + independently repeated fresh AP scans authorize reseeding.
    const trusted=observation?.wifiAbsoluteAccepted===true&&c&&c.anchor?.verified===true&&c.anchor.sources>=3&&Number.isFinite(c.anchor.x)&&Number.isFinite(c.anchor.y)
      &&c.floor===current.floor&&["stairs_right","stairs_left","core_junction","main_entrance"].includes(c.zone)
      &&observation.features?.includes('wifi')&&(observation.quality??0)>=.7&&c.weight>=.8
      &&(!second||c.weight-second.weight>=.3)&&now-s.lastRecovery>15000;
    if(!trusted){s.recoveryCandidate=null;return false;}
    // An AP match in the middle of the corridor can resemble a distant stair/core.
    // Recovery must obey the same physical reachability gate as a soft AP update.
    const map=getMap(s,c.floor);
    if(!corridorCompatible(current.zone,c.zone)
      ||physicalGap(map,c.anchor,current)>15){
      s.recoveryCandidate=null;s.observationReason='wifi_recovery_outside_pdr_gate';return false;
    }
    const scan=observation.featureTimes?.wifi;
    if(!Number.isFinite(scan)||now-scan>5000||scan>now)return false;
    const key=`${c.floor}:${c.zone}`,prev=s.recoveryCandidate;
    if(prev&&scan<=prev.scan)return false;
    const next=prev?.key===key&&scan-prev.scan<=15000?{...prev,scan,count:prev.count+1}:{key,scan,count:1,since:now};
    s.recoveryCandidate=next;
    if(next.count<3||now-next.since<4000)return false;
    const area=Nav.areaAt(map,c.anchor);
    if(!area||area.id!==c.zone)return false;
    // Retain half the old distribution; new hypothesis is not an exact-point teleport.
    const n=Math.floor(s.particles.length/2);
    s.particles.sort((a,b)=>b.weight-a.weight);
    for(let i=0;i<n;i++){
      const x=c.anchor.x+(random(s)-.5)*oldLength(map,1.2),y=c.anchor.y+(random(s)-.5)*.5;
      if(!Nav.contains(area.rect,{x,y}))continue;
      s.particles[s.particles.length-1-i]={floor:c.floor,x,y,weight:1/s.particles.length,scale:1,headingBias:(random(s)-.5)*8};
    }
    normalize(s);s.lastRecovery=now;s.recoveryCount++;s.reason='anchor_recovery';s.recoveryCandidate=null;return true;
  }
  function observeSequence(s,result,time,enabled=false){
    if(s.trackingState!=='tracking')return false;
    s.sequenceReason=result.reason;
    s.sequenceApplicationReason=!enabled?'pattern_disabled':result.reason!=='sequence_candidate'?result.reason
      :time<=s.lastSequenceTime?'stale_sequence':time-s.lastZoneTime<2000?'recent_zone_observation':null;
    if(s.sequenceApplicationReason)return false;
    const c=result.candidates[0];if(!c||!Number.isFinite(c.x)){s.sequenceApplicationReason='invalid_candidate';return false;}
    // Templates currently describe main-corridor x only, not extension coordinates.
    const view=snapshot(s);
    if(!['main_right','main_left','core_junction','stairs_right','stairs_left'].includes(view.zone)){
      s.sequenceApplicationReason='unsupported_sequence_area';return false;
    }
    const map=getMap(s,view.floor);
    if(c.floor!==view.floor||Math.abs(Nav.metricDistance(map,c.x)-Nav.metricDistance(map,view.x))>12){s.sequenceApplicationReason='outside_pdr_gate';return false;}
    s.lastSequenceTime=time;
    for(const p of s.particles)if(p.floor===c.floor)p.weight*=.5+.5*Math.exp(-(((p.x-c.x)/oldLength(map,8))**2)/2);
    resample(s);s.sequenceApplicationReason='applied';return true;
  }
  // Experimental 4F magnetic-grid observation. The caller must establish
  // platform, corridor, calibration and uniqueness before proposing a point.
  // Bounded local proposals and weighting, restricted to the named corridor.
  function observeMagneticGrid(s,coreDistanceM,lengthM,time,corridor='main_right'){
    if(s.trackingState!=='tracking')return false;
    if(!Number.isFinite(coreDistanceM)||!Number.isFinite(lengthM)||!Number.isFinite(time)
      ||coreDistanceM<0||coreDistanceM>lengthM||time<=(s.lastMagneticGridTime??-Infinity))return false;
    const view=snapshot(s),map=getMap(s,view.floor);
    if(!['main_right','main_left'].includes(corridor)||view.floor!==4||view.zone!==corridor)return false;
    const left=corridor==='main_left',distanceAt=x=>left?Nav.metricDistance(map,x)-Nav.metricDistance(map,coreX(map)):lengthM-Nav.metricDistance(map,x);
    const current=distanceAt(view.x);
    if(Math.abs(current-coreDistanceM)>12)return false;
    s.lastMagneticGridTime=time;
    // Weighting alone cannot recover distance when resampling has removed all
    // nearby support. A small proposal is allowed only within 6 m of PDR.
    if(Math.abs(current-coreDistanceM)<=6){
      let lo=left?coreX(map):rightStairX(map),hi=left?leftStairX(map):coreX(map);
      for(let i=0;i<24;i++){const mid=(lo+hi)/2;
        if(left?distanceAt(mid)<coreDistanceM:distanceAt(mid)>coreDistanceM)lo=mid;else hi=mid;}
      const target=(lo+hi)/2,count=Math.floor(s.particles.length*.08);
      for(let i=0;i<count;i++){
        const x=target+(random(s)-.5)*oldLength(map,1.2),y=(random(s)-.5)*.25;
        if(Nav.areaAt(map,{x,y})?.id===corridor)
          s.particles[s.particles.length-1-i]={floor:4,x,y,weight:1/s.particles.length,scale:1,headingBias:(random(s)-.5)*8};
      }
      normalize(s);
    }
    for(const p of s.particles){
      if(p.floor!==4)continue;
      const area=Nav.areaAt(map,p);
      if(area?.id!==corridor)continue;
      const distance=distanceAt(p.x);
      p.weight*=.6+.4*Math.exp(-.5*((distance-coreDistanceM)/3)**2);
    }
    resample(s);s.reason='tracking_magnetic_grid_soft';return true;
  }
  function pressure(s,time,value) {
    if (!s.verticalFloorKnown) {s.vertical.status="initial_floor_ambiguous";return;}
    const view=snapshot(s), map=getMap(s,view.floor);
    const connectorMass=s.particles.filter(p=>p.floor===view.floor && Nav.areaAt(map,p)?.vertical).reduce((a,p)=>a+p.weight,0);
    const withinMass=s.particles.filter(p=>p.floor===view.floor && Nav.areaAt(map,p)?.within_floor).reduce((a,p)=>a+p.weight,0);
    const stairMass=s.particles.filter(p=>p.floor===view.floor && ['stairs_left','stairs_right'].includes(Nav.areaAt(map,p)?.id)
      ||p.floor===view.floor&&Nav.areaAt(map,p)?.id==='core'&&p.y<=-(map.stairPolicy?.coreEntryDepthM || Infinity)).reduce((a,p)=>a+p.weight,0);
    s.vertical=Vertical.update(s.vertical,time,value,{atConnector:connectorMass>=.65,withinFloor:withinMass>.2,
      stepsRecent:s.lastStepTime!==null && time-s.lastStepTime<3000});
    if(map.stairPolicy && stairMass>=.65 && Math.abs(s.vertical.offset)>=.7 && s.trackingState==='tracking'){
      s.trackingState='vertical_moving';s.stairId=view.zone==='core'?'stairs_main':view.zone;
      s.directionCandidate=null;s.directionCandidateSteps=0;s.directionCandidateDistance=0;
    }
    if (s.vertical.transition) {
      if(map.stairPolicy){
        s.pendingFloor=s.vertical.floor;s.trackingState='vertical_floor_pending';
        s.reason='landing_candidate_needs_exit_or_beacon';return;
      }
      // Preserve XY uncertainty. Do not snap to the nearest connector by distance alone.
      s.particles.forEach(p=>{p.floor=s.vertical.floor;});s.reason="experimental_floor_transition";
    }
  }
  // Entry/exit evidence must come from a verified doorway/beacon or an explicit
  // user confirmation. A landing pause alone never confirms the floor.
  function verticalEvidence(s,evidence,time){
    if(!Number.isFinite(time)||evidence?.verified!==true||time<=s.lastVerticalEvidence
      ||time<(s.lastStepTime??-Infinity)||time<s.vertical.lastTime)return false;
    const view=snapshot(s),map=getMap(s,view.floor);
    if(evidence.entryConfirmed){
      const area=Nav.areaAt(map,view);
      if(!area?.vertical)return false;
      s.lastVerticalEvidence=time;s.trackingState='vertical_moving';s.stairId=evidence.stairId || area.id;return true;
    }
    if(s.trackingState==='tracking')return false;
    const floor=Number.isInteger(evidence.beaconFloor)?evidence.beaconFloor:evidence.exitConfirmed?s.pendingFloor:null;
    if(!Number.isInteger(floor)||floor<1||floor>10)return false;
    const targetMap=getMap(s,floor),source=map.coordinateSystem==='meters'?map.sourceMap:map;
    const oldPoint=map.coordinateSystem==='meters'?Nav.fromMeters(source,view):view;
    const point=targetMap.coordinateSystem==='meters'?Nav.toMeters(targetMap.sourceMap,oldPoint):oldPoint;
    if(!Nav.areaAt(targetMap,point))return false;
    s.particles.forEach(p=>{
      const old=map.coordinateSystem==='meters'?Nav.fromMeters(source,p):p;
      const q=targetMap.coordinateSystem==='meters'?Nav.toMeters(targetMap.sourceMap,old):old;
      p.x=q.x;p.y=q.y;p.floor=floor;
    });
    s.lastVerticalEvidence=time;s.vertical=Vertical.create(floor);s.pendingFloor=null;s.trackingState='tracking';
    s.corridorDirection=null;s.directionCandidate=null;s.directionCandidateSteps=0;s.directionCandidateDistance=0;
    s.heading=null;s.corridorHeadingOffset=0;s.stairId=null;
    s.reason='floor_confirmed_needs_exit_position';return true;
  }
  function snapshot(s) {
    normalize(s);
    const groups=new Map(), floors=new Map();
    for (const p of s.particles) {
      const area=Nav.areaAt(getMap(s,p.floor),p), id=`${p.floor}:${area?.id || "unknown"}`;
      if (!groups.has(id)) groups.set(id,{floor:p.floor,zone:area?.id || "unknown",label:area?.label || "미확인 영역",weight:0,points:[]});
      const g=groups.get(id);g.weight+=p.weight;g.points.push(p);
      floors.set(p.floor,(floors.get(p.floor)||0)+p.weight);
    }
    const ordered=[...groups.values()].sort((a,b)=>b.weight-a.weight), top=ordered[0];
    // Pool only adjacent modes on the same confirmed straight corridor, never rooms/floors.
    const corridorIds=['stairs_right','main_right','core_junction','main_left','stairs_left'];
    const center=g=>g.points.reduce((a,p)=>a+p.x*p.weight,0)/g.weight;
    const selected=corridorIds.includes(top.zone)?ordered.filter(g=>g.floor===top.floor&&corridorIds.includes(g.zone)&&Math.abs(center(g)-center(top))<=oldLength(getMap(s,top.floor),12)):[top];
    const points=selected.flatMap(g=>g.points),mass=selected.reduce((a,g)=>a+g.weight,0);
    const x=points.reduce((a,p)=>a+p.x*p.weight,0)/mass;
    const y=points.reduce((a,p)=>a+p.y*p.weight,0)/mass;
    const spread=Math.sqrt(points.reduce((a,p)=>a+((p.x-x)**2+(p.y-y)**2)*p.weight,0)/mass);
    const displayArea=Nav.areaAt(getMap(s,top.floor),{x,y});
    return {version:VERSION,coordinateSystem:s.coordinateSystem,positionUnits:s.coordinateSystem==='meters'?'m':'legacy_map_units',trackingState:s.trackingState,pendingFloor:s.pendingFloor,stairId:s.stairId,
      scopeStatus:s.scopeMass>.5?'outside_tracking_scope':'inside_or_unchecked',floor:top.floor,x,y,zone:displayArea?.id||top.zone,zoneLabel:displayArea?.label||top.label,spread,displayMass:mass,
      modeWeight:top.weight,calibratedProbability:false,reason:s.reason,steps:s.steps,strideMode:s.strideMode,
      hypotheses:ordered.map(({points,...rest})=>rest).slice(0,5),floorCandidates:[...floors].map(([floor,weight])=>({floor,weight})),
      verticalStatus:s.vertical?.status || "baseline",zoneEvidence:s.zoneObservation?.features || [],radioEvidence:s.radioObservation?.features || [],
      zoneHypotheses:(s.zoneObservation?.candidates||[]).slice(0,3).map(c=>({floor:c.floor,zone:c.zone,
        anchorId:c.anchor?.id||null,anchorLabel:c.anchor?.label||null,weight:c.weight,score:c.score,features:c.features||[]})),
      radioHypotheses:(s.radioObservation?.candidates||[]).slice(0,3).map(c=>({floor:c.floor,zone:c.zone,
        anchorId:c.anchor?.id||null,anchorLabel:c.anchor?.label||null,weight:c.weight,score:c.score,features:c.features||[]})),
      observationReason:s.observationReason || "not_observed",particleCount:s.particles.length,
      motionQuality:s.quality,branchProposals:s.branchProposals||0,corridorHeadingOffset:s.corridorHeadingOffset,
      corridorDirection:s.corridorDirection,directionCandidate:s.directionCandidate,
      directionCandidateSteps:s.directionCandidateSteps,recoveryCount:s.recoveryCount,sequenceReason:s.sequenceReason||'sequence_warmup'};
  }
  function landmarks(s,maps=[]) {
    const view=snapshot(s), map=maps.find(m=>Number(m.floor)===view.floor), metricMap=getMap(s,view.floor);
    if (!["main_left","main_right","core_junction","stairs_left","stairs_right"].includes(view.zone)) return [];
    const observed=Nav.observedLandmarks(s.data,view.floor);
    if(observed.length){
      return observed.map(c=>({...c,x:s.coordinateSystem==='meters'?c.xM:Nav.fromMeters(metricMap,{x:c.xM,y:0}).x,
        distance:Math.abs(c.xM-Nav.metricDistance(metricMap,view.x)),positionBasis:'repeated_lap_alignment_not_surveyed_door'}))
        .sort((a,b)=>a.distance-b.distance).slice(0,3);
    }
    // Native metric mode must not infer classroom-front positions from drawing
    // proportions. Unmapped rooms remain unavailable, rather than fabricated.
    if(s.coordinateSystem==='meters')return [
      {id:'CORE',label:'코어 교차영역',x:coreX(metricMap)},
      {id:'RIGHT_STAIRS',label:'오른쪽 계단 진입 전',x:rightStairX(metricMap)},
      {id:'LEFT_STAIRS',label:'왼쪽 계단 입구',x:leftStairX(metricMap)}
    ].map(c=>({...c,distance:Math.abs(c.x-view.x),positionBasis:'corridor_survey'})).sort((a,b)=>a.distance-b.distance).slice(0,3);
    const candidates=[...(map?.rooms || []).filter(r=>!r.provisional && Number.isFinite(r.front_x ?? r.x))
      .map(r=>({id:r.id,label:r.label || r.id,x:r.front_x ?? r.x})),
      {id:"RIGHT_STAIRS",label:"오른쪽 계단 진입 전",x:rightStairX(map || metricMap)},{id:"LEFT_STAIRS",label:"왼쪽 계단 입구",x:leftStairX(map || metricMap)},
      {id:"CORE",label:"코어 교차영역",x:70.804}];
    return candidates.map(c=>({...c,distance:Math.hypot(c.x-view.x,view.y)})).sort((a,b)=>a.distance-b.distance).slice(0,3);
  }
  return {VERSION,create,heading,step,observeZone,observeRadio,observeWifi,pressure,snapshot,landmarks,stride,recover,observeSequence,observeMagneticGrid,corridorMotion,verticalEvidence};
});
