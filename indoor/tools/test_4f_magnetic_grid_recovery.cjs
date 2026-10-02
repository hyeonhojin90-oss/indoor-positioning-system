// Counterfactual recovery trial: hold each raw walk fixed and perturb only the
// estimated particles. Query sessions are excluded from their magnetic grids.
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const Runtime = require('../web/src/positioning/runtime');
const Nav = require('../web/src/positioning/navigation');
const navigation = require('../web/data/navigation/areas-v1.json');
const allModels = require('../web/data/positioning/motion-models.json');
const bleReferences = require('../web/data/positioning/ble-references.json').references;
const aligned = require('../data/analysis/magnetic-map-4f-20260921/aligned-sessions.json');
const prior = require('../data/analysis/magnetic-map-4f-runtime-ab-20260921/results.json');

const ROOT = path.resolve(__dirname, '../..');
const OUT = path.join(ROOT, 'indoor/data/analysis/magnetic-grid-recovery-20260921');
const MAP = Nav.compile(navigation, 4);
const LENGTH = aligned.coordinate.lengthM;
const RIGHT = MAP.distanceMetric.mapBreaks[0];
const CORE = 70.804;
const mean = values => values.length ? values.reduce((a, b) => a + b, 0) / values.length : null;
const median = values => { const a = [...values].sort((x, y) => x - y); return a.length ? (a[(a.length - 1) >> 1] + a[a.length >> 1]) / 2 : null; };
const distanceFromCore = x => LENGTH - Nav.metricDistance(MAP, x);
const xFromCoreDistance = distance => {
  let lo = RIGHT, hi = CORE;
  for (let i = 0; i < 35; i++) {
    const mid = (lo + hi) / 2;
    if (distanceFromCore(mid) > distance) lo = mid; else hi = mid;
  }
  return (lo + hi) / 2;
};
const progress = (snapshot, direction) => direction === 'forward'
  ? distanceFromCore(snapshot.x) : LENGTH - distanceFromCore(snapshot.x);
