const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { createReport, inspectSession, markdown } = require('./analyze_radio_anchors.cjs');

const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'radio-anchor-test-'));
function session(name, zone, apBase, bleBase, failure = null) {
  const rows = [
    { kind: 'session_start', schema_version: 7, platform: 'android', device: 'test-device', wall_time_ms: 1000,
      label: { floor: '4', zone_id: zone, location: zone } },
    { kind: 'ble_scan_status', wall_time_ms: 1005, active: !failure, status: failure || 'BLE 연속 스캔 중', transmitter_count: 2, observation_count: 0 },
    { kind: 'wifi_scan', wall_time_ms: 2000, fresh_results: true, access_points: [
      { bssid: `${apBase}:01`, rssi_dbm: -42 }, { bssid: `${apBase}:02`, rssi_dbm: -55 },
    ] },
    { kind: 'ble_observation', wall_time_ms: 2100, anonymous_id: `${bleBase}a`, rssi_dbm: -48 },
    { kind: 'ble_observation', wall_time_ms: 3200, anonymous_id: `${bleBase}b`, rssi_dbm: -61 },
    { kind: 'session_end', wall_time_ms: 31000 },
  ];
  const file = path.join(temp, `${name}.jsonl`);
  fs.writeFileSync(file, rows.map(row => JSON.stringify(row)).join('\n') + '\n');
  return file;
}
try {
  const files = [
    session('core-1', 'core_junction', 'aa:aa:aa', 'core'), session('core-2', 'core_junction', 'aa:aa:aa', 'core'), session('core-3', 'core_junction', 'aa:aa:aa', 'core'),
    session('stairs-1', 'stairs_right', 'bb:bb:bb', 'stairs'), session('stairs-2', 'stairs_right', 'bb:bb:bb', 'stairs'), session('stairs-3', 'stairs_right', 'bb:bb:bb', 'stairs'),
    session('failed', 'main_right', 'cc:cc:cc', 'failed', 'BLE 수집 권한이 필요합니다.'),
  ];
  const legacy = path.join(temp, 'legacy.jsonl');
  fs.writeFileSync(legacy, JSON.stringify({ kind: 'session_start', schema_version: 6 }) + '\n');
  files.push(legacy);
  const literalDelimiter = path.join(temp, 'literal-delimiter.jsonl');
  const literalRows = [
    { kind: 'session_start', schema_version: 7, platform: 'android', device: 'test-device', wall_time_ms: 1000, label: { floor: '2', zone_id: 'extension_entry', location: 'test' } },
    { kind: 'wifi_scan', wall_time_ms: 2000, fresh_results: true, access_points: [{ bssid: 'dd:dd:dd:01', rssi_dbm: -48 }, { bssid: 'dd:dd:dd:02', rssi_dbm: -61 }] },
    { kind: 'session_end', wall_time_ms: 20000 },
  ];
  fs.writeFileSync(literalDelimiter, literalRows.map(row => JSON.stringify(row)).join('\\n') + '\\n');
  const repaired = inspectSession(literalDelimiter);
  assert.equal(repaired.accepted, true);
  assert.equal(repaired.literal_delimiter_repaired, true);
  const report = createReport(files);
  assert.equal(report.input.accepted_schema7_zone_sessions, 7);
  assert.equal(report.sessions.find(item => item.file === 'failed.jsonl').ble_failure, 'BLE 수집 권한이 필요합니다.');
  assert.equal(report.leave_one_session_out.wifi.top1_accuracy, 1);
  assert.equal(report.leave_one_session_out.ble.top1_accuracy, 1);
  assert.ok(report.zones.wifi.find(item => item.zone === 'core_junction').recommended_repeat_complete);
  const rendered = markdown(report);
  assert.ok(!rendered.includes('aa:aa:aa'));
  assert.ok(rendered.includes('제외: schema 7 이상 AP·BLE 기준점 파일이 아님'));
  assert.ok(!rendered.includes('undefined'));
  console.log('PASS radio anchor schema 7 parser, failure state, privacy, and leave-one-session-out scoring');
} finally {
  fs.rmSync(temp, { recursive: true, force: true });
}
