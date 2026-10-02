// Analysis-only 4F right-corridor replay for a detector-confidence model.
//
// This deliberately does not alter the PDR distance estimate or any runtime
// file.  The question here is narrower: can low-quality peak/interval evidence
// identify a walk whose fixed-stride endpoint needs a wider particle cloud?
// Since the local logs have endpoint labels but no hand-labelled individual
// steps, this is an uncertainty-calibration experiment, not a new step model.
const fs = require('fs');
const path = require('path');
const { createPositionTracker, updatePositionAcceleration } = require('../../app/expo-sensor-collector/positionTracking');

const root = path.resolve(__dirname, '../..');
const survey = require('../web/data/maps/floor-04-survey.json');
const distanceMeters = survey.core_center_to_right_end.reference_length_m;
const currentFixedMeters = distanceMeters / 81;

const clamp = (value, low, high) => Math.max(low, Math.min(high, value));
const mean = values => values.reduce((sum, value) => sum + value, 0) / values.length;
const median = values => {
  const sorted = [...values].sort((a, b) => a - b);
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
};
const quantile = (values, q) => {
  const sorted = [...values].sort((a, b) => a - b);
  if (!sorted.length) return null;
  const index = (sorted.length - 1) * q;
  const low = Math.floor(index), high = Math.ceil(index);
  return sorted[low] + (sorted[high] - sorted[low]) * (index - low);
};

function weightedMedianStride(rows) {
  const sorted = rows.map(row => ({ stride: distanceMeters / row.events.length, weight: row.events.length }))
    .sort((a, b) => a.stride - b.stride);
  const total = sorted.reduce((sum, row) => sum + row.weight, 0);
  let accumulated = 0;
  for (const row of sorted) {
    accumulated += row.weight;
    if (accumulated >= total / 2) return row.stride;
  }
  return sorted.at(-1).stride;
}

function sourceFiles(external) {
  return [
    ...fs.readdirSync(path.join(root, 'indoor/data/raw/ios/2026-09-05')).map(name => path.join(root, 'indoor/data/raw/ios/2026-09-05', name)),
    ...fs.readdirSync(path.join(root, 'indoor/data/raw/ios/2026-09-08')).map(name => path.join(root, 'indoor/data/raw/ios/2026-09-08', name)),
    ...['133338', '133534', '133637', '133734'].map(id => path.join(external, `indoor_positioning_ios_20260914_${id}.jsonl`)),
    ...fs.readdirSync(path.join(root, 'indoor/data/raw/ios/2026-09-14')).map(name => path.join(root, 'indoor/data/raw/ios/2026-09-14', name))
  ];
}

function nearestGyroNorm(gyro, time) {
  // Gyro is preserved as a diagnostic feature only.  It is intentionally not
  // part of the score until a step-labelled external set validates its sign.
  let nearest = null;
  for (const row of gyro) {
    const delta = Math.abs(row.time - time);
    if (delta > 150 || (nearest && delta >= nearest.delta)) continue;
    nearest = { delta, norm: row.norm };
  }
  return nearest?.norm ?? null;
}

