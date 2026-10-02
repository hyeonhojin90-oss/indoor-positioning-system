const assert = require('node:assert/strict');
const Fusion = require('../web/src/positioning/fusion-engine');
const data = require('../web/data/navigation/areas-v1.json');

function feedStep(state, heading, time) {
  Fusion.heading(state, heading, time, 3);
  Fusion.step(state, time, 12, 1);
  return Fusion.snapshot(state);
}

const state = Fusion.create(data, {
  floor: 4,
  x: 60,
  y: 0,
  count: 160,
  initialDirectionSign: -1,
  seed: 173,
});

const forward = feedStep(state, 355, 1_000);
const firstCandidate = feedStep(state, 175, 2_000);
const secondCandidate = feedStep(state, 175, 3_000);
assert.equal(firstCandidate.reason, 'direction_change_pending');
assert.equal(firstCandidate.directionCandidateSteps, 1);
assert.equal(secondCandidate.reason, 'direction_change_pending');
assert.equal(secondCandidate.directionCandidateSteps, 2);
assert.ok(Math.abs(firstCandidate.x - forward.x) < 1e-9);
assert.ok(Math.abs(secondCandidate.x - forward.x) < 1e-9);

const confirmed = feedStep(state, 175, 4_000);
assert.equal(confirmed.directionCandidateSteps, 0);
assert.equal(confirmed.corridorDirection, 1);
assert.ok(confirmed.x > forward.x + state.baseStride * 2.5);

const cancelledState = Fusion.create(data, {
  floor: 4,
  x: 60,
  y: 0,
  count: 160,
  initialDirectionSign: -1,
  seed: 173,
});
const cancelledForward = feedStep(cancelledState, 355, 1_000);
feedStep(cancelledState, 175, 2_000);
feedStep(cancelledState, 175, 3_000);
const cancelled = feedStep(cancelledState, 355, 4_000);
assert.equal(cancelled.corridorDirection, -1);
assert.equal(cancelled.directionCandidateSteps, 0);
assert.ok(cancelled.x < cancelledForward.x - cancelledState.baseStride * 2.5);

console.log('PASS three-step turn buffering and cancelled-candidate replay');
