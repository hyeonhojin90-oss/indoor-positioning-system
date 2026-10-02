const PRESSURE_PER_FLOOR_HPA = 0.44;
const BASELINE_SAMPLE_COUNT = 5;
const CONFIRMATION_SAMPLE_COUNT = 3;

function clampFloor(floor) {
  return Math.max(1, Math.min(10, floor));
}

function median(values) {
  const ordered = [...values].sort((a, b) => a - b);
  const middle = Math.floor(ordered.length / 2);
  return ordered.length % 2 ? ordered[middle] : (ordered[middle - 1] + ordered[middle]) / 2;
}

function createFloorTracker(startFloor, destinationFloor) {
  return {
    status: "calibrating",
    startFloor,
    destinationFloor,
    baselineSamples: [],
    pressureWindow: [],
    baselinePressure: null,
    smoothedPressure: null,
    pressureDelta: 0,
    rawFloor: startFloor,
    candidateFloor: startFloor,
    confirmedFloor: startFloor,
    candidateStreak: 0,
    baselineProgress: 0,
    changed: false
  };
}

function updateFloorTracker(previous, pressure) {
  const state = { ...previous, changed: false };
  if (state.baselinePressure === null) {
    state.baselineSamples = [...state.baselineSamples, pressure].slice(-BASELINE_SAMPLE_COUNT);
    state.baselineProgress = state.baselineSamples.length;
    state.smoothedPressure = median(state.baselineSamples);
    if (state.baselineSamples.length >= BASELINE_SAMPLE_COUNT) {
      state.baselinePressure = median(state.baselineSamples);
      state.pressureWindow = [pressure];
      state.status = "tracking";
    }
    return state;
  }

  state.pressureWindow = [...state.pressureWindow, pressure].slice(-3);
  state.smoothedPressure = median(state.pressureWindow);
  state.pressureDelta = state.baselinePressure - state.smoothedPressure;
  state.rawFloor = state.startFloor + state.pressureDelta / PRESSURE_PER_FLOOR_HPA;
  const candidate = clampFloor(Math.round(state.rawFloor));

  if (candidate === state.candidateFloor) {
    state.candidateStreak += 1;
  } else {
    state.candidateFloor = candidate;
    state.candidateStreak = 1;
  }

  if (state.candidateStreak >= CONFIRMATION_SAMPLE_COUNT && candidate !== state.confirmedFloor) {
    state.confirmedFloor = candidate;
    state.changed = true;
  }
  return state;
}

module.exports = {
  BASELINE_SAMPLE_COUNT,
  CONFIRMATION_SAMPLE_COUNT,
  PRESSURE_PER_FLOOR_HPA,
  createFloorTracker,
  updateFloorTracker
};
