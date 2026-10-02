const fs=require('node:fs'),vm=require('node:vm'),path=require('node:path'),{createRequire}=require('node:module');
const root=path.resolve(__dirname,'../..'),out=path.join(root,'indoor/data/analysis/meters-20261002');fs.mkdirSync(out,{recursive:true});
const original=fs.readFileSync(path.join(root,'exports/indoor-before-meters-20261002/indoor/tools/evaluate_minimum_engine_20260923.cjs'),'utf8');
const currentRuntime=require('../web/src/positioning/runtime'),Nav=require('../web/src/positioning/navigation');
const oldRuntime=require('../../exports/indoor-before-meters-20261002/indoor/web/src/positioning/runtime');
const oldData=require('../../exports/indoor-before-meters-20261002/indoor/web/data/navigation/areas-v1.json');
const requireHere=createRequire(__filename);
for(const variant of ['before','scope_legacy','scope_meters']){
  const runtime=variant==='before'?oldRuntime:variant==='scope_legacy'?currentRuntime:{...currentRuntime,
    create:(data,models,refs,options)=>currentRuntime.create(data,models,refs,{...options,coordinateSystem:'meters',inputCoordinates:'legacy'}),
    snapshot:(r,maps)=>{const s=currentRuntime.snapshot(r,maps),p=Nav.fromMeters(Nav.compile(r.engine.data,s.floor),s);return {...s,x:p.x,y:p.y};}};
  const code=original.replace("out=path.join(root,'indoor/data/analysis/minimum-engine-20260923')",`out=path.join(root,'indoor/data/analysis/meters-20261002/${variant}')`);
  const req=name=>name==='../web/src/positioning/runtime'?runtime:name==='../web/data/navigation/areas-v1.json'&&variant==='before'?oldData:requireHere(name);
  vm.runInNewContext(code,{require:req,__dirname:path.join(root,'indoor/tools'),console:{log:()=>{}},performance},{filename:variant+'.cjs'});
  console.log(variant,'completed');
}
const result=Object.fromEntries(['before','scope_legacy','scope_meters'].map(v=>[v,JSON.parse(fs.readFileSync(path.join(out,v,'evaluation.json'))).summary]));
fs.writeFileSync(path.join(out,'comparison.json'),JSON.stringify(result,null,2));
console.log(JSON.stringify(Object.fromEntries(Object.entries(result).map(([k,v])=>[k,{left:v.left.pdr,right:v.right.pdr,rightHybrid:v.right.hybrid_ble}]))));
