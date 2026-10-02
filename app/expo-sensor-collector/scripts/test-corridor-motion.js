const assert=require('node:assert/strict');
const F=require('../../../indoor/web/src/positioning/fusion-engine');
const N=require('../../../indoor/web/src/positioning/navigation');
const data=require('../../../indoor/web/data/navigation/areas-v1.json');
for(const floor of [1,2,3,4,5,6,7,8,9,10]){
  const map=N.compile(data,floor);
  for(const heading of [355,15,25,175,195]){
    const r=F.corridorMotion(map,{x:60,y:.8},{x:59,y:1.2},heading);
    assert.equal(r.aligned,true);assert.equal(r.to.y,.4);assert.ok(Math.abs(Math.abs(r.to.x-60)-Math.hypot(1,.4))<1e-9);
  }
  assert.equal(F.corridorMotion(map,{x:70.8,y:0},{x:70.8,y:-1},85).aligned,false);
  assert.equal(F.corridorMotion(map,{x:60,y:15},{x:59,y:16},355).aligned,false);
}
for(const [floor,point] of [[2,[1040,620]],[2,[1170,610]],[3,[1200,620]],[3,[1200,510]]]){
  const p=N.svgToMap(...point),raw={x:p.x-.5,y:p.y+.2};
  assert.deepEqual(F.corridorMotion(N.compile(data,floor),p,raw,355),{to:raw,aligned:false});
}
for(const [heading,x] of [[20,70.804],[195,20]]){
  const s=F.create(data,{floor:4,x,y:0});
  for(let i=1;i<=40;i++){F.heading(s,heading,i*600,3);F.step(s,i*600,2);}
  assert.notEqual(F.snapshot(s).zone,'unknown');
  assert.ok(Math.abs(F.snapshot(s).y)<.1);
  assert.ok(F.snapshot(s).corridorHeadingOffset>10 && F.snapshot(s).corridorHeadingOffset<35);
  F.heading(s,85,25000,3);F.step(s,25000,2);
  assert.ok(Math.abs(F.snapshot(s).y)<.1,'unmapped perpendicular turn does not leave the corridor');
}
for(const [heading,direction] of [[242,1],[298,-1]]){
  const s=F.create(data,{floor:4,x:heading===242?0:70.804,y:0,initialDirectionSign:direction});
  for(let i=1;i<=25;i++){F.heading(s,heading,i*600,3);F.step(s,i*600,2);}
  const v=F.snapshot(s);assert.ok(Math.abs(v.y)<.1);assert.notEqual(v.zone,'unknown');
  assert.equal(v.corridorDirection,direction);
}
console.log('PASS corridor drift in both directions, 10 floors, turns, open areas, no distant teleport');
