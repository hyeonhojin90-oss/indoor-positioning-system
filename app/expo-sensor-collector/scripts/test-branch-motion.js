const assert=require('node:assert/strict');
const F=require('../../../indoor/web/src/positioning/fusion-engine');
const N=require('../../../indoor/web/src/positioning/navigation');
const data=require('../../../indoor/web/data/navigation/areas-v1.json');
for(const floor of [4,6,7,8,9,10]){
 const distances=[];
 for(const heading of [355,25,45,175,205,225]){
  const s=F.create(data,{floor,x:40,y:0});
  for(let i=1;i<=15;i++){F.heading(s,heading,i*600,3);F.step(s,i*600,2);}
  const v=F.snapshot(s);assert.ok(Math.abs(v.y)<.01);assert.notEqual(v.zone,'unknown');distances.push(Math.abs(v.x-40));
 }
 assert.ok(Math.max(...distances)-Math.min(...distances)<.6,'offset must not shorten straight-corridor progress');
}
const map=N.compile(data,2),from=N.svgToMap(1170,715);
const moves=N.branchMoves(map,from,1,265);
assert.ok(moves.some(m=>m.target==='entry'));
assert.equal(N.branchMoves(map,from,1,85).length,0,'pointing away');
assert.equal(N.branchMoves(map,{x:60,y:0},1,265).length,0,'no distant branch');
for(const move of moves){assert.ok(Math.hypot(move.to.x-from.x,move.to.y-from.y)<=1+1e-9);assert.ok(N.transition(map,from,move.to).allowed);}
const blocked=N.branchMoves(map,N.svgToMap(1075,630),1,355);
assert.ok(!blocked.some(m=>m.target==='study'),'no direct 2107 to study connection');
for(const floor of [2,3]){
 const s=F.create(data,{floor,x:N.svgToMap(floor===2?1170:1210,732).x,y:0});
 F.heading(s,305,600,3);F.step(s,600,2);
 assert.ok(s.branchProposals>0,'near portal opens alternative');
 assert.equal(s.particles.length,160);
 assert.ok(Math.abs(s.particles.reduce((a,p)=>a+p.weight,0)-1)<1e-9);
}
console.log('PASS 6 standard floors, angle/stride invariance, 2/3F local branches, walls, count and weights');
// Force low effective sample size and verify a weak occupied branch is retained.
const mixed=F.create(data,{floor:2,x:40,y:0});
const entry=N.svgToMap(1170,630);
mixed.particles.forEach((p,i)=>{p.x=i===159?entry.x:40;p.y=i===159?entry.y:0;p.weight=i===0?.98:.02/159;});
F.observeZone(mixed,{id:'test',timestamp:1000,quality:1,candidates:[{floor:2,zone:'main_right',weight:.9},{floor:2,zone:'entry',weight:.1}]},1000);
assert.equal(mixed.particles.length,160);
assert.ok(mixed.particles.some(p=>N.areaAt(map,p)?.id==='entry'),'weak mapped branch survives resampling');
assert.ok(Math.abs(mixed.particles.reduce((a,p)=>a+p.weight,0)-1)<1e-9);
const {ROUTES}=require('../routes');
const passages=ROUTES.filter(r=>r.geometryStatus==='entry-coordinate-unverified');
assert.equal(passages.length,8);assert.ok(passages.every(r=>r.laps.length===3&&r.start===r.destination));
console.log('PASS branch preservation and 8 passage collection presets');
