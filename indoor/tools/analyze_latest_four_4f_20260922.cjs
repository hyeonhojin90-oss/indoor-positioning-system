const fs = require('node:fs');
const path = require('node:path');
const Runtime = require('../web/src/positioning/runtime');
const Navigation = require('../web/src/positioning/navigation');
const navigation = require('../web/data/navigation/areas-v1.json');
const models = require('../web/data/positioning/motion-models.json');
const floorMap = require('../web/data/maps/floor-04.json');
const zoneReferences = require('../web/data/positioning/zone-references.json').references;
const bleReferences = require('../web/data/positioning/ble-references.json').references;

const ROOT = path.resolve(__dirname, '../..');
const INPUT = path.resolve(process.argv[2] || path.join(ROOT, 'indoor/data/raw/android/2026-09-22/latest-four'));
const OUTPUT = path.resolve(process.argv[3] || path.join(ROOT, 'indoor/data/analysis/latest-four-4f-20260922'));
const map = Navigation.compile(navigation, 4);
const CORE_X = 70.804;
const RIGHT_X = map.distanceMetric.mapBreaks[0];
const LEFT_X = map.distanceMetric.mapBreaks.at(-1);
const references = [...zoneReferences, ...bleReferences];

const mean = a => a.length ? a.reduce((s, x) => s + x, 0) / a.length : null;
const median = a => {
  const b = a.filter(Number.isFinite).sort((x, y) => x - y);
  return b.length ? (b[(b.length - 1) >> 1] + b[b.length >> 1]) / 2 : null;
};
const metric = x => Navigation.metricDistance(map, x);
const yaw = values => {
  const [x, y, z, w0] = values;
  const w = Number.isFinite(w0) ? w0 : Math.sqrt(Math.max(0, 1 - x*x - y*y - z*z));
  return (Math.atan2(2 * (w*z + x*y), 1 - 2 * (y*y + z*z)) * 180 / Math.PI + 360) % 360;
};
function routeInfo(route) {
  const reverse = route.endsWith('_REVERSE');
  const right = route.includes('_RIGHT_');
  return {
    reverse, right,
    startX: reverse ? (right ? RIGHT_X : LEFT_X) : CORE_X,
    sign: reverse ? (right ? 1 : -1) : (right ? -1 : 1),
    endpointX: reverse ? CORE_X : (right ? RIGHT_X : LEFT_X),
  };
}
function truthX(location) {
  if (location.includes('코어복도')) return CORE_X;
  if (location.includes('오른쪽 계단')) return RIGHT_X;
  if (location.includes('왼쪽 계단')) return LEFT_X;
  const id = location.match(/4\d{3}/)?.[0];
  const room = id && floorMap.rooms.find(r => r.id === id);
  return room ? (room.front_x ?? room.x) : null;
}
function replay(rows, mode4, seedX = null, directionSeed) {
  const route = rows[0].label.route_id;
  const info = routeInfo(route);
  const endTime = rows.filter(row => row.kind === 'label').at(-1).wall_time_ms;
  const runtime = Runtime.create(navigation, models, mode4 ? references : [], {
    floor: 4, x: seedX ?? info.startX, y: 0, platform: 'android', device: rows[0].device,
    initialDirectionSign: directionSeed === undefined ? info.sign : directionSeed,
    sequenceEnabled: mode4, bleEnabled: mode4,
  });
  const laps = [];
  let detectedSteps = 0;
  const hasRecordedFusionHeading = rows.some(row => row.sensor === 'heading_degrees');
  let latestHeading = null;
  let lastHeadingSent = null;
  let lastHeadingSentTime = -Infinity;
  for (const row of rows) {
    const t = row.kind === 'sample' && Number.isFinite(row.sensor_wall_time_ms)
      ? row.sensor_wall_time_ms : row.wall_time_ms;
    if (!Number.isFinite(t) || t > endTime) continue;
    if (row.sensor === 'heading_degrees') Runtime.heading(runtime, t, row.values?.[0], 3);
    else if (row.sensor === 'rotation_vector' && !hasRecordedFusionHeading) latestHeading = Math.round(yaw(row.values));
    else if (row.sensor === 'magnetic_field_ut') Runtime.magnetic(runtime, t, row.values);
    else if (row.sensor === 'pressure_hpa') Runtime.pressure(runtime, t, row.values?.[0]);
    else if (row.kind === 'ble_observation' && mode4) Runtime.ble(runtime, t, row);
    else if (row.sensor === 'accelerometer_mps2' && Runtime.acceleration(runtime, t, row.values)) detectedSteps++;
    // Android sends rounded heading after rotation, magnetic, pressure, and step-counter callbacks.
    // Acceleration is forwarded first but does not trigger a heading update.
    if (!hasRecordedFusionHeading && latestHeading !== null && ['rotation_vector', 'magnetic_field_ut', 'pressure_hpa', 'step_counter'].includes(row.sensor)) {
      if (latestHeading !== lastHeadingSent || t - lastHeadingSentTime >= 750) {
        Runtime.heading(runtime, t, latestHeading, 3);
        lastHeadingSent = latestHeading;
        lastHeadingSentTime = t;
      }
    }
    if (row.kind === 'label') {
      const x = truthX(row.label.location);
      const snapshot = Runtime.snapshot(runtime, []);
      laps.push({
        label: row.label.location, estimateX: snapshot.x,
        estimateM: metric(snapshot.x), truthX: x,
        truthM: Number.isFinite(x) ? metric(x) : null,
        errorM: Number.isFinite(x) ? Math.abs(metric(snapshot.x) - metric(x)) : null,
      });
    }
  }
  const snapshot = Runtime.snapshot(runtime, []);
  return {
    detectedSteps,
    endpointEstimateM: metric(snapshot.x), endpointTruthM: metric(info.endpointX),
    endpointErrorM: Math.abs(metric(snapshot.x) - metric(info.endpointX)),
    weakLapMeanM: mean(laps.map(x => x.errorM).filter(Number.isFinite)),
    sequence: snapshot.sequenceStats, ble: snapshot.bleStats, laps,
  };
}
function fingerprint(rows) {
  const groups = new Map();
  for (const row of rows) if (row.kind === 'ble_observation' && row.anonymous_id && Number.isFinite(row.rssi_dbm)) {
    if (!groups.has(row.anonymous_id)) groups.set(row.anonymous_id, []);
    groups.get(row.anonymous_id).push(row.rssi_dbm);
  }
  return Object.fromEntries([...groups].map(([id, values]) => [id, median(values)]));
}
function identitySets(rows) {
  const ble = rows.filter(row => row.kind === 'ble_observation');
  return {
    address: new Set(ble.map(row => row.anonymous_id).filter(Boolean)),
    manufacturerPayload: new Set(ble.flatMap(row => row.manufacturer_payload_hashes || [])),
    servicePayload: new Set(ble.flatMap(row => row.service_data_hashes || [])),
    serviceUuid: new Set(ble.flatMap(row => row.service_uuids || [])),
  };
}
function compareFingerprints(a, b) {
  if (!a || !b) return { commonIds: null, medianAbsoluteRssiDifferenceDb: null, unavailable: true };
  const common = Object.keys(a).filter(id => Number.isFinite(b[id]));
  return { commonIds: common.length, medianAbsoluteRssiDifferenceDb: median(common.map(id => Math.abs(a[id] - b[id]))) };
}
function savedPredictionEvaluation(rows) {
  const predictions = rows.filter(row => row.kind === 'derived_fusion');
  const labels = rows.filter(row => row.kind === 'label');
  const laps = labels.map(label => {
    const prediction = predictions.findLast(row => row.wall_time_ms <= label.wall_time_ms);
    const truth = truthX(label.label.location);
    const baselineX = prediction?.baseline_pdr?.matched_x;
    return {
      label: label.label.location, predictionGapMs: prediction ? label.wall_time_ms - prediction.wall_time_ms : null,
      steps: prediction?.steps ?? null, mode4X: prediction?.x ?? null, baselineX: baselineX ?? null,
      truthX: truth,
      mode4ErrorM: prediction && Number.isFinite(truth) ? Math.abs(metric(prediction.x) - metric(truth)) : null,
      baselineErrorM: Number.isFinite(baselineX) && Number.isFinite(truth) ? Math.abs(metric(baselineX) - metric(truth)) : null,
      zone: prediction?.zone ?? null, spread: prediction?.spread ?? null,
      sequenceApplied: prediction?.sequenceStats?.applied ?? 0,
      bleApplied: prediction?.bleStats?.applied ?? 0,
    };
  });
  const endpoint = laps.at(-1);
  return {
    predictions: predictions.length, endpoint,
    weakLapMode4MeanM: mean(laps.map(x => x.mode4ErrorM).filter(Number.isFinite)),
    weakLapBaselineMeanM: mean(laps.map(x => x.baselineErrorM).filter(Number.isFinite)), laps,
  };
}

