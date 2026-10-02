// Offline held-out-session diagnostic. No production model/code writes.
const fs=require('fs'),path=require('path'),Module=require('module');
const seqPath=path.resolve(__dirname,'../web/src/positioning/sequence.js');
const m=new Module(seqPath,module);m.filename=seqPath;m.paths=module.paths;
// Production distance rejects <5 samples. Permit 3 only in this experiment.
m._compile(fs.readFileSync(seqPath,'utf8').replace('a.length<5||b.length<5','a.length<3||b.length<3'),seqPath);
const S=m.exports,templates=require('../web/data/positioning/motion-models.json').templates.filter(t=>t.platform==='ios');
const output={note:'Same endpoint suffixes of existing 8-step templates; source-session holdout, weak interpolated labels. Not independent field accuracy or full 3/6-step runtime cadence evaluation.',results:[]};
for(const n of [3,6,8]){
 const rows=templates.map(t=>({...t,values:t.values.slice(-n)}));const errors=[],reasons={};
 for(const q of rows){const r=S.match(q.values,rows.filter(t=>t.source!==q.source),q);reasons[r.reason]=(reasons[r.reason]||0)+1;
  if(r.reason==='sequence_candidate')errors.push(Math.abs(r.candidates[0].x-q.x));}
 output.results.push({steps:n,queries:rows.length,sources:[...new Set(rows.map(t=>t.source))].length,accepted:errors.length,reasons,meanError:errors.length?errors.reduce((a,b)=>a+b,0)/errors.length:null,over6:errors.filter(e=>e>6).length});
}
fs.writeFileSync(path.resolve(__dirname,'../data/analysis/detailed-20260914/sequence-3-6-8.json'),JSON.stringify(output,null,2));console.log(output);
