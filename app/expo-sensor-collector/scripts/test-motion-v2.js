const A=require('node:assert/strict'),base='../../../indoor/web/src/positioning/';
const S=require(base+'sequence'),C=require(base+'calibration'),Q=require(base+'quality'),R=require(base+'runtime'),F=require(base+'fusion-engine'),Z=require(base+'zone-classifier');
const data=require('../../../indoor/web/data/navigation/areas-v1.json');
let count=0;function test(name,fn){fn();count++;console.log('PASS '+name);}
test('DTW offset and scale invariant',()=>A.ok(S.distance([1,3,2,5,8,4],[12,16,14,20,26,18])<1e-10));
test('Flat and incomplete sequences rejected',()=>{A.equal(S.distance([1,1,1,1,1],[2,3,4,5,6]),Infinity);A.equal(S.distance([1,2],[1,2]),Infinity);});
test('Other device references excluded',()=>A.equal(S.match([1,2,4,3,6],[{platform:'ios',device:'other',floor:4,direction:'right',values:[1,2,4,3,6]}],{platform:'ios',device:'mine',floor:4,direction:'right'}).candidates.length,0));
test('Regression remains unvalidated and bounded',()=>{const rows=Array.from({length:30},(_,i)=>({cadence:1+i/20,peak:2+i%3,stride:.5+i/100}));const m=C.fit(rows);A.equal(m.validated,false);A.ok(C.predict(m,{cadence:100,peak:100},.8)<=.96);});
test('Lap smoothing hits both anchors',()=>{const r=C.smooth([{time:0,progress:0},{time:1,progress:1},{time:2,progress:2}],[{time:0,x:10,floor:4},{time:2,x:0,floor:4}]);A.deepEqual(r.points.map(p=>p.smoothedX),[10,5,0]);});
test('No invented movement in stationary lap',()=>A.equal(C.smooth([{time:0,progress:0},{time:1,progress:0}],[{time:0,x:10,floor:4},{time:1,x:0,floor:4}]).issues[0].reason,'no_motion_between_laps'));
test('Cross-floor smoothing rejected',()=>A.equal(C.smooth([],[{time:0,x:0,floor:3},{time:1,x:1,floor:4}]).issues[0].reason,'invalid_anchor_interval'));
test('Magnetic disturbance and short steps rejected',()=>{A.equal(Q.magnetic([200,200,200,200,200]).weight,0);A.equal(Q.gait([100],2).weight,0);});
test('Long pause clears sequence and default correction off',()=>{const r=R.create(data,{},[],{floor:4,x:70.804,y:0,platform:'ios'});r.lastStep=100;r.sequence=[1,2,3];r.sequenceKey='4:right';R.heading(r,200,355,3);R.step(r,5000,2);A.deepEqual(r.sequence,[]);A.equal(r.sequenceEnabled,false);});
test('Sequence can be explicitly enabled only for an A/B experiment',()=>{const r=R.create(data,{},[],{floor:4,x:70.804,y:0,platform:'ios',sequenceEnabled:true});A.equal(r.sequenceEnabled,true);});
test('A/B sequence branch applies only a clearly separated 8-step candidate',()=>{
 const values=[30,35,42,51,45,39,48,55],templates=[
  {platform:'ios',device:'mine',floor:4,direction:'right',x:60,values},
  {platform:'ios',device:'mine',floor:4,direction:'right',x:100,values:[55,48,39,45,51,42,35,30]}
 ];
 const off=R.create(data,{templates},[],{floor:4,x:65,y:0,platform:'ios',device:'mine',sequenceEnabled:false});
 const on=R.create(data,{templates},[],{floor:4,x:65,y:0,platform:'ios',device:'mine',sequenceEnabled:true});
 off.sequenceKey='4:right';on.sequenceKey='4:right';
 for(let i=0;i<8;i++)for(const r of [off,on]){R.heading(r,1000+i*500,355,3);r.stepMag=[values[i]-2,values[i]-1,values[i],values[i]+1,values[i]+2];R.step(r,1000+i*500,2);}
 A.equal(off.sequenceDiagnostic.applied,false);A.equal(on.sequenceDiagnostic.applied,true);
});
test('V2 magnetic sequence rejects a match outside the 12 m PDR gate',()=>{
 const s=F.create(data,{floor:4,x:70.804,y:0});
 const result={reason:'sequence_candidate',candidates:[{floor:4,x:3.3631,score:.1}]};
 A.equal(F.observeSequence(s,result,1000,true),false);A.equal(s.sequenceApplicationReason,'outside_pdr_gate');
});
test('BLE fingerprint stays a soft candidate and cannot bypass the 12 m PDR gate',()=>{
 const ble=Object.fromEntries(Array.from({length:8},(_,i)=>[`id${i}`,-50-i]));
 const refs=[{floor:4,platform:'android',device:'mine',zone:'main_right',ble,anchor:{id:'near',x:38,y:0,sigma_m:6}},
  {floor:4,platform:'android',device:'mine',zone:'stairs_right',ble:Object.fromEntries(Object.keys(ble).map(k=>[k,-90])),anchor:{id:'far',x:3.3631,y:0,sigma_m:6}}];
 const o=Z.classify({id:'ble-1',timestamp:1000,platform:'android',device:'mine',quality:1,ble:{supported:true,timestamp:1000,rssi:ble}},refs,1000);
 A.equal(o.candidates[0].anchor.id,'near');
 const near=F.create(data,{floor:4,x:43,y:0}),before=F.snapshot(near).x;A.equal(F.observeRadio(near,o,1000),true);A.ok(F.snapshot(near).x<before);
 const far=F.create(data,{floor:4,x:70.804,y:0});A.equal(F.observeRadio(far,o,1000),false);A.equal(far.observationReason,'ble_outside_pdr_gate');
});
test('BLE runtime evaluates a rolling 5 s window no faster than every 3 s',()=>{
 const ble=Object.fromEntries(Array.from({length:8},(_,i)=>[`id${i}`,-50-i]));
 const refs=[{floor:4,platform:'android',device:'mine',zone:'main_right',ble,anchor:{id:'near',x:38,y:0,sigma_m:6}}];
 const r=R.create(data,{templates:[]},refs,{floor:4,x:43,y:0,platform:'android',device:'mine',bleEnabled:true,magneticZoneEnabled:false,sequenceEnabled:false});
 for(const t of [0,1000,2000,3000,4000])for(const [anonymous_id,rssi_dbm] of Object.entries(ble))R.ble(r,t,{anonymous_id,rssi_dbm});
 A.equal(r.bleStats.evaluated,2);A.equal(r.bleStats.applied,1);A.equal(R.snapshot(r,[]).bleEnabled,true);
});
test('Anchor recovery needs verified repeated fresh wifi',()=>{const s=F.create(data,{floor:4,x:70.804,y:0});const o={features:['wifi'],quality:1,candidates:[{floor:4,zone:'stairs_right',weight:.95,anchor:{verified:true,sources:3,x:0,y:0}}],featureTimes:{wifi:1000}};
 A.equal(F.recover(s,o,1000),false);A.equal(F.recover(s,o,1000),false);o.featureTimes.wifi=3000;A.equal(F.recover(s,o,3000),false);o.featureTimes.wifi=5000;A.equal(F.recover(s,o,5000),true);A.equal(s.recoveryCount,1);
 o.featureTimes.wifi=7000;A.equal(F.recover(s,o,7000),false);
 const t=F.create(data,{floor:4,x:70.804,y:0});o.candidates[0].anchor.verified=false;for(const time of [1000,3000,5000]){o.featureTimes.wifi=time;A.equal(F.recover(t,o,time),false);}});
console.log(`${count} motion-v2 tests passed`);
