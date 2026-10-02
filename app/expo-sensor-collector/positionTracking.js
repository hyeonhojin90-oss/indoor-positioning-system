const MAP_MIN_X = 0;
const MAP_MAX_X = 135.407;
const PROVISIONAL_STRIDE_MAP_UNITS = 70.804 / 81;
const Navigation = require('../../indoor/web/src/positioning/navigation');
const navigationData = require('../../indoor/web/data/navigation/areas-v1.json');
const distanceMaps = new Map();
function advanceMeasured(floor,x,delta) {
  if(!distanceMaps.has(floor))distanceMaps.set(floor,Navigation.compile(navigationData,floor));
  return Navigation.advanceDistance(distanceMaps.get(floor),x,delta);
}

function clamp(value, minimum, maximum) {
  return Math.max(minimum, Math.min(maximum, value));
}

function angleDelta(current, reference) {
  let delta = current - reference;
  while (delta > Math.PI) delta -= Math.PI * 2;
  while (delta < -Math.PI) delta += Math.PI * 2;
  return delta;
}

function createStepDetector() {
  return {
    gravity: null,
    previousDynamic: 0,
    rising: false,
    peakValue: 0,
    peakTime: null,
    lastSampleTime: null,
    lastStepTime: null
  };
}

function updateStepDetector(previous, timestamp, values) {
  const state = { ...previous };
  const magnitude = Math.hypot(values[0], values[1], values[2]);
  if (state.gravity === null) {
    state.gravity = magnitude;
    state.lastSampleTime = timestamp;
    return { state, detected: false, peak: 0 };
  }

  const dt = Math.max(0.001, Math.min(0.1, (timestamp - state.lastSampleTime) / 1000));
  state.lastSampleTime = timestamp;
  const alpha = Math.min(1, dt / 0.8);
  state.gravity += alpha * (magnitude - state.gravity);
  const dynamic = magnitude - state.gravity;
  let detected = false;
  let detectedPeak = 0;

  if (dynamic > state.previousDynamic) {
    if (!state.rising) {
      state.peakValue = dynamic;
      state.peakTime = timestamp;
    }
    state.rising = true;
    if (dynamic > state.peakValue) {
      state.peakValue = dynamic;
      state.peakTime = timestamp;
    }
  } else if (state.rising) {
    const separated = state.lastStepTime === null || state.peakTime - state.lastStepTime >= 280;
    if (state.peakValue >= 1.0 && separated) {
      detected = true;
      detectedPeak = state.peakValue;
      state.lastStepTime = state.peakTime;
    }
    state.rising = false;
    state.peakValue = dynamic;
    state.peakTime = timestamp;
  }
  state.previousDynamic = dynamic;
  return { state, detected, peak: detectedPeak };
}

function createPositionTracker({ floor, x, initialDirectionSign }) {
  return {
    floor,
    x,
    initialDirectionSign,
    currentDirectionSign: initialDirectionSign,
    initialAlpha: null,
    currentAlpha: null,
    detectedSteps: 0,
    detector: createStepDetector(),
    changed: false
  };
}

function updatePositionHeading(previous, alpha) {
  const state = { ...previous, currentAlpha: alpha, changed: false };
  if (state.initialAlpha === null) state.initialAlpha = alpha;
  const delta = angleDelta(alpha, state.initialAlpha);
  state.currentDirectionSign = Math.cos(delta) >= 0 ? state.initialDirectionSign : -state.initialDirectionSign;
  return state;
}

function updatePositionAcceleration(previous, timestamp, values) {
  const detection = updateStepDetector(previous.detector, timestamp, values);
  const state = { ...previous, detector: detection.state, changed: false };
  if (detection.detected) {
    state.detectedSteps += 1;
    state.x = clamp(advanceMeasured(state.floor,state.x,state.currentDirectionSign * PROVISIONAL_STRIDE_MAP_UNITS), MAP_MIN_X, MAP_MAX_X);
    state.changed = true;
  }
  return { state, detected: detection.detected, peak: detection.peak };
}

module.exports = {
  MAP_MAX_X,
  MAP_MIN_X,
  PROVISIONAL_STRIDE_MAP_UNITS,
  angleDelta,
  createPositionTracker,
  updatePositionAcceleration,
  updatePositionHeading
};