const yaw = values => {
  const [x, y, z, w0] = values;
  const w = Number.isFinite(w0) ? w0 : Math.sqrt(Math.max(0, 1 - x*x - y*y - z*z));
  return (Math.atan2(2*(w*z+x*y), 1-2*(y*y+z*z))*180/Math.PI+360)%360;
};
function gridFor(query) {
  const training = aligned.sessions.filter(s => s.file !== query.file && s.platform === query.platform);
  const norm = [];
  for (let i = 0; i <= Math.floor(LENGTH/.5); i++) {
    const x = i*.5, values = [], sources = new Set();
    for (const session of training) for (const point of session.points) {
      if (Math.abs(point.distanceMFromCore-x) <= .375 && Number.isFinite(point.magneticMagnitudeUt)) {
        values.push(point.magneticMagnitudeUt); sources.add(session.file);
      }
    }
    const average = mean(values);
    const variance = values.length > 1 ? values.reduce((sum,v) => sum+(v-average)**2,0)/(values.length-1) : 0;
    norm.push({x,mean:average,variance,samples:values.length,sessions:sources.size});
  }
  for (let i = 1; i < norm.length-1; i++) if (norm[i].mean === null && norm[i-1].mean !== null && norm[i+1].mean !== null) {
    norm[i].mean = (norm[i-1].mean+norm[i+1].mean)/2;
    norm[i].variance = Math.max(4,norm[i-1].variance,norm[i+1].variance);
    norm[i].sessions = Math.min(norm[i-1].sessions,norm[i+1].sessions);
  }
  return {coordinate:{lengthM:LENGTH,gridStepM:.5},platforms:{[query.platform]:{norm}}};
}
function perturb(engine, direction, offsetM) {
  const targets = engine.particles.filter(p => p.floor===4 && Nav.areaAt(MAP,p)?.id==='main_right')
    .map(p => ({p,target:distanceFromCore(p.x)+(direction==='forward'?offsetM:-offsetM)}));
  // Reject boundary clipping: it would make the injected error misleading.
  if (targets.some(v => v.target<=.1 || v.target>=LENGTH-.1)) return {moved:0,clipped:true};
  for (const v of targets) v.p.x=xFromCoreDistance(v.target);
  return {moved:targets.length,clipped:false};
}
function replay(session, rows, models, grid, kind, scenario=null) {
  const initial = session.direction === 'forward' ? CORE : RIGHT;
  const options = {floor:4,x:initial,y:0,platform:session.platform,device:rows[0].device||rows[0].device_model,
    initialDirectionSign:session.direction==='forward'?-1:1,magneticZoneEnabled:false,
    bleEnabled:session.platform==='android',sequenceEnabled:kind==='baseline'};
  if (kind==='grid') Object.assign(options,{magneticGridEnabled:true,magneticGrid:grid});
  const runtime = Runtime.create(navigation,models,bleReferences,options);
  const endTime=rows.filter(r=>r.kind==='label').at(-1).wall_time_ms;
  const estimates=[];
  let injected=null;
  for(const row of rows) {
    const t=row.wall_time_ms;
    if(!Number.isFinite(t)||t>endTime)continue;
    if(row.sensor==='heading_degrees') Runtime.heading(runtime,t,row.values?.[0],row.accuracy);
    else if(row.sensor==='rotation_vector'&&session.platform==='android') Runtime.heading(runtime,t,yaw(row.values),3);
    else if(row.sensor==='magnetic_field_ut') Runtime.magnetic(runtime,t,row.values);
    else if(row.sensor==='pressure_hpa') Runtime.pressure(runtime,t,row.values?.[0]);
    else if(row.kind==='ble_observation') Runtime.ble(runtime,t,row);
    else if(row.sensor==='accelerometer_mps2'&&Runtime.acceleration(runtime,t,row.values)) {
      const step=estimates.length+1;
      if(scenario&&step===scenario.step) {
        const before=progress(Runtime.snapshot(runtime,[]),session.direction);
        const detail=perturb(runtime.engine,session.direction,scenario.offsetM);
        const after=progress(Runtime.snapshot(runtime,[]),session.direction);
        injected={step,before,after,actualOffsetM:after-before,
          gridAppliedBefore:runtime.magneticGridStats.applied,...detail};
      }
      estimates.push(progress(Runtime.snapshot(runtime,[]),session.direction));
    }
  }
  return {estimates,injected,finalProgress:progress(Runtime.snapshot(runtime,[]),session.direction),
    gridStats:Runtime.snapshot(runtime,[]).magneticGridStats};
}
const scenarios=[];
for(const offsetM of [-8,-7,-5,5,7,8])scenarios.push({fraction:.4,offsetM});
for(const offsetM of [-7,7])scenarios.push({fraction:.6,offsetM});
const trials=[];
for(const session of aligned.sessions) {
  const rows=fs.readFileSync(path.join(ROOT,session.file),'utf8').trim().split(/\r?\n/).map(JSON.parse);
  if(!rows.some(r=>r.sensor==='heading_degrees'||r.sensor==='rotation_vector'))continue;
  const models={...allModels,templates:(allModels.templates||[]).filter(t=>t.source!==path.basename(session.file))};
  const grid=gridFor(session);
  const controls={baseline:replay(session,rows,models,grid,'baseline'),grid:replay(session,rows,models,grid,'grid')};
  const old=prior.sessions.find(s=>s.file===session.file);
  assert(old,'missing prior A/B session');
  for(const kind of ['baseline','grid']) {
    assert.equal(controls[kind].estimates.length,old[kind==='baseline'?'baseline':'gridCandidate'].detectedSteps);
    const error=Math.abs(LENGTH-controls[kind].finalProgress);
    assert(Math.abs(error-old[kind==='baseline'?'baseline':'gridCandidate'].endpointErrorM)<1e-6,
      `control replay drift: ${session.file} ${kind}`);
  }
  const count=controls.baseline.estimates.length;
  for(const spec of scenarios) {
    const scenario={...spec,step:Math.round(count*spec.fraction)};
    const injected={baseline:replay(session,rows,models,grid,'baseline',scenario),
      grid:replay(session,rows,models,grid,'grid',scenario)};
    const sample={file:session.file,platform:session.platform,direction:session.direction,steps:count,scenario};
    for(const kind of ['baseline','grid']) {
      const run=injected[kind],control=controls[kind];
      assert.equal(run.estimates.length,count);
      assert(run.injected && run.injected.moved>0 && !run.injected.clipped,
        `invalid perturbation: ${session.file} ${kind} ${scenario.fraction} ${scenario.offsetM}`);
      const residualAt=lag=>run.estimates[Math.min(count,scenario.step+lag)-1]-control.estimates[Math.min(count,scenario.step+lag)-1];
      sample[kind]={initialResidualM:run.injected.actualOffsetM,residual8M:residualAt(8),
        residual16M:residualAt(16),endpointResidualM:residualAt(count),
        actualEndpointErrorM:Math.abs(LENGTH-run.finalProgress),
        controlEndpointErrorM:Math.abs(LENGTH-control.finalProgress),
        movedParticles:run.injected.moved,
        gridAppliedAfterInjection:run.gridStats.applied-run.injected.gridAppliedBefore};
    }
    trials.push(sample);
  }
}
const summarize=ss=>({trials:ss.length,
  initialAbsM:mean(ss.map(t=>Math.abs(t.grid.initialResidualM))),
  pdrResidual8AbsM:mean(ss.map(t=>Math.abs(t.baseline.residual8M))),
  gridResidual8AbsM:mean(ss.map(t=>Math.abs(t.grid.residual8M))),
  pdrResidual16AbsM:mean(ss.map(t=>Math.abs(t.baseline.residual16M))),
  gridResidual16AbsM:mean(ss.map(t=>Math.abs(t.grid.residual16M))),
  pdrEndpointResidualAbsM:mean(ss.map(t=>Math.abs(t.baseline.endpointResidualM))),
  gridEndpointResidualAbsM:mean(ss.map(t=>Math.abs(t.grid.endpointResidualM))),
  gridBeatsPdrAt16:ss.filter(t=>Math.abs(t.grid.residual16M)<Math.abs(t.baseline.residual16M)).length,
  gridImprovesOwnOffsetAt16:ss.filter(t=>Math.abs(t.grid.residual16M)<Math.abs(t.grid.initialResidualM)-.5).length});
const report={version:'magnetic-grid-recovery-20260921',method:'same raw walk, mid-walk particle shift only; compare each perturbed run with its unperturbed same-mode control; query walk excluded from grid; no intermediate surveyed truth',
  scenarios,summary:{all:summarize(trials),android:summarize(trials.filter(t=>t.platform==='android')),
    ios:summarize(trials.filter(t=>t.platform==='ios')),
    sevenMeter40:summarize(trials.filter(t=>t.scenario.fraction===.4&&Math.abs(t.scenario.offsetM)===7))},trials};
fs.mkdirSync(OUT,{recursive:true});
fs.writeFileSync(path.join(OUT,'results.json'),JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify(report.summary,null,2));
