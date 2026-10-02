const assert = require("assert");
const {
  circularDistance,
  classifyCorridorDirection,
  rankStationaryCandidates
} = require("../initialPositioning");

assert.strictEqual(circularDistance(350, 10), 20);
assert.strictEqual(classifyCorridorDirection(350).sign, -1);
assert.strictEqual(classifyCorridorDirection(175).sign, 1);
assert.strictEqual(classifyCorridorDirection(270).label, "코어→메인복도 후보");

const result = rankStationaryCandidates({
  platform: "ios",
  magneticValues: [50.8, 51.2, 51.1],
  pressureValues: [998.9],
  references: [
    { platform: "ios", node_id: "A", observation_count: 3, magnetic_median_ut: 51, magnetic_between_observation_std_ut: 0.5, magnetic_within_window_std_ut: 0.5, pressure_median_hpa: 998.9 },
    { platform: "ios", node_id: "B", observation_count: 3, magnetic_median_ut: 40, magnetic_between_observation_std_ut: 1, magnetic_within_window_std_ut: 1, pressure_median_hpa: 998.9 },
    { platform: "android", floor: 2, node_id: "C", observation_count: 3, magnetic_median_ut: 52, magnetic_between_observation_std_ut: 1, magnetic_within_window_std_ut: 1, pressure_median_hpa: 998.9 }
  ],
  transferModels: [{ source_platform: "android", target_platform: "ios", slope: 1, intercept: 0, rmse_ut: 1 }]
});
assert.strictEqual(result.candidates[0].node_id, "A");
assert.strictEqual(result.candidates.length, 3);
assert.strictEqual(result.candidates.some((candidate) => candidate.transferred_from === "android"), true);

console.log("initial positioning tests passed");
