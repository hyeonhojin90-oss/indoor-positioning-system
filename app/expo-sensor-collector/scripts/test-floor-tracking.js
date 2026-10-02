const assert = require("node:assert/strict");
const { createFloorTracker, updateFloorTracker } = require("../floorTracking");

let tracker = createFloorTracker(1, 4);
for (const pressure of [1000.01, 1000.00, 999.99, 1000.00, 1000.01]) {
  tracker = updateFloorTracker(tracker, pressure);
}
assert.equal(tracker.baselinePressure, 1000.00);
assert.equal(tracker.confirmedFloor, 1);

for (const pressure of [999.56, 999.56, 999.56, 999.56, 999.56]) {
  tracker = updateFloorTracker(tracker, pressure);
}
assert.equal(tracker.confirmedFloor, 2);

tracker = updateFloorTracker(tracker, 997.00);
assert.equal(tracker.confirmedFloor, 2, "한 번의 이상치는 층을 바꾸면 안 된다");

for (const pressure of [999.12, 999.12, 999.12, 999.12, 999.12]) {
  tracker = updateFloorTracker(tracker, pressure);
}
assert.equal(tracker.confirmedFloor, 3);

for (const pressure of [998.68, 998.68, 998.68, 998.68, 998.68]) {
  tracker = updateFloorTracker(tracker, pressure);
}
assert.equal(tracker.confirmedFloor, 4);
console.log("floor tracking tests passed");