function confidenceFeatures(events) {
  let varianceEvents = 0;
  let nearThreshold = 0, irregularIntervals = 0, longGaps = 0;
  const enriched = [];
  const priorIntervals = [];

  for (let index = 0; index < events.length; index += 1) {
    const event = events[index];
    const peakQuality = clamp((event.peak - 1.0) / 0.8, 0, 1);
    let intervalQuality = 0.8;
    let missedStepRisk = 0;
    let intervalMs = null;
    if (index > 0) {
      intervalMs = event.time - events[index - 1].time;
      const expected = priorIntervals.length >= 3 ? median(priorIntervals) : null;
      if (expected) {
        const ratio = intervalMs / expected;
        intervalQuality = Math.exp(-Math.abs(Math.log(Math.max(ratio, 0.01))) / 0.55);
        if (intervalQuality < 0.6) irregularIntervals += 1;
        // A large gap can contain an undetected step.  It increases spread but
        // never creates or removes a step in this experiment.
        missedStepRisk = clamp((ratio - 1.55) / 0.70, 0, 1);
        if (missedStepRisk > 0) longGaps += 1;
      }
      priorIntervals.push(intervalMs);
    }
    if (event.peak < 1.25) nearThreshold += 1;
    // Threshold-edge peaks are uncertain, but an accepted peak remains more
    // likely a step than a non-step.  This has no fitted constants.
    const confidence = 0.55 + 0.45 * Math.sqrt(peakQuality * intervalQuality);
    const eventVariance = confidence * (1 - confidence) + missedStepRisk * missedStepRisk;
    varianceEvents += eventVariance;
    enriched.push({ time: event.time, peak: event.peak, intervalMs, peakQuality, intervalQuality,
      missedStepRisk, confidence, gyroNorm: event.gyroNorm, eventVariance });
  }
  const gyroValues = enriched.map(row => row.gyroNorm).filter(Number.isFinite);
  return {
    events: enriched,
    sigmaEvents: Math.sqrt(varianceEvents),
    meanConfidence: mean(enriched.map(row => row.confidence)),
    nearThresholdFraction: nearThreshold / enriched.length,
    irregularIntervalFraction: irregularIntervals / Math.max(1, enriched.length - 1),
    longGapFraction: longGaps / Math.max(1, enriched.length - 1),
    medianGyroNorm: gyroValues.length ? median(gyroValues) : null
  };
}

function load(file) {
  const rows = fs.readFileSync(file, 'utf8').trim().split(/\r?\n/).map(JSON.parse);
  const route = rows[0]?.label?.route_id;
  if (!['4F_CORE_TO_RIGHT_STAIRS', '4F_CORE_TO_RIGHT_STAIRS_REVERSE'].includes(route)) return null;
  let tracker = createPositionTracker({ floor: 4, x: 70.804, initialDirectionSign: -1 });
  const gyro = rows.filter(row => row.sensor === 'gyroscope_rads')
    .map(row => ({ time: row.wall_time_ms, norm: Math.hypot(...row.values) }));
  const events = [];
  for (const row of rows) {
    if (row.sensor !== 'accelerometer_mps2') continue;
    const result = updatePositionAcceleration(tracker, row.wall_time_ms, row.values);
    tracker = result.state;
    if (result.detected) events.push({ time: row.wall_time_ms, peak: result.peak });
  }
  events.forEach(event => { event.gyroNorm = nearestGyroNorm(gyro, event.time); });
  const features = confidenceFeatures(events);
  return {
    file: path.basename(file), route, fresh: /_(170738|170901|171021|171142)\.jsonl$/.test(file),
    eventCount: events.length, effectiveStrideMeters: distanceMeters / events.length, ...features
  };
}

function spearman(rows) {
  const ranks = values => values.map(value => 1 + values.filter(other => other < value).length
    + (values.filter(other => other === value).length - 1) / 2);
  const x = ranks(rows.map(row => row.sigmaEvents));
  const y = ranks(rows.map(row => row.absoluteErrorMeters));
  const xMean = mean(x), yMean = mean(y);
  const numerator = x.reduce((sum, value, index) => sum + (value - xMean) * (y[index] - yMean), 0);
  const denominator = Math.sqrt(x.reduce((sum, value) => sum + (value - xMean) ** 2, 0)
    * y.reduce((sum, value) => sum + (value - yMean) ** 2, 0));
  return denominator ? numerator / denominator : null;
}

function scoreFold(train, test) {
  const stride = weightedMedianStride(train);
  const trainRows = train.map(row => ({ ...row, absoluteErrorMeters: Math.abs(row.eventCount * stride - distanceMeters) }));
  // The multiplier is fit only from completed paths.  The 80th percentile is
  // a declared target coverage, not a parameter chosen from the held-out path.
  const multiplier = quantile(trainRows.map(row => row.absoluteErrorMeters / Math.max(0.05, stride * row.sigmaEvents)), 0.8);
  const estimatedMeters = test.eventCount * stride;
  const absoluteErrorMeters = Math.abs(estimatedMeters - distanceMeters);
  const radiusMeters = multiplier * stride * test.sigmaEvents;
  return { strideMeters: stride, multiplier, estimatedMeters, absoluteErrorMeters, radiusMeters,
    covered: absoluteErrorMeters <= radiusMeters };
}