const sessions = fs.readdirSync(INPUT).filter(x => x.endsWith('.jsonl')).sort().map(file => {
  const text = fs.readFileSync(path.join(INPUT, file), 'utf8').trim();
  const rows = text.split(/\r?\n/).map(JSON.parse);
  const labels = rows.filter(r => r.kind === 'label');
  const start = rows[0], end = rows.at(-1);
  const kinds = rows.reduce((o, r) => (o[r.kind] = (o[r.kind] || 0) + 1, o), {});
  const fp = fingerprint(rows);
  const identities = identitySets(rows);
  const productionIds = new Set(bleReferences.filter(r => r.floor === 4).flatMap(r => Object.keys(r.ble || {})));
  const route = start.label.route_id;
  const reverseSide = route.endsWith('_REVERSE') ? (route.includes('_RIGHT_') ? 'stairs_right' : 'stairs_left') : null;
  const oldArea = map.areas.find(area => area.id === reverseSide);
  const oldSeedX = oldArea ? (oldArea.rect[0] + oldArea.rect[2]) / 2 : null;
  const oldSeedReplay = oldSeedX === null ? null : replay(rows, true, oldSeedX);
  const correctedSeedReplay = oldSeedX === null ? null : replay(rows, true);
  const unseededDirectionReplay = replay(rows, true, null, null);
  return {
    file, route, durationS: (end.wall_time_ms - start.wall_time_ms) / 1000,
    schema: start.schema_version, ended: end.kind === 'session_end', parseErrors: 0,
    labelCount: labels.length, labels: labels.map(r => r.label.location),
    duplicateSuffixLabels: labels.map(r => r.label.location).filter(x => /앞 앞$/.test(x)),
    stepCounterDelta: end.steps_since_start, kinds,
    bleUniqueIds: Object.keys(fp).length, bleFingerprint: fp, identities,
    productionBleReferenceCommonIds: [...identities.address].filter(id => productionIds.has(id)).length,
    reverseSeedAblation: oldSeedReplay && {
      oldSeedX, correctedSeedX: routeInfo(route).startX,
      oldEndpointErrorM: oldSeedReplay.endpointErrorM,
      correctedEndpointErrorM: correctedSeedReplay.endpointErrorM,
    },
    directionSeedAblation: {
      unseededEndpointErrorM: unseededDirectionReplay.endpointErrorM,
      seededEndpointErrorM: replay(rows, true).endpointErrorM,
    },
    pdr: replay(rows, false), mode4: replay(rows, true), saved: savedPredictionEvaluation(rows),
  };
});

