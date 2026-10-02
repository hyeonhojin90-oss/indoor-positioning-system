// Physical-distance sensitivity analysis. No production engine/model mutation.
const fs=require('fs'),path=require('path');
const survey=require('../web/data/maps/floor-04-survey.json');
const L=survey.core_center_to_right_end.reference_length_m;
const sessions=['133338','133534','133637','133734'].map(id=>{
 const rows=fs.readFileSync(path.join(process.argv[2],`indoor_positioning_ios_20260914_${id}.jsonl`),'utf8').trim().split(/\r?\n/).map(JSON.parse);
 const end=rows.filter(r=>r.kind==='label'&&r.comparison).at(-1);
 const steps=rows.filter(r=>r.kind==='derived_position'&&r.wall_time_ms<=end.wall_time_ms).length;
 return {id,steps,direction:rows[0].positioning_config.initial_direction_sign,rows};
});
const results=sessions.map(s=>{
 const others=sessions.filter(t=>t!==s),trainSteps=others.reduce((a,t)=>a+t.steps,0)/others.length;
 const variants={legacyNumberMisusedAsMeters:70.804/81,rescaled81:L/81,heldoutEndpointCalibration:L/trainSteps};
 return {id:s.id,steps:s.steps,direction:s.direction,
 variants:Object.fromEntries(Object.entries(variants).map(([k,stride])=>[k,{stride,distance:s.steps*stride,signedEndpointError:s.steps*stride-L,absoluteEndpointError:Math.abs(s.steps*stride-L)}])),
 laps:s.rows.filter(r=>r.kind==='label'&&r.comparison).map(r=>{const n=s.rows.filter(t=>t.kind==='derived_position'&&t.wall_time_ms<=r.wall_time_ms).length;
  const x=r.label.map_x,provisionalX=x<=69.424?x/69.424*survey.right_corridor.length_m:survey.right_corridor.length_m+(x-69.424)/2.76*survey.core.wall_center_width_m;
  return {label:r.label.location,steps:n,diagramX:x,provisionalPhysicalX:provisionalX,pdrX:s.direction<0?L-n*L/81:n*L/81,notSurveyedClassroomTruth:true};})};
});
const averages=Object.fromEntries(Object.keys(results[0].variants).map(k=>[k,results.reduce((a,r)=>a+r.variants[k].absoluteEndpointError,0)/results.length]));
const out={referenceLength:L,coreWidth:survey.core.wall_center_width_m,rightLength:survey.right_corridor.length_m,assumptions:['Scan boundary registration pending.','Current engine core uses map 69.424..72.184 (2.76), not outer core 12.734.','81 is previous calibration count, not personal measured stride.','Endpoint leave-one-session-out has only 3 training runs each, same day/user.','No magnetic/particle replay: isolates distance and stride calibration.','Room distances are projected diagram positions, not physical ground truth.'],results,averages};
fs.writeFileSync(path.resolve(__dirname,'../data/analysis/detailed-20260914/survey-distance-audit.json'),JSON.stringify(out,null,2));
console.log(JSON.stringify({...out,results:results.map(({laps,...r})=>r)},null,2));
