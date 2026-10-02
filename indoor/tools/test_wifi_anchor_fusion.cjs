const assert = require('node:assert/strict');
const Fusion = require('../web/src/positioning/fusion-engine');
const Zones = require('../web/src/positioning/zone-classifier');
const navigation = require('../web/data/navigation/areas-v1.json');
const wifiReferences = require('../web/data/positioning/wifi-references.json').references;

const reference = wifiReferences.find(row =>
  row.floor === 4 && row.zone === 'core_junction' && row.anchor?.verified === true,
);
assert.ok(reference, 'verified 4F core Wi-Fi reference is required');

const timestamp = 10_000;
const observation = Zones.classify({
  id: `wifi-${timestamp}`,
  timestamp,
  platform: reference.platform,
  device: reference.device,
  quality: 1,
  wifi: { supported: true, fresh: true, timestamp, rssi: reference.wifi },
}, wifiReferences, timestamp);

assert.equal(observation.reason, 'relative_zone_scores');
assert.equal(observation.candidates[0].anchor.id, reference.anchor.id);

const startX = reference.anchor.x + 8;
const state = Fusion.create(navigation, { floor: 4, x: startX, y: reference.anchor.y, count: 160, seed: 173 });
const before = Fusion.snapshot(state);
assert.equal(Fusion.observeWifi(state, observation, timestamp), true);
const after = Fusion.snapshot(state);
assert.equal(after.reason, 'tracking_wifi_anchor_soft');
assert.equal(after.zoneHypotheses[0].anchorId, reference.anchor.id);
assert.ok(Math.abs(after.x - reference.anchor.x) < Math.abs(before.x - reference.anchor.x));
assert.equal(Fusion.observeWifi(state, observation, timestamp), false, 'same scan must not be applied twice');

const farState = Fusion.create(navigation, { floor: 4, x: reference.anchor.x + 25, y: 0, count: 160, seed: 173 });
assert.equal(Fusion.observeWifi(farState, observation, timestamp), false);
assert.equal(farState.observationReason, 'wifi_outside_pdr_gate');
const strongObservation = {...observation, candidates:[{...observation.candidates[0],weight:1}]};
assert.equal(Fusion.recover(farState, strongObservation, timestamp), false, 'a distant AP must not start hard recovery');
assert.equal(farState.observationReason, 'wifi_recovery_outside_pdr_gate');
assert.equal(farState.recoveryCandidate, null);

// A core scan also has a lower-ranked right-stair reference. Proximity to that
// weaker candidate cannot make the distant, qualified core fingerprint valid.
const wrongAnchorState = Fusion.create(navigation, { floor: 4, x: 0, y: 0, count: 160, seed: 173 });
const preserved = wrongAnchorState.particles.map(p=>({...p}));
assert.ok(observation.candidates.some(c=>c.floor===4&&c.zone==='stairs_right'&&c.wifiScore<=4));
assert.equal(Fusion.observeWifi(wrongAnchorState, observation, timestamp), false);
assert.equal(wrongAnchorState.observationReason, 'wifi_outside_pdr_gate');
assert.deepEqual(wrongAnchorState.particles.map(p=>[p.x,p.y]),preserved.map(p=>[p.x,p.y]));
assert.ok(wrongAnchorState.particles.every((p,i)=>Math.abs(p.weight-preserved[i].weight)<1e-12));

console.log('PASS fresh AP fingerprint is a gated soft anchor with logged candidates');