function main() {
  const external = process.argv[2];
  if (!external) throw new Error('Usage: node indoor/tools/evaluate_4f_detection_confidence.cjs <external-jsonl-directory>');
  const sessions = sourceFiles(external).filter(fs.existsSync).map(load).filter(Boolean);
  if (sessions.length !== 15) throw new Error(`Expected 15 iPhone 4F corridor sessions, got ${sessions.length}`);

  const leaveOneOut = sessions.map(test => {
    const trial = scoreFold(sessions.filter(row => row !== test), test);
    return { file: test.file, route: test.route, fresh: test.fresh, eventCount: test.eventCount,
      effectiveStrideMeters: test.effectiveStrideMeters, sigmaEvents: test.sigmaEvents,
      meanConfidence: test.meanConfidence, nearThresholdFraction: test.nearThresholdFraction,
      irregularIntervalFraction: test.irregularIntervalFraction, longGapFraction: test.longGapFraction,
      medianGyroNorm: test.medianGyroNorm, ...trial };
  });
  const chronologicalTrain = sessions.filter(row => !row.fresh);
  const chronologicalTest = sessions.filter(row => row.fresh);
  const chronological = chronologicalTest.map(test => ({ file: test.file, eventCount: test.eventCount,
    sigmaEvents: test.sigmaEvents, meanConfidence: test.meanConfidence,
    nearThresholdFraction: test.nearThresholdFraction, irregularIntervalFraction: test.irregularIntervalFraction,
    longGapFraction: test.longGapFraction, ...scoreFold(chronologicalTrain, test) }));
  const descriptive = leaveOneOut.map(row => ({ ...row }));
  const report = {
    purpose: 'Analysis-only detector-confidence replay. It neither changes event counts nor stride; it tests whether event-quality evidence can calibrate a position/particle uncertainty radius.',
    distanceMeters,
    currentRuntimeFixedMeters: currentFixedMeters,
    method: {
      fixedPointEstimate: 'Training walks only: step-count weighted median of surveyed distance / detected events.',
      confidence: 'Accepted event peak margin above 1.0m/s² plus online interval regularity. Large gaps add missing-step risk. Gyro is recorded only as a diagnostic and is not scored.',
      uncertainty: 'Per-event Bernoulli-like variance plus missing-step risk is summed. A multiplier is fitted on completed training paths to target 80% endpoint coverage.',
      importantLimit: 'Endpoint labels cannot identify which individual event was missed or duplicated. A positive result means only that uncertainty is calibrated, not that step classification is correct.'
    },
    leaveOneOut: {
      targetCoverage: 0.8,
      fixedPointMAEMeters: mean(leaveOneOut.map(row => row.absoluteErrorMeters)),
      coverage: mean(leaveOneOut.map(row => Number(row.covered))),
      meanRadiusMeters: mean(leaveOneOut.map(row => row.radiusMeters)),
      riskErrorSpearmanDescriptive: spearman(descriptive),
      trials: leaveOneOut
    },
    chronological11ToNew4: {
      trainingFiles: chronologicalTrain.map(row => row.file), testFiles: chronologicalTest.map(row => row.file),
      targetCoverage: 0.8,
      fixedPointMAEMeters: mean(chronological.map(row => row.absoluteErrorMeters)),
      coverage: mean(chronological.map(row => Number(row.covered))),
      meanRadiusMeters: mean(chronological.map(row => row.radiusMeters)),
      trials: chronological
    },
    decisionRule: 'Do not modify production until a separate, step-labelled dataset validates event confidence and a new local walking set confirms endpoint coverage without an impractically wide radius.'
  };
  const output = path.join(root, 'indoor/data/analysis/detailed-20260914/4f-detector-confidence-replay.json');
  fs.writeFileSync(output, JSON.stringify(report, null, 2) + '\n');
  console.log(JSON.stringify({ leaveOneOut: report.leaveOneOut, chronological11ToNew4: report.chronological11ToNew4 }, null, 2));
}

main();
