// Build and evaluate a 1D magnetic map for the surveyed 4F right corridor.
//
// This tool never edits the runtime model. It produces review artifacts under
// indoor/data/analysis/magnetic-map-4f-20260921. Evaluation is leave-one-session-
// out: every query session is removed before its reference map/windows are built.
// Intermediate truth is endpoint-aligned by detected-step progress and is weak;
// the final endpoint is the confirmed physical endpoint.

const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const Position = require('../../app/expo-sensor-collector/positionTracking');
const Sequence = require('../web/src/positioning/sequence');
const Navigation = require('../web/src/positioning/navigation');
const navigationData = require('../web/data/navigation/areas-v1.json');

const ROOT = path.resolve(__dirname, '../..');
const RAW = path.join(ROOT, 'indoor/data/raw');
const OUTPUT = path.join(ROOT, 'indoor/data/analysis/magnetic-map-4f-20260921');
const SURVEY = require('../web/data/maps/floor-04-survey.json');
const MAP = Navigation.compile(navigationData, 4);
const CORE_X = 70.804;
const RIGHT_X = MAP.distanceMetric.mapBreaks[0];
const LENGTH_M = Math.abs(Navigation.metricDistance(MAP, CORE_X) - Navigation.metricDistance(MAP, RIGHT_X));
const BASE_STRIDE_M = LENGTH_M / MAP.distanceMetric.calibrationSteps;
const GRID_STEP_M = 0.5;
const WINDOW = 8;
const TAU_GRAVITY_S = 1.0;
const TRANSITION_SIGMA_M = 0.28;
const MIN_FEATURE_VARIANCE = 4.0;

