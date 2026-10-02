const A=require('node:assert/strict'),N=require('../../../indoor/web/src/positioning/navigation'),F=require('../../../indoor/web/src/positioning/fusion-engine');
const data=require('../../../indoor/web/data/navigation/areas-v1.json');
for(const floor of [2,3]){
 const map=N.compile(data,floor),area=map.areas.find(a=>a.id==='extension');
 const from={x:(area.rect[0]+area.rect[2])/2+.4,y:(area.rect[1]+area.rect[3])/2};
 for(const [heading,sign] of [[245,1],[65,-1]]){
  const moved=F.corridorMotion(map,from,{x:from.x+.7,y:from.y+.7},heading,-1);
  A.equal(moved.aligned,true);A.equal(Math.sign(moved.to.y-from.y),sign);
  A.ok(Math.abs(moved.to.x-(area.rect[0]+area.rect[2])/2)<.4);
 }
 A.equal(F.corridorMotion(map,from,{x:from.x+1,y:from.y},355).aligned,false);
}
const map=N.compile(data,2),points=[[1104,732],[1104,692],[1104,650]].map(p=>N.svgToMap(...p));
for(let i=1;i<points.length;i++)A.equal(N.transition(map,points[i-1],points[i]).reason,'mapped_area');
A.equal(N.transition(map,N.svgToMap(1135,732),N.svgToMap(1135,650)).allowed,false);
A.equal(N.transition(map,N.svgToMap(1050,640),N.svgToMap(1120,640)).allowed,false);
console.log('PASS extension bidirectional heading tolerance, pillar-left passage, retained walls');
for(const floor of [2,3,4,6,7,8,9,10]){
 const m=N.compile(data,floor),a=m.areas.find(a=>a.id==='side_passage'),x=(a.rect[0]+a.rect[2])/2;
 A.equal(N.transition(m,{x,y:0},{x,y:-2}).reason,'mapped_area');
 A.equal(N.transition(m,{x,y:-2},{x,y:0}).reason,'mapped_area');
 A.equal(a.vertical,undefined);
}
console.log('PASS eight side passages connect both ways without floor-transition flags');
