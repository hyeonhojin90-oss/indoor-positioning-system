const assert=require('node:assert/strict');
const Runtime=require('../web/src/positioning/runtime');
const Fusion=require('../web/src/positioning/fusion-engine');
const Nav=require('../web/src/positioning/navigation');
const data=require('../web/data/navigation/areas-v1.json');
const grid=require('../data/analysis/magnetic-map-4f-20260921/grid-4f-right.json');
const map=Nav.compile(data,4),at40=grid.coordinate.lengthM-Nav.metricDistance(map,40);
assert.equal(Runtime.create(data,{},[],{floor:4,x:40,platform:'android'}).magneticGrid,null);
assert.equal(Runtime.create(data,{},[],{floor:4,x:40,platform:'android',magneticGridEnabled:true,magneticGrid:grid}).magneticGrid,grid);
const candidate=Runtime.create(data,{},[],{floor:4,x:40,platform:'android',magneticGridEnabled:true,magneticGrid:grid,
  sequenceEnabled:true,magneticZoneEnabled:true});
assert.equal(candidate.sequenceEnabled,false);
assert.equal(candidate.magneticZoneEnabled,false);
const fallback=Runtime.create(data,{},[],{floor:4,x:40,platform:'android',magneticGridEnabled:true,
  magneticGrid:grid,sequenceFallbackEnabled:true,sequenceEnabled:true});
assert.equal(fallback.sequenceEnabled,true);
assert.equal(fallback.magneticGrid,grid);
assert.equal(Fusion.observeMagneticGrid(Fusion.create(data,{floor:4,x:40}),at40+13,grid.coordinate.lengthM,1000),false);
const engine=Fusion.create(data,{floor:4,x:40});
assert.equal(Fusion.observeMagneticGrid(engine,at40,grid.coordinate.lengthM,1000),true);
assert.equal(Fusion.observeMagneticGrid(engine,at40,grid.coordinate.lengthM,1000),false);
assert.equal(Fusion.observeMagneticGrid(Fusion.create(data,{floor:3,x:40}),at40,grid.coordinate.lengthM,1000),false);
console.log('magnetic grid opt-in and particle gates: OK');