function median(values) {
  const sorted = values.filter(Number.isFinite).sort((a, b) => a - b);
  if (!sorted.length) return null;
  return (sorted[(sorted.length - 1) >> 1] + sorted[sorted.length >> 1]) / 2;
}
function mean(values) { return values.length ? values.reduce((a, b) => a + b, 0) / values.length : null; }
function variance(values, average = mean(values)) {
  return values.length > 1 ? values.reduce((s, v) => s + (v - average) ** 2, 0) / (values.length - 1) : 0;
}
function quantile(values, q) {
  const a = values.filter(Number.isFinite).sort((x, y) => x - y);
  if (!a.length) return null;
  const i = (a.length - 1) * q, lo = Math.floor(i), hi = Math.ceil(i);
  return a[lo] + (a[hi] - a[lo]) * (i - lo);
}
function walk(directory) {
  if (!fs.existsSync(directory)) return [];
  return fs.readdirSync(directory, { withFileTypes: true }).flatMap(entry => {
    const file = path.join(directory, entry.name);
    return entry.isDirectory() ? walk(file) : entry.name.endsWith('.jsonl') ? [file] : [];
  });
}
function relative(file) { return path.relative(ROOT, file).replaceAll('\\', '/'); }
function sha256(file) { return crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex'); }
function routeOf(rows) { return rows[0]?.label?.route_id || rows.find(r => r.label?.route_id)?.label.route_id || ''; }
function platformOf(rows, file) { return rows[0]?.platform || (file.includes(`${path.sep}ios${path.sep}`) ? 'ios' : 'android'); }
function deviceOf(rows, platform) { return rows[0]?.device || rows[0]?.device_model || (platform === 'ios' ? 'ios_unknown' : 'android_unknown'); }
function isForward(route) { return !route.endsWith('_REVERSE'); }
function clamp(v, a, b) { return Math.max(a, Math.min(b, v)); }

function parseSession(file) {
  const text = fs.readFileSync(file, 'utf8').trim(), lines = text.split(/\r?\n/);
  let first;
  try { first = JSON.parse(lines[0]); } catch { return null; }
  const initialRoute = first?.label?.route_id || '';
  if (!['4F_CORE_TO_RIGHT_STAIRS', '4F_CORE_TO_RIGHT_STAIRS_REVERSE'].includes(initialRoute)) return null;
  let rows;
  try { rows = lines.map(JSON.parse); }
  catch (error) { return { excluded: true, file: relative(file), route: initialRoute, reason: `parse_error:${error.message}` }; }
  const route = routeOf(rows);
  if (!['4F_CORE_TO_RIGHT_STAIRS', '4F_CORE_TO_RIGHT_STAIRS_REVERSE'].includes(route)) return null;
  const labels = rows.filter(r => r.kind === 'label');
  if (rows.at(-1)?.kind !== 'session_end') return { excluded: true, file: relative(file), route, reason: 'incomplete_session' };
  if (labels.length < 8) return { excluded: true, file: relative(file), route, reason: 'insufficient_route_labels' };
  const endpoint = labels.at(-1)?.label?.location || '';
  if (isForward(route) && !endpoint.includes('오른쪽 계단')) return { excluded: true, file: relative(file), route, reason: 'forward_endpoint_not_right_stair' };
  if (!isForward(route) && !endpoint.includes('코어')) return { excluded: true, file: relative(file), route, reason: 'reverse_endpoint_not_core' };

  const platform = platformOf(rows, file), device = deviceOf(rows, platform);
  const startTime = rows[0].wall_time_ms;
  const endTime = labels.at(-1).wall_time_ms;
  const sign = isForward(route) ? 1 : -1;
  let tracker = Position.createPositionTracker({ floor: 4, x: CORE_X, initialDirectionSign: -1 });
  let gravity = null, gravityTime = null, pendingMag = [], stepOrdinal = 0;
  const steps = [];
  for (const row of rows) {
    const time = row.wall_time_ms;
    if (!Number.isFinite(time) || time < startTime || time > endTime) continue;
    if (row.sensor === 'accelerometer_mps2' && Array.isArray(row.values) && row.values.length >= 3) {
      if (!gravity) gravity = row.values.slice(0, 3);
      else {
        const dt = clamp((time - gravityTime) / 1000, 0.001, 0.2);
        const alpha = 1 - Math.exp(-dt / TAU_GRAVITY_S);
        gravity = gravity.map((v, i) => v + alpha * (row.values[i] - v));
      }
      gravityTime = time;
      const update = Position.updatePositionAcceleration(tracker, time, row.values);
      tracker = update.state;
      if (update.detected) {
        stepOrdinal++;
        const norm = median(pendingMag.map(x => x.norm));
        const mv = median(pendingMag.map(x => x.mv));
        steps.push({ time, ordinal: stepOrdinal, peak: update.peak, norm, mv, magneticSamples: pendingMag.length });
        pendingMag = [];
      }
    } else if (row.sensor === 'magnetic_field_ut' && gravity && Array.isArray(row.values) && row.values.length >= 3) {
      const norm = Math.hypot(...row.values.slice(0, 3));
      const gNorm = Math.hypot(...gravity);
      const mv = gNorm > 1 ? row.values.slice(0, 3).reduce((s, v, i) => s + v * gravity[i] / gNorm, 0) : null;
      pendingMag.push({ norm, mv });
    }
  }
  if (steps.length < 40) return { excluded: true, file: relative(file), route, reason: `too_few_detected_steps:${steps.length}` };
  const usable = steps.filter(s => Number.isFinite(s.norm) && Number.isFinite(s.mv));
  if (usable.length < steps.length * 0.8) return { excluded: true, file: relative(file), route, reason: `insufficient_step_features:${usable.length}/${steps.length}` };
  const normOrigin = mean(usable.slice(0, WINDOW).map(s => s.norm));
  const mvOrigin = mean(usable.slice(0, WINDOW).map(s => s.mv));
  for (const step of steps) {
    const progress = step.ordinal / steps.length;
    step.truthM = isForward(route) ? progress * LENGTH_M : LENGTH_M * (1 - progress);
    step.normDelta = Number.isFinite(step.norm) ? step.norm - normOrigin : null;
    step.mvDelta = Number.isFinite(step.mv) ? step.mv - mvOrigin : null;
  }
  const pdrEnd = clamp((isForward(route) ? 0 : LENGTH_M) + sign * steps.length * BASE_STRIDE_M, 0, LENGTH_M);
  const truthEnd = isForward(route) ? LENGTH_M : 0;
  return {
    file: relative(file), basename: path.basename(file), sha256: sha256(file), platform, device, route,
    direction: isForward(route) ? 'forward' : 'reverse', sign, steps,
    alignment: 'confirmed_endpoints_then_detected_step_progress', endpointAlignedStrideM: LENGTH_M / steps.length,
    fixedStrideM: BASE_STRIDE_M, pdrTerminalErrorM: Math.abs(pdrEnd - truthEnd), labels: labels.length,
  };
}

function buildGrid(training, feature) {
  const cells = [];
  for (let x = 0; x <= LENGTH_M + 1e-9; x += GRID_STEP_M) {
    const values = [];
    const sources = new Set();
    for (const session of training) for (const step of session.steps) {
      if (Math.abs(step.truthM - x) <= GRID_STEP_M * 0.75 && Number.isFinite(step[feature])) {
        values.push(step[feature]); sources.add(session.file);
      }
    }
    const average = mean(values);
    cells.push({ x: Number(x.toFixed(3)), mean: average, variance: average === null ? null : variance(values, average), samples: values.length, sessions: sources.size });
  }
  // A 0.5 m grid is dense enough for the current step spacing. Only fill a rare
  // single empty cell between two measured cells; do not extrapolate into gaps.
  for (let i = 1; i < cells.length - 1; i++) if (cells[i].mean === null && cells[i - 1].mean !== null && cells[i + 1].mean !== null) {
    cells[i].mean = (cells[i - 1].mean + cells[i + 1].mean) / 2;
    cells[i].variance = Math.max(cells[i - 1].variance || 0, cells[i + 1].variance || 0, MIN_FEATURE_VARIANCE);
    cells[i].interpolated = true;
  }
  return cells;
}
function cellAt(cells, x) { return cells[clamp(Math.round(x / GRID_STEP_M), 0, cells.length - 1)]; }
function normalizeWeights(weights) {
  const sum = weights.reduce((a, b) => a + b, 0);
  if (!(sum > 0)) return weights.map(() => 1 / weights.length);
  return weights.map(v => v / sum);
}
function gaussian(value, meanValue, varianceValue) {
  const v = Math.max(MIN_FEATURE_VARIANCE, varianceValue || 0);
  return Math.exp(-0.5 * (value - meanValue) ** 2 / v);
}
function summarizeErrors(errors) {
  return { meanM: mean(errors), medianM: quantile(errors, .5), p90M: quantile(errors, .9), maxM: errors.length ? Math.max(...errors) : null };
}
function baseline(session) {
  let x = session.direction === 'forward' ? 0 : LENGTH_M;
  const rows = [];
  for (const step of session.steps) {
    x = clamp(x + session.sign * BASE_STRIDE_M, 0, LENGTH_M);
    rows.push({ estimateM: x, truthM: step.truthM, errorM: Math.abs(x - step.truthM) });
  }
  return rows;
}
function sequenceDistance(query, reference, features) {
  const values = features.map(feature => Sequence.distance(query.map(s => s[feature]), reference.map(s => s[feature])));
  return values.every(Number.isFinite) ? mean(values) : Infinity;
}
function sequenceVariant(session, training, features) {
  const references = [];
  for (const source of training.filter(s => s.direction === session.direction)) {
    for (let end = WINDOW - 1; end < source.steps.length; end += 2) {
      const window = source.steps.slice(end - WINDOW + 1, end + 1);
      if (features.every(f => window.every(s => Number.isFinite(s[f])))) references.push({ source: source.file, x: window.at(-1).truthM, window });
    }
  }
  let x = session.direction === 'forward' ? 0 : LENGTH_M;
  const rows = [], stats = { evaluated: 0, applied: 0, noReference: 0, ambiguous: 0 };
  for (let i = 0; i < session.steps.length; i++) {
    x = clamp(x + session.sign * BASE_STRIDE_M, 0, LENGTH_M);
    if ((i + 1) % WINDOW === 0) {
      stats.evaluated++;
      const window = session.steps.slice(i - WINDOW + 1, i + 1);
      const candidates = references.filter(r => Math.abs(r.x - x) <= 12)
        .map(r => ({ ...r, score: sequenceDistance(window, r.window, features) }))
        .filter(r => Number.isFinite(r.score)).sort((a, b) => a.score - b.score);
      const best = candidates[0];
      if (!best) stats.noReference++;
      else {
        const alternative = candidates.find(r => Math.abs(r.x - best.x) > 4.25);
        const margin = alternative ? alternative.score - best.score : 0;
        if (best.score <= .5 && margin >= .08) { x = clamp(x + .25 * (best.x - x), 0, LENGTH_M); stats.applied++; }
        else stats.ambiguous++;
      }
    }
    rows.push({ estimateM: x, truthM: session.steps[i].truthM, errorM: Math.abs(x - session.steps[i].truthM) });
  }
  return { rows, stats, references: references.length };
}
function gridVariant(session, training, features) {
  const grids = Object.fromEntries(features.map(feature => [feature, buildGrid(training, feature)]));
  const positions = grids[features[0]].map(c => c.x);
  const start = session.direction === 'forward' ? 0 : LENGTH_M;
  // Calibrate a constant device/session offset from the first eight steps at a
  // known start. This is causal and works for either direction because it is
  // referenced to the absolute training grid, not to a direction-specific zero.
  const offsets = Object.fromEntries(features.map(feature => {
    const residuals = session.steps.slice(0, WINDOW).map(step => {
      const expectedX = clamp(start + session.sign * BASE_STRIDE_M * step.ordinal, 0, LENGTH_M);
      const expected = cellAt(grids[feature], expectedX)?.mean;
      return Number.isFinite(step[feature]) && Number.isFinite(expected) ? step[feature] - expected : null;
    }).filter(Number.isFinite);
    return [feature, median(residuals) || 0];
  }));
  let weights = positions.map(x => Math.exp(-0.5 * ((x - (session.direction === 'forward' ? 0 : LENGTH_M)) / .55) ** 2));
  weights = normalizeWeights(weights);
  const rows = [];
  for (const step of session.steps) {
    const predicted = positions.map(() => 0);
    for (let i = 0; i < positions.length; i++) for (let j = 0; j < positions.length; j++) {
      const target = positions[j] + session.sign * BASE_STRIDE_M;
      predicted[i] += weights[j] * Math.exp(-0.5 * ((positions[i] - target) / TRANSITION_SIGMA_M) ** 2);
    }
    weights = normalizeWeights(predicted);
    if (step.ordinal > WINDOW && features.every(f => Number.isFinite(step[f]))) {
      weights = weights.map((weight, i) => {
        let likelihood = 1;
        for (const feature of features) {
          const cell = cellAt(grids[feature], positions[i]);
          if (cell?.mean === null || cell?.sessions < 1) continue;
          likelihood *= Math.pow(gaussian(step[feature] - offsets[feature], cell.mean, cell.variance), .35 / features.length);
        }
        return weight * (.08 + .92 * likelihood);
      });
      weights = normalizeWeights(weights);
    }
    const estimateM = positions.reduce((s, x, i) => s + x * weights[i], 0);
    rows.push({ estimateM, truthM: step.truthM, errorM: Math.abs(estimateM - step.truthM) });
  }
  return { rows, offsets, coverage: Object.fromEntries(features.map(f => [f, grids[f].filter(c => c.mean !== null).length / grids[f].length])) };
}

function summarizeVariant(rows) {
  const all = rows.flatMap(r => r.rows.map(x => x.errorM));
  const terminal = rows.map(r => r.rows.at(-1).errorM);
  const arrival = rows.map(r => {
    const endpoint = r.direction === 'forward' ? LENGTH_M : 0;
    const index = r.rows.findIndex(x => Math.abs(x.estimateM - endpoint) <= 1);
    const arrivalStep = index < 0 ? null : index + 1;
    return { arrivalStep, totalSteps: r.rows.length, stepDifference: arrivalStep === null ? null : arrivalStep - r.rows.length,
      equivalentM: arrivalStep === null ? null : Math.abs(arrivalStep - r.rows.length) * LENGTH_M / r.rows.length };
  });
  return { trajectoryWeakTruth: summarizeErrors(all), terminalConfirmedEndpoint: summarizeErrors(terminal),
    arrivalWithin1m: { reached: arrival.filter(x => x.arrivalStep !== null).length,
      medianStepDifference: quantile(arrival.map(x => x.stepDifference), .5),
      medianTimingErrorEquivalentM: quantile(arrival.map(x => x.equivalentM), .5) }, sessions: rows.length };
}

const parsed = walk(RAW).map(parseSession).filter(Boolean);
const excluded = parsed.filter(s => s.excluded);
const sessions = parsed.filter(s => !s.excluded);
if (sessions.length < 4) throw new Error(`Need at least 4 complete sessions, found ${sessions.length}`);
const legacySurveyDistanceM = SURVEY.core_center_to_right_end.reference_length_m;
const legacySurveyDifferenceM = LENGTH_M - legacySurveyDistanceM;
// The shared 2F-10F corridor survey is now the runtime authority.  The older
// floor-04 survey remains provenance for the original scan, so tolerate only
// the small core-width update and fail on a material geometry disagreement.
if (Math.abs(legacySurveyDifferenceM) > 0.05) throw new Error('Runtime and legacy 4F survey distance materially disagree');

const foldRows = [];
for (const query of sessions) {
  const training = sessions.filter(s => s.file !== query.file && s.platform === query.platform);
  if (!training.length) continue;
  const base = baseline(query);
  const e0 = sequenceVariant(query, training, ['norm']);
  const e1 = sequenceVariant(query, training, ['norm', 'mv']);
  const e2 = gridVariant(query, training, ['normDelta']);
  const e3 = gridVariant(query, training, ['normDelta', 'mvDelta']);
  foldRows.push({
    file: query.file, sha256: query.sha256, platform: query.platform, device: query.device,
    direction: query.direction, steps: query.steps.length, endpointAlignedStrideM: query.endpointAlignedStrideM,
    baseline: { rows: base }, e0: { rows: e0.rows, stats: e0.stats, references: e0.references },
    e1: { rows: e1.rows, stats: e1.stats, references: e1.references },
    e2: { rows: e2.rows, offsets: e2.offsets, coverage: e2.coverage }, e3: { rows: e3.rows, offsets: e3.offsets, coverage: e3.coverage },
  });
}
const variantKeys = ['baseline', 'e0', 'e1', 'e2', 'e3'];
function groupSummary(rows) {
  return Object.fromEntries(variantKeys.map(key => [key, summarizeVariant(rows.map(r => ({ rows: r[key].rows, direction: r.direction }))) ]));
}
const summary = {
  all: groupSummary(foldRows),
  byPlatform: Object.fromEntries([...new Set(foldRows.map(r => r.platform))].map(p => [p, groupSummary(foldRows.filter(r => r.platform === p))])),
  byDirection: Object.fromEntries([...new Set(foldRows.map(r => r.direction))].map(d => [d, groupSummary(foldRows.filter(r => r.direction === d))])),
};
function paired(rows) {
  const value = (row, key) => mean(row[key].rows.map(x => x.errorM));
  return {
    sessions: rows.length,
    beatsBaseline: Object.fromEntries(['e0', 'e1', 'e2', 'e3'].map(key => [key, rows.filter(r => value(r, key) < value(r, 'baseline')).length])),
    mvBeatsMagnitude: { sequence: rows.filter(r => value(r, 'e1') < value(r, 'e0')).length,
      grid: rows.filter(r => value(r, 'e3') < value(r, 'e2')).length },
  };
}
summary.pairedComparisons = { all: paired(foldRows),
  byPlatform: Object.fromEntries([...new Set(foldRows.map(r => r.platform))].map(p => [p, paired(foldRows.filter(r => r.platform === p))])) };
const compactFolds = foldRows.map(row => ({
  file: row.file, sha256: row.sha256, platform: row.platform, device: row.device, direction: row.direction,
  steps: row.steps, endpointAlignedStrideM: row.endpointAlignedStrideM,
  variants: Object.fromEntries(variantKeys.map(key => [key, {
    ...summarizeVariant([{ rows: row[key].rows, direction: row.direction }]),
    ...(row[key].stats ? { sequence: row[key].stats, references: row[key].references } : {}),
    ...(row[key].coverage ? { coverage: row[key].coverage } : {}),
  }]))
}));

const productionCandidate = { version: '4f-right-magnetic-grid-review-20260921', runtimeDefault: false,
  coordinate: { origin: '4F core center', destination: 'right stair entrance before entering stairs', lengthM: LENGTH_M, gridStepM: GRID_STEP_M },
  calibration: { method: 'median offset of first 8 detected steps versus absolute grid near known start', causalAfterStep: 8 }, platforms: {} };
for (const platform of [...new Set(sessions.map(s => s.platform))]) {
  const training = sessions.filter(s => s.platform === platform);
  productionCandidate.platforms[platform] = {
    sessions: training.map(s => ({ file: s.file, sha256: s.sha256, direction: s.direction, steps: s.steps.length })),
    norm: buildGrid(training, 'norm'), mv: buildGrid(training, 'mv'),
  };
}
const aligned = {
  version: 1, coordinate: productionCandidate.coordinate,
  method: 'confirmed endpoints with detected-step progress; intermediate positions are weak labels',
  sessions: sessions.map(session => ({
    file: session.file, sha256: session.sha256, platform: session.platform, device: session.device,
    direction: session.direction, detectedSteps: session.steps.length, endpointAlignedStrideM: session.endpointAlignedStrideM,
    points: session.steps.map((step, index) => ({ step: step.ordinal, timeMsFromFirstStep: step.time - session.steps[0].time,
      distanceMFromCore: step.truthM, magneticMagnitudeUt: step.norm, magneticVerticalUt: step.mv,
      magneticSamples: step.magneticSamples, accelerationPeakMps2: step.peak })),
  })),
};
function gridDiagnostics(cells) {
  const measured = cells.filter(cell => cell.mean !== null), deviations = measured.map(cell => Math.sqrt(cell.variance || 0));
  const sessionCounts = measured.map(cell => cell.sessions);
  return { cells: cells.length, measuredCells: measured.length, rangeUt: Math.max(...measured.map(c => c.mean)) - Math.min(...measured.map(c => c.mean)),
    medianCellStandardDeviationUt: quantile(deviations, .5), minIndependentSessionsPerCell: Math.min(...sessionCounts),
    medianIndependentSessionsPerCell: quantile(sessionCounts, .5) };
}
const gridDiagnosticsByPlatform = Object.fromEntries(Object.entries(productionCandidate.platforms).map(([platform, value]) => [platform,
  { magnitude: gridDiagnostics(value.norm), vertical: gridDiagnostics(value.mv) }]));

const result = {
  version: 1, createdAt: new Date().toISOString(), runtimeChanged: false,
  coordinate: { lengthM: LENGTH_M, basis: 'navigation distanceMetric from the shared 2F-10F corridor survey',
    legacyFloor4Survey: SURVEY.core_center_to_right_end, legacySurveyDifferenceM,
    baseStrideM: BASE_STRIDE_M, diagramCoordinateNotMeters: Math.abs(CORE_X - RIGHT_X) },
  extraction: { stepDetector: 'app/expo-sensor-collector/positionTracking.js', gravity: `causal vector EMA tau=${TAU_GRAVITY_S}s`, mv: 'dot(magnetic, unit_gravity)', calibration: 'first 8 steps estimate a constant offset against the absolute training grid near the known start', intermediateTruth: 'linear detected-step progress between confirmed endpoints' },
  dataset: { included: sessions.map(s => ({ file: s.file, sha256: s.sha256, platform: s.platform, device: s.device, direction: s.direction, steps: s.steps.length, labels: s.labels, endpointAlignedStrideM: s.endpointAlignedStrideM, fixedPdrTerminalErrorM: s.pdrTerminalErrorM })), excluded },
  variants: {
    baseline: 'fixed-stride PDR only', e0: '8-step magnitude session templates, current thresholds, 25% accepted correction',
    e1: 'E0 plus vertical magnetic component', e2: '0.5m 1D absolute grid HMM using start-calibrated magnitude',
    e3: 'E2 plus start-calibrated vertical magnetic component',
  }, gridDiagnostics: gridDiagnosticsByPlatform, summary, folds: compactFolds,
  limitations: [
    'Intermediate truth is endpoint-aligned detected-step progress, not surveyed foot position.',
    'Confirmed endpoint error is stronger evidence than intermediate trajectory error.',
    'All sessions are the same user; platform-specific grids are evaluated separately.',
    'm_v uses a causal accelerometer-vector EMA because TYPE_GRAVITY was not recorded.',
    'Thresholds and grid-filter constants were fixed before examining this run and were not tuned on held-out folds.',
    'The candidate grid is an offline review artifact and is not loaded by the app.',
  ],
};

fs.mkdirSync(OUTPUT, { recursive: true });
fs.writeFileSync(path.join(OUTPUT, 'evaluation.json'), `${JSON.stringify(result, null, 2)}\n`);
fs.writeFileSync(path.join(OUTPUT, 'grid-4f-right.json'), `${JSON.stringify(productionCandidate, null, 2)}\n`);
fs.writeFileSync(path.join(OUTPUT, 'aligned-sessions.json'), `${JSON.stringify(aligned, null, 2)}\n`);
console.log(JSON.stringify({ coordinate: result.coordinate, dataset: { included: sessions.length, excluded: excluded.length }, summary }, null, 2));
