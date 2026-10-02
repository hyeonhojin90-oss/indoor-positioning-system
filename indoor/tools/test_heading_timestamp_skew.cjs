const assert = require('node:assert/strict');
const Fusion = require('../web/src/positioning/fusion-engine');
const navigation = require('../web/data/navigation/areas-v1.json');

function oneStep(headingTime) {
  const state = Fusion.create(navigation, { floor: 4, x: 95, y: 0 });
  Fusion.heading(state, 175, headingTime, 3);
  Fusion.step(state, 1000, 1.2, 1);
  return { reason: state.reason, x: Fusion.snapshot(state).x };
}

const near = oneStep(1120);
assert.notEqual(near.reason, 'heading_unavailable');
assert.ok(near.x > 95.3, `short callback skew should preserve the step: ${near.x}`);

const far = oneStep(1300);
assert.equal(far.reason, 'heading_unavailable');
assert.ok(Math.abs(far.x - 95) < 0.3);

const stale = oneStep(-4000);
assert.equal(stale.reason, 'heading_unavailable');

console.log('PASS bounded heading timestamp skew');
