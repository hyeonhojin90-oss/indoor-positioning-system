const assert=require("node:assert/strict");
const Nav=require("../../../indoor/web/src/positioning/navigation");
const Zones=require("../../../indoor/web/src/positioning/zone-classifier");
const Vertical=require("../../../indoor/web/src/positioning/vertical-tracker");
const Fusion=require("../../../indoor/web/src/positioning/fusion-engine");
const data=require("../../../indoor/web/data/navigation/areas-v1.json");
const floor02=require("../../../indoor/web/data/maps/floor-02.json");
const {ROUTES,FLOOR_MAPS}=require("../routes");
let passed=0;
function test(name,fn){fn();passed++;console.log(`PASS ${name}`);}
const map2=Nav.compile(data,2), map3=Nav.compile(data,3);
const path=(map,points)=>points.slice(1).map((p,i)=>Nav.transition(map,Nav.svgToMap(...points[i]),Nav.svgToMap(...p)));
test("SVG-map roundtrip preserves original core and extension",()=>{
  for(const p of [[70,732],[711,732],[690,764],[732,1014],[1310,732],[1169,85],[1050,640]]) {
    const m=Nav.svgToMap(...p),r=Nav.mapToSvg(m.x,m.y);
    assert.ok(Math.hypot(r.x-p[0],r.y-p[1])<1e-8);
  }
  assert.equal(Nav.svgToMap(711,732).x,70.804);
});
test("2F open2107 connects to Mspace",()=>assert.ok(path(map2,[[1043,732],[1043,640],[1043,560],[1043,300]]).every(v=>v.allowed&&v.reason==="mapped_area")));
test("2F entry connects to study independently of 2107",()=>assert.ok(path(map2,[[1169,732],[1169,642],[1138,642]]).every(v=>v.allowed&&v.reason==="mapped_area")));
test("2F entry connects to extension",()=>assert.ok(path(map2,[[1163,732],[1163,640],[1163,300]]).every(v=>v.allowed&&v.reason==="mapped_area")));
test("2F 2107-study wall blocks both directions including long segments",()=>{
  for(const points of [[[1050,640],[1120,640]],[[1120,640],[1050,640]],[[1010,620],[1200,680]]]) assert.equal(path(map2,points)[0].allowed,false);
});
test("Known pillar cannot be tunnelled through",()=>assert.equal(path(map2,[[1120,690],[1170,690]])[0].allowed,false));
test("TDM interior is outside the agreed corridor tracking scope",()=>{
  const result=path(map2,[[1170,630],[1270,630]])[0];
  assert.equal(result.allowed,false);
  assert.equal(result.reason,"outside_tracking_scope");
});
test("3F surveyed extension and registered IT stairs remain reachable",()=>{
  const points=[{x:11.5,y:0},{x:11.5,y:12},{x:18.5,y:12},{x:18.5,y:30}];
  assert.ok(points.slice(1).every((p,i)=>Nav.transition(map3,points[i],p).allowed));
  assert.ok(Nav.transition(map3,{x:18.5,y:11},{x:23,y:11}).allowed);
  assert.equal(Nav.transition(map3,{x:23,y:11},{x:31,y:11}).allowed,false,
    "unconfirmed IT-hall connection must not be invented");
});
test("1-10F compile independently without mutable common geometry",()=>{
  for(let f=1;f<=10;f++)assert.ok(Nav.areaAt(Nav.compile(data,f),{x:70.804,y:0}));
  map2.areas[0].label="test";assert.notEqual(data.common[0].label,"test");
});
test("Collection new routes no longer cross 2107 wall; 10 floors retained",()=>{
  assert.equal(new Set(ROUTES.map(r=>r.floor)).size,10);
  for(const id of ["2F_STUDY_V3","2F_EXTENSION_V3"]) {
    const r=ROUTES.find(r=>r.id===id);assert.ok(r);assert.ok(!r.laps.some(l=>l.includes("2107")));
  }
  const extension=ROUTES.find(r=>r.id==="2F_EXTENSION_V3");
  assert.ok(extension.laps.every(l=>l.includes("중앙")||l.includes("교차점")));
});
test("2F main-right collection preserves the confirmed door and 2107 order",()=>{
  const r=ROUTES.find(r=>r.id==="2F_CORE_TO_RIGHT_STAIRS");
  assert.equal(r.start,"코어·오른쪽 메인복도 교차점");
  assert.deepEqual(r.laps.slice(0,6),[
    "2211 문 1","2211 문 2","2210 문 1","2107 진입 가능점","2210 문 2 · 2107 끝점","2210-1 앞"
  ]);
});
test("2F 2211 and renamed 2210-1 have equal widths with one shared boundary",()=>{
  const a=floor02.rooms.find((room)=>room.id==="2211");
  const b=floor02.rooms.find((room)=>room.id==="2210-1");
  assert.equal(a.width,b.width);
  assert.ok(Math.abs((a.x-a.width/2)-(b.x+b.width/2))<0.002);
  assert.equal(a.hide_door,true);
  assert.equal(b.hide_door,true);
});
const refs=[{platform:"ios",floor:4,zone:"main_right",magnetic:42,spread:3},
  {platform:"ios",floor:4,zone:"stairs_right",magnetic:52,spread:3}];
