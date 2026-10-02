const A=require('node:assert/strict');
const F=require('../../../indoor/web/src/positioning/fusion-engine');
const data=require('../../../indoor/web/data/navigation/areas-v1.json');
for(const floor of [2,3,4,6,10]){
 const s=F.create(data,{floor,x:40,y:0,initialDirectionSign:-1});
 s.particles.forEach((p,i)=>Object.assign(p,{x:40,y:0,scale:i%2?.85:1.15,headingBias:0}));
 F.heading(s,355,1000,3);F.step(s,1100,2);
 A.ok(s.particles.every(p=>Math.abs(p.x-s.particles[0].x)<1e-8),`floor ${floor}: same corridor step`);
}
const N=require('../../../indoor/web/src/positioning/navigation'),m=N.compile(data,4);
const rightEndpoint=m.distanceMetric.mapBreaks[0];
let x=70.804;for(let i=0;i<81;i++)x=N.advanceDistance(m,x,-70.804/81);
A.ok(Math.abs(x-rightEndpoint)<1e-8,'81 calibrated steps reach the main-corridor line before the surveyed right stair entrance');
for(let i=0;i<81;i++)x=N.advanceDistance(m,x,70.804/81);
A.ok(Math.abs(x-70.804)<1e-8,'reverse returns to core center');
A.ok(Math.abs(N.metricDistance(m,135.407)-N.metricDistance(m,72.184)-47.3473772)<1e-8,'left wing uses surveyed 47.347m');
A.ok(Math.abs(N.advanceDistance(m,72.184,47.3473772/m.distanceMetric.metersPerLegacyUnit)-135.407)<1e-8,'surveyed left distance reaches the left end');
A.ok(Math.abs(N.advanceDistance(m,N.advanceDistance(m,73,-2),2)-73)<1e-8,'core boundary round trip');
for(const floor of [2,3,4,5,6,7,8,9,10])A.ok(N.compile(data,floor).distanceMetric,`floor ${floor}: shared metric`);
A.equal(N.compile(data,1).distanceMetric.status,
  'common_geometry_reused_user_confirmation_not_1f_survey',
  'floor 1 reuses the confirmed common geometry without claiming a 1F survey');
console.log('PASS uniform corridor stride on 2/3/4/6/10F');
