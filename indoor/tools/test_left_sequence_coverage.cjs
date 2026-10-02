const A=require('node:assert/strict'),S=require('../web/src/positioning/sequence');
const candidate=require('../data/analysis/left-magnetic-20260923/candidate-model.json');
const base={platform:'android',floor:4,direction:'right',device:'phone'};
const values=[20,22,25,19,30,31,22,24];
const refs=[{...base,x:20,values},{...base,x:120,corridor:'main_left',values,verticalValues:values}];
A.equal(S.match(values,refs,{...base,corridor:'main_left'}).candidates.length,1);
A.equal(S.match(values,[refs[0]],{...base,corridor:'main_left'}).reason,'no_sequence_reference');
A.equal(S.match(values,[refs[1]],{...base,corridor:'main_left',verticalValues:Array(8).fill(null)}).reason,'no_sequence_reference');
for(const direction of ['left','right'])A.ok(candidate.templates.some(t=>t.direction===direction&&t.corridor==='main_left'));
for(const t of candidate.templates){A.ok(t.x>=70.804&&t.x<=135.407);A.equal(t.values.length,8);A.equal(t.verticalValues.length,8);A.ok(t.sourceSha256);}
const evals=require('../data/analysis/left-magnetic-20260923/evaluation.json');
for(const fold of evals.folds)A.ok(!fold.trainingSources.includes(fold.file),'query must not be a training source');
console.log('PASS corridor isolation, missing vertical samples, bidirectional coverage, holdout separation');
