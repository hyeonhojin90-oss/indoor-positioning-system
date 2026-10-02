const A=require('node:assert/strict'),F=require('../web/src/positioning/fusion-engine'),N=require('../web/src/positioning/navigation');
const data=require('../web/data/navigation/areas-v1.json'),g=require('../data/analysis/left-grid-20260923/grid-4f-left.json'),e=require('../data/analysis/left-grid-20260923/evaluation.json');
const map=N.compile(data,4),d=N.metricDistance(map,100)-N.metricDistance(map,70.804);
A.equal(F.observeMagneticGrid(F.create(data,{floor:4,x:100,y:0}),d,g.coordinate.lengthM,1000,'main_left'),true);
A.equal(F.observeMagneticGrid(F.create(data,{floor:4,x:35,y:0}),d,g.coordinate.lengthM,1000,'main_left'),false);
A.equal(F.observeMagneticGrid(F.create(data,{floor:3,x:100,y:0}),d,g.coordinate.lengthM,1000,'main_left'),false);
for(const fold of e.folds){A.equal(fold.trainingSources.length,4);A.ok(fold.trainingSources.every(s=>s.sha256!==fold.excludedSha256));}
A.equal(g.sources.length,5);A.ok(g.platforms.android.norm.filter(c=>c.sessions>=2).length>80);
console.log('PASS left grid coordinate/zone/floor gates and LOSO source exclusion');
