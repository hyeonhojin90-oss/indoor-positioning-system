const { chromium } = require('playwright');
const assert = require('node:assert/strict');

(async () => {
  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  try {
    const page = await browser.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    page.on('response', response => {
      if (response.status() >= 400) errors.push(`${response.status()} ${response.url()}`);
    });
    await page.addInitScript(() => {
      window.routeRecords = [];
      window.routeReady = false;
      window.RouteFusionHost = {
        ready: () => { window.routeReady = true; },
        failed: message => { throw new Error(message); },
        publish: json => window.routeRecords.push(JSON.parse(json)),
      };
    });
    await page.goto('http://127.0.0.1:4175/fusion-route-runtime.html');
    await page.waitForFunction(() => window.routeReady === true);
    const result = await page.evaluate(async () => {
      const started = window.RouteFusion.start(4, 70.804, 'samsung SM-S938N', 'F4_GUIDANCE_FUSION_V1');
      const now = Date.now();
      window.RouteFusion.receive({ sensor: 'heading_degrees', time: now, values: [355], accuracy: 3 });
      const refs = await (await fetch('data/positioning/wifi-references.json')).json();
      const ref = refs.references.find(row => row.floor === 4 && row.zone === 'core_junction' && row.anchor?.verified);
      const wifiUsed = window.RouteFusion.wifi(now + 1, { fresh: true, timestamp: now + 1, rssi: ref.wifi });
      const snapshot = window.RouteFusion.snapshot();
      window.RouteFusion.stop();
      const extensionStarted = window.RouteFusion.start(2, 9.435, 'samsung SM-S938N', '2F_EXTENSION_V3');
      const extensionSnapshot = window.RouteFusion.snapshot();
      const rightReverseStarted = window.RouteFusion.start(4, 70.804, 'samsung SM-S938N', '4F_CORE_TO_RIGHT_STAIRS_REVERSE');
      const rightReverseSnapshot = window.RouteFusion.snapshot();
      const leftReverseStarted = window.RouteFusion.start(4, 70.804, 'samsung SM-S938N', '4F_CORE_TO_LEFT_STAIRS_REVERSE');
      const leftReverseSnapshot = window.RouteFusion.snapshot();
      const lapCaptured = window.RouteFusion.captureLap(1, now + 2);
      return { started, wifiUsed, snapshot, extensionStarted, extensionSnapshot,
        rightReverseStarted, rightReverseSnapshot, leftReverseStarted, leftReverseSnapshot, lapCaptured,
        records: window.routeRecords };
    });
    assert.equal(result.started, true);
    assert.equal(result.wifiUsed, true);
    assert.equal(result.snapshot.reason, 'tracking_wifi_anchor_soft');
    assert.ok(result.snapshot.zoneHypotheses[0].anchorId);
    assert.ok(result.records.some(row => row.kind === 'derived_fusion' && row.comparison_variant === 'mode4_mag_v2_ble_ap'));
    assert.equal(result.extensionStarted, true);
    assert.equal(result.extensionSnapshot.zone, 'entry');
    assert.ok(Math.abs(result.extensionSnapshot.x - 17.6625) < 0.2);
    assert.ok(Math.abs(result.extensionSnapshot.y - 1.18) < 0.2);
    assert.equal(result.rightReverseStarted, true);
    assert.equal(result.leftReverseStarted, true);
    assert.ok(Math.abs(result.rightReverseSnapshot.x - 3.363100346) < 0.3);
    assert.ok(Math.abs(result.leftReverseSnapshot.x - 135.407) < 0.3);
    assert.equal(result.lapCaptured, true);
    assert.ok(result.records.some(row => row.kind === 'lap_fusion_snapshot' && row.lap_index === 1));
    assert.deepEqual(errors, []);
    console.log('PASS Android route mode-4 runtime and AP fingerprint bridge');
  } finally {
    await browser.close();
  }
})().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
