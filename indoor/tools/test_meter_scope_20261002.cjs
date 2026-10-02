const A=require('node:assert/strict'),N=require('../web/src/positioning/navigation'),F=require('../web/src/positioning/fusion-engine'),R=require('../web/src/positioning/runtime');
const data=require('../web/data/navigation/areas-v1.json');let checks=0;
for(let floor=1;floor<=10;floor++){
  const old=N.compile(data,floor),m=N.compile(data,floor,'meters');
  for(const x of [-2,3.363100346,40,69.424,70.804,72.184,100,135.407,137]){
    const p={x,y:.3},q=N.fromMeters(old,N.toMeters(old,p));A.ok(Math.abs(q.x-x)<1e-8);A.equal(q.y,p.y);checks++;
  }
  A.ok(m.scope.closed);A.equal(m.distanceMetric.metersPerLegacyUnit,1);
  A.equal(N.transition(m,{x:80,y:0},{x:80,y:5}).allowed,false);checks++;
}
const map=N.compile(data,4),meter=N.compile(data,4,'meters'),scale=map.distanceMetric.metersPerLegacyUnit;
for(const units of ['legacy','meters'])for(const floor of [2,3]){
  const m=N.compile(data,floor,units);
  for(const portal of m.portals.filter(p=>p.between.includes('entry')||p.between.includes('extension'))){
    const mid={x:(portal.line[0].x+portal.line[1].x)/2,y:(portal.line[0].y+portal.line[1].y)/2};
    const toward=id=>{const rect=m.areas.find(a=>a.id===id).rect,dx=(rect[0]+rect[2])/2-mid.x,dy=(rect[1]+rect[3])/2-mid.y,scale=.25/Math.hypot(dx,dy);
      return {x:mid.x+dx*scale,y:mid.y+dy*scale};};
    A.ok(N.transition(m,toward(portal.between[0]),toward(portal.between[1])).allowed);checks++;
  }
}
let s=F.create(data,{floor:4,x:30,y:0,coordinateSystem:'meters',count:1,initialDirectionSign:-1});
let start=F.snapshot(s).x;
for(let i=0;i<10;i++){F.heading(s,355,i*600+1000,3);F.step(s,i*600+1000,2);}
A.ok(Math.abs(start-F.snapshot(s).x-10*70.804/81*scale)<1e-8);checks++;
for(const floor of [2,3]){
  const m=N.compile(data,floor,'meters'),a=m.areas.find(a=>a.id==='extension');
  const legacy=N.compile(data,floor),oldArea=legacy.areas.find(a=>a.id==='extension');
  const surveyedWidth=(oldArea.rect[2]-oldArea.rect[0])*legacy.extensionMotionMetric.xMetersPerUnit;
  A.ok(Math.abs(a.rect[2]-a.rect[0]-surveyedWidth)<1e-8);checks++;
  const p={x:(a.rect[0]+a.rect[2])/2,y:(a.rect[1]+a.rect[3])/2};
  const source={x:oldArea.rect[0]+.5,y:oldArea.rect[1]+5};
  const roundtrip=N.fromMeters(legacy,N.toMeters(legacy,source));
  A.ok(Math.abs(roundtrip.x-source.x)<1e-8);A.equal(roundtrip.y,source.y);checks++;
  const e=F.create(data,{floor,...p,coordinateSystem:'meters',count:1});F.heading(e,265,1000,3);
  const before=F.snapshot(e);F.step(e,1000,2);A.ok(Math.abs(F.snapshot(e).y-before.y-e.baseStride)<1e-8);checks++;
  const far=F.create(data,{floor,...p,y:25,coordinateSystem:'meters',count:1});
  const radio={id:'too-far-along-extension',timestamp:2000,features:['wifi'],featureTimes:{wifi:2000},wifiAbsoluteAccepted:true,
    candidates:[{floor,zone:'entry',weight:1,wifiScore:1,anchor:{x:p.x,y:2,verified:true,sources:3}}]};
  A.equal(F.observeWifi(far,radio,2000),false);checks++;
  A.equal(F.observeRadio(far,{...radio,features:['ble'],featureTimes:{ble:2000}},2000),false);checks++;
}
const one=N.compile(data,1),entry=one.areas.find(a=>a.id==='main_entrance');
A.ok(entry);A.ok(N.transition(one,{x:(entry.rect[0]+entry.rect[2])/2,y:2},{x:(entry.rect[0]+entry.rect[2])/2,y:0}).allowed);checks++;
A.equal(N.transition(one,{x:60,y:0},{x:60,y:5}).allowed,false);checks++;
const two=N.compile(data,2),wall=two.walls[0],p=wall.line[0],q=wall.line[1];
A.equal(N.transition(two,{x:p.x-1,y:(p.y+q.y)/2},{x:p.x+1,y:(p.y+q.y)/2}).allowed,false);checks++;
const r=R.create(data,{},[],{floor:4,x:40,y:0,coordinateSystem:'meters',inputCoordinates:'legacy'});
A.ok(Math.abs(F.snapshot(r.engine).x-N.metricDistance(map,40))<.6);checks++;
const gridLength=require('../web/data/positioning/grid-4f-right.json').coordinate.lengthM;
A.ok(F.observeMagneticGrid(r.engine,gridLength-F.snapshot(r.engine).x,gridLength,1000));checks++;
const anchor={id:'test',verified:true,sources:4,x:40,y:0,sigma_m:6};
const xAnchor=N.toMeters(map,anchor);
A.ok(F.observeWifi(r.engine,{id:'scan',timestamp:2000,features:['wifi'],featureTimes:{wifi:2000},wifiAbsoluteAccepted:true,
  candidates:[{floor:4,zone:'main_right',weight:1,wifiScore:1,anchor:{...anchor,...xAnchor}}]},2000));checks++;