const obs={id:"a",timestamp:2000,platform:"ios",magnetic:52,wifi:{supported:false}};
test("Zone scorer is separate and returns relative not calibrated scores",()=>{
  const r=Zones.classify(obs,refs,2000);assert.equal(r.candidates[0].zone,"stairs_right");assert.equal(r.calibratedProbability,false);
});
test("Missing AP API != empty AP scan",()=>{
  const a=Zones.classify(obs,refs,2000),b=Zones.classify({...obs,wifi:undefined},refs,2000);assert.deepEqual(a,b);
});
test("Cross-device raw references not silently pooled",()=>assert.equal(Zones.classify({...obs,platform:"android"},refs,2000).reason,"no_reference_data"));
test("Magnetic disturbance and no refs do not fabricate a zone",()=>{
  assert.equal(Zones.classify({...obs,magneticStd:30},refs,2000).candidates.length,0);
  assert.equal(Zones.classify({...obs,magnetic:200},refs,2000).reason,"out_of_distribution");
});
test("WiFi stale/cached or fewer than 4 shared BSSIDs cannot vote",()=>{
  const radioRefs=[{platform:"android",floor:4,zone:"stairs_right",wifi:{a:-40,b:-45,c:-50,d:-55}}];
  const r={id:"r",timestamp:2000,platform:"android",wifi:{supported:true,fresh:true,timestamp:2000,rssi:{a:-41,b:-44,c:-49,d:-54}}};
  assert.equal(Zones.classify(r,radioRefs,2000).candidates[0].zone,"stairs_right");
  for(const wifi of [{...r.wifi,fresh:false},{...r.wifi,timestamp:-5000},{...r.wifi,rssi:{a:-40,b:-45,c:-50}}])assert.equal(Zones.classify({...r,wifi},radioRefs,2000).candidates.length,0);
});
test("A zone window is fused only once",()=>{
  const s=Fusion.create(data,{floor:4,x:1});const z=Zones.classify(obs,refs,2000);
  assert.ok(Fusion.observeZone(s,z,2000));const before=JSON.stringify(s.particles);
  assert.equal(Fusion.observeZone(s,z,2001),false);assert.equal(JSON.stringify(s.particles),before);
});
test("Same WiFi scan with new envelope ID is not independent evidence",()=>{
  const s=Fusion.create(data,{floor:4,x:1});
  const r={id:"r1",timestamp:2000,featureTimes:{wifi:1900},features:["wifi"],candidates:[{floor:4,zone:"stairs_right",weight:1}]};
  assert.ok(Fusion.observeZone(s,r,2000));
  assert.equal(Fusion.observeZone(s,{...r,id:"r2",timestamp:3000},3000),false);
});
test("2D PDR follows core heading without forcing main line",()=>{
  const s=Fusion.create(data,{floor:4,x:70.804,y:-7});
  for(let i=0;i<5;i++){Fusion.heading(s,265,1000+i*600,3);Fusion.step(s,1000+i*600,2);}
  const v=Fusion.snapshot(s);assert.ok(v.y>-4);assert.ok(v.x>69&&v.x<73);
});
test("2F surveyed extension advances one shared physical stride",()=>{
  const area=map2.areas.find(a=>a.id==="extension"),start={x:(area.rect[0]+area.rect[2])/2,y:area.rect[1]+1};
  const s=Fusion.create(data,{floor:2,...start,count:80,baseStride:70.804/81});
  for(let i=0;i<10;i++){Fusion.heading(s,285,1000+i*1000,3);Fusion.step(s,1000+i*1000,2,1);}
  const v=Fusion.snapshot(s),expected=10*(70.804/81)*data.floors["2"].extensionMotionMetric.legacyStepMeters;
  assert.ok(Math.abs((v.y-start.y)-expected)<.08,`${v.y-start.y} vs ${expected}`);
  assert.equal(v.zone,"extension");
});
test("No fresh heading means no invented direction",()=>{
  const s=Fusion.create(data,{floor:4,x:40});const x=Fusion.snapshot(s).x;
  Fusion.step(s,1000,2);assert.equal(Fusion.snapshot(s).x,x);assert.equal(s.reason,"heading_unavailable");
});
test("Known wall cannot be crossed by particle steps; recovery flags loss",()=>{
  const p=Nav.svgToMap(1070,640),s=Fusion.create(data,{floor:2,...p});
  for(let i=0;i<12;i++){Fusion.heading(s,355,1000+i*600,3);Fusion.step(s,1000+i*600,2);}
  const wallX=Nav.svgToMap(1080,640).x;
  assert.ok(s.particles.every(p=>p.x>=wallX));assert.equal(s.reason,"recovery_required_wall");
});
test("Initial multiple floors/areas retained, not averaged through walls",()=>{
  const s=Fusion.create(data,{hypotheses:[{floor:2,x:20,y:0,weight:1},{floor:3,x:100,y:0,weight:1}]});
  const v=Fusion.snapshot(s);assert.equal(v.floorCandidates.length,2);assert.ok(v.x<25||v.x>95);
  Fusion.pressure(s,1000,998);assert.equal(s.vertical.status,"initial_floor_ambiguous");
});
test("No trained regression keeps cadence-neutral stride; trained bounds capped",()=>{
  assert.equal(Fusion.stride(.8,1,2,null).length,.8);assert.equal(Fusion.stride(.8,3,2,null).length,.8);
  assert.ok(Math.abs(Fusion.stride(.8,3,2,{validated:true,units:"map_units",coefficients:[0,1,0]}).length-.96)<1e-10);
});
function verticalRun(context,drop) {
  let s=Vertical.create(3);
  for(let t=0;t<=2000;t+=250)s=Vertical.update(s,t,998,context);
  for(let t=2250;t<=14000;t+=250)s=Vertical.update(s,t,998-drop,context);
  return s;
}
test("IT hall elevation .1827 and even .44 never force 4F",()=>{
  for(const d of [.1827,.44])assert.equal(verticalRun({withinFloor:true,atConnector:true},d).floor,3);
});
test("Pressure change away from connector remains unconfirmed",()=>assert.equal(verticalRun({atConnector:false},.44).floor,3));
test("Stable landing + connector allows relative floor change",()=>{
  assert.equal(verticalRun({atConnector:true},.44).floor,4);
  assert.equal(verticalRun({atConnector:true},-.44).floor,2);
});
test("High callback rate alone cannot confirm a floor",()=>{
  let s=Vertical.create(4);for(let t=0;t<=1000;t+=10)s=Vertical.update(s,t,998,{});
  for(let t=1010;t<=2000;t+=10)s=Vertical.update(s,t,997.56,{atConnector:true});assert.equal(s.floor,4);
});
test("Half landing does not count as a whole floor",()=>assert.equal(verticalRun({atConnector:true},.22).floor,3));
test("NaN/out-of-order pressure cannot poison tracker",()=>{
  const s=verticalRun({atConnector:false},0);assert.equal(Vertical.update(s,1,990,{}),s);assert.equal(Vertical.update(s,16000,NaN,{}),s);
});
test("Side stairs included in endpoint results, not just classroom names",()=>{
  const rightEntrance=Nav.compile(data,4).distanceMetric.mapBreaks[0];
  const s=Fusion.create(data,{floor:4,x:rightEntrance});assert.equal(Fusion.landmarks(s,FLOOR_MAPS)[0].id,"RIGHT_STAIRS");
  for(const coordinateSystem of ['legacy','meters']){
    const metric=Nav.compile(data,4,coordinateSystem),core=coordinateSystem==='meters'
      ?Nav.metricDistance(metric.sourceMap,70.804):70.804;
    for(const [x,id] of [[metric.distanceMetric.mapBreaks[0],'RIGHT_STAIRS'],[core,'CORE'],[metric.distanceMetric.mapBreaks.at(-1),'LEFT_STAIRS']]){
      const state=Fusion.create(data,{floor:4,x,y:0,count:1,coordinateSystem});
      Object.assign(state.particles[0],{x,y:0});
      assert.equal(Fusion.landmarks(state,FLOOR_MAPS)[0].id,id,
        `${coordinateSystem}: surveyed endpoints remain available alongside observed classrooms`);
    }
  }
});
console.log(`${passed} fusion tests passed`);