const byRoute = Object.fromEntries(sessions.map(s => [s.route, s]));
const pairs = [
  ['right', byRoute['4F_CORE_TO_RIGHT_STAIRS'], byRoute['4F_CORE_TO_RIGHT_STAIRS_REVERSE']],
  ['left', byRoute['4F_CORE_TO_LEFT_STAIRS'], byRoute['4F_CORE_TO_LEFT_STAIRS_REVERSE']],
].map(([side, a, b]) => ({side, ...compareFingerprints(a?.bleFingerprint, b?.bleFingerprint),
  commonManufacturerPayloadIds: a && b ? [...a.identities.manufacturerPayload].filter(id => b.identities.manufacturerPayload.has(id)).length : null,
  commonServicePayloadIds: a && b ? [...a.identities.servicePayload].filter(id => b.identities.servicePayload.has(id)).length : null,
  commonServiceUuids: a && b ? [...a.identities.serviceUuid].filter(id => b.identities.serviceUuid.has(id)).length : null,
}));
for (const session of sessions) {
  session.bleIdentityCounts = Object.fromEntries(Object.entries(session.identities).map(([key, value]) => [key, value.size]));
  delete session.bleFingerprint;
  delete session.identities;
}

const report = {
  version: 1, createdAt: new Date().toISOString(), files: sessions.length,
  coordinate: {rightCoreToStairM: metric(CORE_X) - metric(RIGHT_X), leftCoreToStairM: metric(LEFT_X) - metric(CORE_X)},
  sessions, bleWholeRouteRepeatability: pairs,
  summary: {
    pdrEndpointMeanM: mean(sessions.map(s => s.pdr.endpointErrorM)),
    mode4EndpointMeanM: mean(sessions.map(s => s.mode4.endpointErrorM)),
    savedMode4EndpointMeanM: mean(sessions.map(s => s.saved.endpoint?.mode4ErrorM).filter(Number.isFinite)),
    savedBaselineEndpointMeanM: mean(sessions.map(s => s.saved.endpoint?.baselineErrorM).filter(Number.isFinite)),
    pdrWeakLapMeanM: mean(sessions.map(s => s.pdr.weakLapMeanM)),
    mode4WeakLapMeanM: mean(sessions.map(s => s.mode4.weakLapMeanM)),
    replaySequenceApplied: sessions.reduce((n, s) => n + s.mode4.sequence.applied, 0),
    replayBleApplied: sessions.reduce((n, s) => n + s.mode4.ble.applied, 0),
    savedSequenceAppliedAtArrival: sessions.reduce((n, s) => n + (s.saved.endpoint?.sequenceApplied || 0), 0),
    savedBleAppliedAtArrival: sessions.reduce((n, s) => n + (s.saved.endpoint?.bleApplied || 0), 0),
    productionBleReferenceCommonIds: sessions.map(s => s.productionBleReferenceCommonIds),
  },
  limitations: [
    'Only route endpoints are confirmed physical truth. Classroom-front lap coordinates are diagram-derived weak truth.',
    'Whole-route BLE comparison measures repeatability, not point-level localization.',
    'The files contain no saved derived prediction rows, so offline replay is required to assess mode 4.',
  ],
};
fs.mkdirSync(OUTPUT, {recursive: true});
fs.writeFileSync(path.join(OUTPUT, 'analysis.json'), JSON.stringify(report, null, 2) + '\n');
console.log(JSON.stringify({summary: report.summary, coordinate: report.coordinate, pairs,
  sessions: sessions.map(s => ({file:s.file, route:s.route, counter:s.stepCounterDelta,
    detected:s.pdr.detectedSteps, pdrEnd:s.pdr.endpointErrorM, mode4End:s.mode4.endpointErrorM,
    savedPredictions:s.saved.predictions, savedMode4End:s.saved.endpoint?.mode4ErrorM,
    savedBaselineEnd:s.saved.endpoint?.baselineErrorM, savedX:s.saved.endpoint?.mode4X,
    pdrWeak:s.pdr.weakLapMeanM, mode4Weak:s.mode4.weakLapMeanM,
    sequence:s.mode4.sequence, ble:s.mode4.ble, bleUniqueIds:s.bleUniqueIds,
    productionCommon:s.productionBleReferenceCommonIds, identityCounts:s.bleIdentityCounts,
    badLabels:s.duplicateSuffixLabels}))}, null, 2));