const st=F.create(data,{floor:4,x:135.8,y:0});
A.equal(F.verticalEvidence(st,{verified:false,entryConfirmed:true},1000),false);
A.equal(F.verticalEvidence(st,{verified:true,entryConfirmed:true},1000),true);
const fixed=F.snapshot(st);F.heading(st,175,2000,3);F.step(st,2000,2);
A.equal(F.snapshot(st).x,fixed.x);A.equal(F.snapshot(st).y,fixed.y);checks++;
A.equal(F.verticalEvidence(st,{verified:true,exitConfirmed:true},3000),false);checks++;
A.equal(F.verticalEvidence(st,{verified:true,beaconFloor:5},3000),true);
A.equal(F.snapshot(st).floor,5);A.equal(F.snapshot(st).trackingState,'tracking');checks++;
A.equal(F.verticalEvidence(st,{verified:true,entryConfirmed:true},2999),false);checks++;
A.equal(st.heading,null);checks++;
F.step(st,3500,2);A.equal(F.snapshot(st).reason,'heading_unavailable');checks++;
// A stable pause in a stairwell creates a floor candidate, never a confirmed
// floor. Walking within the stairs continues sensor counts but freezes XY.
const ps=F.create(data,{floor:4,x:135.8,y:0,count:1});
for(let t=0;t<=2000;t+=250)F.pressure(ps,t,1000);
const beforePressure=F.snapshot(ps);
for(let t=2250;t<=9000;t+=250)F.pressure(ps,t,999.56);
A.equal(F.snapshot(ps).floor,4);A.equal(F.snapshot(ps).pendingFloor,5);
A.equal(F.snapshot(ps).trackingState,'vertical_floor_pending');checks++;
F.heading(ps,355,9250,3);F.step(ps,9250,2);
A.equal(F.snapshot(ps).x,beforePressure.x);checks++;
A.equal(F.observeZone(ps,{id:'pause',timestamp:9250,candidates:[{floor:4,zone:'stairs_left',weight:1}]},9250),false);checks++;
A.ok(F.verticalEvidence(ps,{verified:true,exitConfirmed:true},9500));
A.equal(F.snapshot(ps).floor,5);checks++;
const paused=R.create(data,{},[],{floor:4,x:135.8,y:0});
paused.gridOffset=123;paused.ble=[{id:'old',time:1,rssi:-40}];paused.sequence=[1,2,3];
A.ok(R.verticalEvidence(paused,{verified:true,entryConfirmed:true},1000));
A.equal(paused.gridOffset,null);A.deepEqual(paused.ble,[]);A.deepEqual(paused.sequence,[]);checks++;
// Only measured/labelled progression can name a room in metric mode. Drawing
// proportions alone never create a classroom coordinate on unlabelled floors.
const f6=F.create(data,{floor:6,x:40,y:0,coordinateSystem:'meters',count:1});
A.ok(F.landmarks(f6,[require('../web/data/maps/floor-06.json')]).every(l=>!/^6\d{3}$/.test(l.id)));checks++;
console.log('PASS meter/scope/vertical',checks,'checks');
