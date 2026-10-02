(function(root,factory){if(typeof module==='object'&&module.exports)module.exports=factory(require('./fusion-engine'),require('./zone-classifier'),require('./sequence'),require('./quality'),require('./navigation'));
else root.IndoorRuntime=factory(root.IndoorFusion,root.IndoorZones,root.IndoorSequence,root.IndoorQuality,root.IndoorNavigation);})(globalThis,function(F,Z,S,Q,Nav){
  'use strict';
  const median=a=>{const b=a.filter(Number.isFinite).sort((x,y)=>x-y);return b.length?(b[(b.length-1)>>1]+b[b.length>>1])/2:null;};
  function gridDistance(r){const s=F.snapshot(r.engine),map=Nav.compile(r.engine.data,4,r.engine.coordinateSystem);
    const core=map.coordinateSystem==='meters'?map.coreX:70.804;
    return {snapshot:s,distance:r.magneticGrid.coordinate.corridor==='main_left'?Nav.metricDistance(map,s.x)-Nav.metricDistance(map,core):r.magneticGrid.coordinate.lengthM-Nav.metricDistance(map,s.x)};}
  function gridCell(r,d){const cells=r.magneticGrid?.platforms?.[r.platform]?.norm;
    if(!Array.isArray(cells)||!Number.isFinite(d))return null;
    const index=Math.round(d/r.magneticGrid.coordinate.gridStepM);return cells[index]||null;}
  function magneticGridStep(r,time,value){
    const stats=r.magneticGridStats;stats.evaluated++;
    if(!Number.isFinite(value)){stats.reasons.no_magnetic_sample++;return;}
    const position=gridDistance(r),length=r.magneticGrid.coordinate.lengthM;
    if(position.snapshot.floor!==4||position.snapshot.zone!==(r.magneticGrid.coordinate.corridor||'main_right')){
      stats.reasons.outside_corridor++;r.gridWindow=[];return;
    }
    const source=gridCell(r,position.distance);
    if(r.gridOffset===null){
      if(source&&source.sessions>=2&&Number.isFinite(source.mean))r.gridCalibration.push(value-source.mean);
      if(r.gridCalibration.length===8)r.gridOffset=median(r.gridCalibration);
      stats.reasons.calibrating++;return;
    }
    r.gridWindow.push(value-r.gridOffset);
    if(r.gridWindow.length<4)return;
    const window=r.gridWindow;r.gridWindow=[];
    const sign=(r.engine.corridorDirection===-1?1:-1)*(r.magneticGrid.coordinate.corridor==='main_left'?-1:1);
    const strideM=r.magneticGrid.coordinate.strideM||length/81,spacing=r.magneticGrid.coordinate.gridStepM;
    const candidates=[];
    for(let d=Math.max(0,position.distance-12);d<=Math.min(length,position.distance+12);d+=spacing){
      let score=0,valid=true;
      for(let j=0;j<4;j++){
        const cell=gridCell(r,d-sign*(3-j)*strideM);
        if(!cell||cell.sessions<2||!Number.isFinite(cell.mean)){valid=false;break;}
        score+=(window[j]-cell.mean)**2/Math.max(16,cell.variance||0);
      }
      if(valid)candidates.push({distance:d,score:score/4});
    }
    candidates.sort((a,b)=>a.score-b.score);
    const best=candidates[0],other=best&&candidates.find(c=>Math.abs(c.distance-best.distance)>=3);
    if(!best){stats.reasons.no_reference++;return;}
    // Weak, broad magnetic peaks should not displace an otherwise stable PDR.
    if(!other||best.score>1.5||other.score-best.score<.3){stats.reasons.ambiguous++;return;}
    if(F.observeMagneticGrid(r.engine,best.distance,length,time,r.magneticGrid.coordinate.corridor||'main_right')){
      stats.applied++;stats.reasons.applied++;r.lastGridAppliedStep=r.engine.steps;
    }
    else stats.reasons.rejected_by_particle_gate++;
  }
  function coordinates(data,point,floor){return Nav.toMeters(Nav.compile(data,floor),point);}
  function convertObservation(r,observation){
    if(r.engine.coordinateSystem!=='meters')return observation;
    return {...observation,candidates:observation.candidates.map(c=>({...c,
      ...(Number.isFinite(c.x)?coordinates(r.engine.data,c,c.floor):{}),
      anchor:c.anchor&&Number.isFinite(c.anchor.x)?{...c.anchor,...coordinates(r.engine.data,c.anchor,c.floor),coordinateSystem:'meters'}:c.anchor}))};
  }
  function create(data,models,references,options){
    if(options.coordinateSystem==='meters'&&options.inputCoordinates==='legacy'){
      options={...options,...coordinates(data,{x:options.x,y:options.y||0},options.floor),
        ...(options.hypotheses?{hypotheses:options.hypotheses.map(h=>({...h,...coordinates(data,h,h.floor)}))}:{}),
        ...(Number.isFinite(options.baseStride)?{baseStride:options.baseStride*Nav.compile(data,options.floor).distanceMetric.metersPerLegacyUnit}:{})};
    }
    return {engine:F.create(data,{...options,strideModel:models.strideModels?.[options.platform]}),
    models,references,platform:options.platform,device:options.device,mag:[],stepMag:[],sequence:[],intervals:[],lastStep:null,lastMagWindow:null,
    verticalSequenceEnabled:options.verticalSequenceEnabled===true,gravityVector:null,gravityVectorTime:null,stepVertical:[],sequenceVertical:[],
    wifi:null,lastWifiTimestamp:-Infinity,ble:[],lastBleWindow:-Infinity,bleStats:{evaluated:0,applied:0,reasons:{}},sequenceStats:{evaluated:0,applied:0,reasons:{}},
    magneticGrid:options.magneticGridEnabled===true?options.magneticGrid||null:null,
    magneticGridStats:{evaluated:0,applied:0,reasons:{no_magnetic_sample:0,outside_corridor:0,calibrating:0,no_reference:0,ambiguous:0,applied:0,rejected_by_particle_gate:0}},
    gridCalibration:[],gridOffset:null,gridWindow:[],lastGridAppliedStep:-Infinity,
    // A researcher may explicitly enable the guarded sequence branch for an A/B trial.
    // The default remains disabled until the model itself is validated.
    magneticZoneEnabled:options.magneticGridEnabled===true?false:options.magneticZoneEnabled!==false,
    bleEnabled:options.bleEnabled===true,
    sequenceEnabled:options.magneticGridEnabled===true?options.sequenceFallbackEnabled===true:
      options.sequenceEnabled===true || (options.sequenceEnabled!==false&&models.sequenceValidated===true),
    weinbergModel:options.weinbergModel||null,
    detector:{gravity:null,time:null,previous:0,rising:false,peak:0,peakTime:0,lastStep:-Infinity,valley:Infinity}};}
  function acceleration(r,time,values){
    if(Number.isFinite(time)&&values.slice(0,3).every(Number.isFinite)&&
      (r.gravityVectorTime===null||time>r.gravityVectorTime)){
      const a=r.gravityVectorTime===null?1:1-Math.exp(-Math.max(.001,Math.min(.2,(time-r.gravityVectorTime)/1000)));
      r.gravityVector=r.gravityVector?r.gravityVector.map((v,i)=>v+a*(values[i]-v)):values.slice(0,3);r.gravityVectorTime=time;
    }
    const d=r.detector,v=Math.hypot(...values.slice(0,3));if(!Number.isFinite(v)||time<=d.time)return false;
    if(d.gravity===null){d.gravity=v;d.time=time;return false;}
    const dt=Math.max(.001,Math.min(.1,(time-d.time)/1000));d.time=time;d.gravity+=dt/.8*(v-d.gravity);
    const dynamic=v-d.gravity;d.valley=Math.min(d.valley,dynamic);let detected=false;
    if(dynamic>d.previous){if(!d.rising||dynamic>d.peak){d.peak=dynamic;d.peakTime=time;}d.rising=true;}
    else if(d.rising){if(d.peak>=1&&d.peakTime-d.lastStep>=280){step(r,time,d.peak,Math.max(.01,d.peak-d.valley));d.valley=dynamic;d.lastStep=d.peakTime;detected=true;}d.rising=false;}
    d.previous=dynamic;return detected;
  }
  function heading(r,time,value,accuracy){F.heading(r.engine,value,time,accuracy);}
  function magnetic(r,time,values){
    const g=r.gravityVector&&Math.hypot(...r.gravityVector);
    if(g>1&&time>=r.gravityVectorTime&&time-r.gravityVectorTime<=250){
      r.stepVertical.push(values.slice(0,3).reduce((s,v,i)=>s+v*r.gravityVector[i]/g,0));
      if(r.stepVertical.length>200)r.stepVertical.shift();
    }
    const value=Math.hypot(...values.slice(0,3));if(!Number.isFinite(value))return;
    r.mag.push(value);r.stepMag.push(value);
    // Bounded buffers even when standing still or callbacks continue in the background.
    if(r.stepMag.length>200)r.stepMag.shift();
    if(r.lastMagWindow===null)r.lastMagWindow=time;
    if(time-r.lastMagWindow<2000)return;
    const quality=Q.magnetic(r.mag);r.mag=[];r.lastMagWindow=time;
    const observation=Z.classify({id:`mag-${time}`,timestamp:time,platform:r.platform,device:r.device,
      magnetic:quality.weight>=.2?quality.median:null,magneticStd:quality.std,quality:quality.weight},r.references,time);
    r.engine.observationReason=quality.weight<.2?quality.reason:observation.reason;
    if(r.magneticZoneEnabled)F.observeZone(r.engine,observation,time);
  }
  function step(r,time,peak,amplitude=null){
    if(r.lastStep!==null&&time<=r.lastStep)return;
    const floor=F.snapshot(r.engine).floor,h=r.engine.heading?.value;
    const direction=Number.isFinite(h)?Math.cos((h-355)*Math.PI/180)>0?'right':'left':null;
    const key=`${floor}:${direction}`;
    if(r.sequenceKey!==key||(r.lastStep!==null&&time-r.lastStep>3000)){r.sequence=[];r.stepMag=[];r.sequenceVertical=[];r.stepVertical=[];}
    r.sequenceKey=key;
    if(r.lastStep!==null)r.intervals.push(time-r.lastStep);r.intervals=r.intervals.slice(-8);r.lastStep=time;
    const wm=r.weinbergModel,ratio=wm&&Number.isFinite(wm.coefficient)&&wm.coefficient>0&&Number.isFinite(wm.baseMeters)&&wm.baseMeters>0&&Number.isFinite(amplitude)&&amplitude>0?wm.coefficient*Math.pow(amplitude,.25)/wm.baseMeters:null;
    const quality=Q.gait(r.intervals,peak);F.step(r.engine,time,peak,quality.weight,ratio);
    if(r.engine.trackingState!=='tracking'){clearMotionBuffers(r);return;}
    const mag=Q.magnetic(r.stepMag);r.stepMag=[];
    const vertical=median(r.stepVertical);r.stepVertical=[];
    if(r.magneticGrid)magneticGridStep(r,time,mag.weight>=.2?mag.median:null);
    if(mag.weight<.2){r.sequence=[];r.sequenceVertical=[];return;}
    r.sequence.push(mag.median);
    r.sequenceVertical.push(vertical);
    if(r.sequence.length<8)return;
    const view=F.snapshot(r.engine);
    const corridor=['main_left','stairs_left'].includes(view.zone)?'main_left':
      ['main_right','stairs_right'].includes(view.zone)?'main_right':null;
    const result=S.match(r.sequence,r.models.templates||[],{platform:r.platform,device:r.device,floor,direction,corridor,
      verticalValues:r.verticalSequenceEnabled?r.sequenceVertical:null});
    r.sequenceDiagnostic={reason:result.reason,margin:result.margin,applied:false,
      candidates:result.candidates.slice(0,3).map(c=>({x:c.x,score:c.score,floor:c.floor}))};
    r.sequence=[]; // disjoint windows: do not multiply the same samples repeatedly
    r.sequenceVertical=[];
    // One magnetic sample must not vote twice. V2 may fill an eight-step
    // window only if the grid did not correct any step in that window.
    const gridCovered=r.magneticGrid&&r.engine.steps-r.lastGridAppliedStep<8;
    r.sequenceDiagnostic.applied=gridCovered?false:F.observeSequence(r.engine,convertObservation(r,result),time,r.sequenceEnabled);
    r.sequenceDiagnostic.applicationReason=gridCovered?'grid_primary_applied':r.engine.sequenceApplicationReason;
    r.sequenceStats.evaluated++;
    if(r.sequenceDiagnostic.applied)r.sequenceStats.applied++;
    const reason=r.sequenceDiagnostic.applicationReason;
    r.sequenceStats.reasons[reason]=(r.sequenceStats.reasons[reason]||0)+1;
  }
  function wifi(r,time,scan){
    r.wifiDiagnostic={timestamp:scan?.timestamp??null,applied:false,reason:'stale_or_duplicate'};
    if(!scan?.fresh||!Number.isFinite(scan.timestamp)||scan.timestamp<=r.lastWifiTimestamp)return false;
    r.lastWifiTimestamp=scan.timestamp;
    const observation=Z.classify({id:`wifi-${scan.timestamp}`,timestamp:time,platform:r.platform,device:r.device,
      quality:Math.max(.1,Math.min(1,scan.quality??1)),wifi:{supported:true,fresh:true,timestamp:scan.timestamp,rssi:scan.rssi}},r.references,time);
    r.engine.observationReason=observation.reason;
    const used=F.observeWifi(r.engine,convertObservation(r,observation),time);
    r.wifiDiagnostic={timestamp:scan.timestamp,applied:used,reason:used?'accepted':r.engine.observationReason,
      stepsDuringScan:scan.steps_during_scan??null,quality:scan.quality??1};
    if(used)F.recover(r.engine,r.engine.zoneObservation,time);
    return used;
  }
  function ble(r,time,observation){
    if(!r.bleEnabled||!observation?.anonymous_id||!Number.isFinite(observation.rssi_dbm)||!Number.isFinite(time))return false;
    r.ble.push({id:observation.anonymous_id,rssi:observation.rssi_dbm,time});
    r.ble=r.ble.filter(v=>time-v.time<=5000);
    if(time-r.lastBleWindow<3000)return false;r.lastBleWindow=time;
    const grouped=new Map();for(const v of r.ble){if(!grouped.has(v.id))grouped.set(v.id,[]);grouped.get(v.id).push(v.rssi);}
    const median=a=>{const b=[...a].sort((x,y)=>x-y),n=b.length;return n%2?b[(n-1)/2]:(b[n/2-1]+b[n/2])/2;};
    const rssi=Object.fromEntries([...grouped].filter(([,v])=>v.length>=2).map(([id,v])=>[id,median(v)]));
    let reason='insufficient_ble_window',used=false;
    if(Object.keys(rssi).length>=4){const result=Z.classify({id:`ble-${time}`,timestamp:time,platform:r.platform,device:r.device,quality:1,
      ble:{supported:true,timestamp:time,rssi}},r.references,time);reason=result.reason;used=F.observeRadio(r.engine,convertObservation(r,result),time);}
    r.bleStats.evaluated++;if(used)r.bleStats.applied++;r.bleStats.reasons[reason]=(r.bleStats.reasons[reason]||0)+1;
    r.engine.observationReason=reason;return used;
  }
  function clearMotionBuffers(r){
    r.mag=[];r.stepMag=[];r.sequence=[];r.stepVertical=[];r.sequenceVertical=[];
    r.sequenceKey=null;r.intervals=[];r.ble=[];
    r.gridCalibration=[];r.gridOffset=null;r.gridWindow=[];r.lastGridAppliedStep=-Infinity;
  }
  function pressure(r,time,value){
    const previous=r.engine.trackingState;F.pressure(r.engine,time,value);
    if(previous!==r.engine.trackingState)clearMotionBuffers(r);
  }
  function snapshot(r,maps=[]){const view=F.snapshot(r.engine),landmarks=F.landmarks(r.engine,maps);
    const displayMap=maps.find(m=>Number(m.floor)===view.floor),nearest=landmarks[0];
    const mapPoint=r.engine.coordinateSystem==='meters'?Nav.fromMeters(Nav.compile(r.engine.data,view.floor),view):{x:view.x,y:view.y};
    const room=nearest?.positionBasis&&nearest.distance<=2?displayMap?.rooms?.find(room=>room.id===nearest.id):null;
    const displayPosition=room?{x:room.front_x??room.x,y:0,landmarkId:room.id,basis:'estimated_landmark_display_only'}
      :{...mapPoint,basis:'coordinate_projection'};
    const corridor={main_left:'왼쪽 메인복도 · 강의실 라인',main_right:'오른쪽 메인복도 · 강의실 라인',extension:'증축복도 내부'}[view.zone];
    const locationLabel=view.trackingState!=='tracking'
      ? `층간 이동 감지 중${view.pendingFloor?' · '+view.pendingFloor+'층 후보 · 출구 확인 대기':''}`
      : `${view.floor}층 · ${corridor||view.zoneLabel}${landmarks[0]?.distance<=4?' · '+landmarks[0].label+' 부근 (추정)':''}`;
    return {...view,displayPosition,zoneLabel:corridor||view.zoneLabel,locationLabel,wifiDiagnostic:r.wifiDiagnostic||null,
      landmarks,navigationVersion:r.engine.data.version,
    magneticStrategy:r.magneticGrid?(r.sequenceEnabled?'grid_primary_v2_fallback':'grid_only'):'v2',
    modelVersion:r.models.version||'unversioned',magneticZoneEnabled:r.magneticZoneEnabled,bleEnabled:r.bleEnabled,sequenceEnabled:r.sequenceEnabled,
    magneticGridEnabled:!!r.magneticGrid,magneticGridStats:{...r.magneticGridStats,reasons:{...r.magneticGridStats.reasons}},
    bleStats:{...r.bleStats,reasons:{...r.bleStats.reasons}},
    sequenceStats:{...r.sequenceStats,reasons:{...r.sequenceStats.reasons}},sequenceDiagnostic:r.sequenceDiagnostic||null};}
  function verticalEvidence(r,evidence,time){
    const used=F.verticalEvidence(r.engine,evidence,time);
    if(used)clearMotionBuffers(r);
    return used;
  }
  return {create,heading,magnetic,step,wifi,ble,pressure,snapshot,acceleration,verticalEvidence};
});
