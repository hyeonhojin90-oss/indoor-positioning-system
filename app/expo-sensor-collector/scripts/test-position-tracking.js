const assert = require("node:assert/strict");
const Navigation = require("../../../indoor/web/src/positioning/navigation");
const navigationData = require("../../../indoor/web/data/navigation/areas-v1.json");
const {
  PROVISIONAL_STRIDE_MAP_UNITS,
  createPositionTracker,
  updatePositionAcceleration,
  updatePositionHeading
} = require("../positionTracking");

let tracker = createPositionTracker({ floor: 3, x: 70.804, initialDirectionSign: -1 });
tracker = updatePositionHeading(tracker, 0);
assert.equal(tracker.currentDirectionSign, -1);
tracker = updatePositionHeading(tracker, Math.PI);
assert.equal(tracker.currentDirectionSign, 1, "180도 회전하면 진행 부호가 바뀌어야 한다");

tracker = updatePositionHeading(tracker, 0);
const before = tracker.x;
for (const [offset, magnitude] of [[0, 9.8], [50, 11.5], [100, 9.4]]) {
  const result = updatePositionAcceleration(tracker, 1000 + offset, [0, 0, magnitude]);
  tracker = result.state;
}
assert.equal(tracker.detectedSteps, 1);
const map = Navigation.compile(navigationData, 3);
const referenceDistance = Navigation.metricDistance(map, 70.804)
  - Navigation.metricDistance(map, map.distanceMetric.mapBreaks[0]);
const movedMeters = Navigation.metricDistance(map, before)
  - Navigation.metricDistance(map, tracker.x);
assert.ok(Math.abs(movedMeters - referenceDistance / 81) < 1e-9,
  "one detected step advances one 81st of the surveyed core-to-stair distance");
console.log("position tracking tests passed");
