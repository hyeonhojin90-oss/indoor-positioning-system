#!/usr/bin/env node
/*
 * Schema 7+ Android AP+BLE anchor survey analyzer.
 *
 * This is a readiness check, not a positioning engine: it never writes a
 * fingerprint into Fusion or estimates a user's current position.
 */
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const os = require('node:os');

const MIN_SHARED_SIGNALS = 2;
const RECOMMENDED_SESSIONS_PER_ZONE = 3;

function median(values) {
  const sorted = values.filter(Number.isFinite).sort((a, b) => a - b);
  if (!sorted.length) return null;
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
}

function mean(values) {
  const usable = values.filter(Number.isFinite);
  return usable.length ? usable.reduce((sum, value) => sum + value, 0) / usable.length : null;
}

function standardDeviation(values) {
  const average = mean(values);
  return average === null ? null : Math.sqrt(mean(values.map(value => (value - average) ** 2)));
}

function alias(kind, identifier) {
  return `${kind}_${crypto.createHash('sha256').update(String(identifier)).digest('hex').slice(0, 10)}`;
}

function walkJsonl(target) {
  if (!fs.existsSync(target)) return [];
  const stat = fs.statSync(target);
  if (stat.isFile()) return target.toLowerCase().endsWith('.jsonl') ? [target] : [];
  return fs.readdirSync(target, { withFileTypes: true }).flatMap(entry =>
    walkJsonl(path.join(target, entry.name))
  );
}

function parseJsonl(file) {
  const rows = [];
  const errors = [];
  const source = fs.readFileSync(file, 'utf8').replace(/^\uFEFF/, '');
  // Some Android exports from the recorder used the two printable characters
  // "\\n" between records, rather than an actual line break.  Repair only a
  // delimiter found between complete top-level objects; never rewrite the raw
  // survey file itself.
  const normalized = source.replace(/}(?:\\r)?\\n(?=\{)/g, '}\n');
  const literalDelimiterRepaired = normalized !== source;
  normalized.split(/\r?\n/).forEach((line, index) => {
    if (!line.trim()) return;
    try { rows.push(JSON.parse(line)); } catch { errors.push(index + 1); }
  });
  return { rows, errors, literal_delimiter_repaired: literalDelimiterRepaired };
}

function signalMap(rows, medium) {
  const values = new Map();
  if (medium === 'wifi') {
    rows.filter(row => row.kind === 'wifi_scan' && row.fresh_results === true).forEach(row => {
      (row.access_points || []).forEach(ap => {
        if (!ap.bssid || !Number.isFinite(ap.rssi_dbm)) return;
        const id = alias('ap', ap.bssid);
        if (!values.has(id)) values.set(id, []);
        values.get(id).push(ap.rssi_dbm);
      });
    });
  } else {
    rows.filter(row => row.kind === 'ble_observation').forEach(row => {
      if (!row.anonymous_id || !Number.isFinite(row.rssi_dbm)) return;
      const id = alias('ble', row.anonymous_id);
      if (!values.has(id)) values.set(id, []);
      values.get(id).push(row.rssi_dbm);
    });
  }
  return new Map([...values].map(([id, readings]) => [id, median(readings)]));
}

function inspectSession(file) {
  const { rows, errors, literal_delimiter_repaired } = parseJsonl(file);
  const start = rows.find(row => row.kind === 'session_start');
  if (!start || !Number.isFinite(Number(start.schema_version)) || Number(start.schema_version) < 7) {
    return { file: path.basename(file), accepted: false, reason: 'schema 7 이상 AP·BLE 기준점 파일이 아님', parse_errors: errors, literal_delimiter_repaired };
  }
  const label = start.label || {};
  const end = rows.findLast(row => row.kind === 'session_end');
  const statuses = rows.filter(row => row.kind === 'ble_scan_status');
  const failedStatus = statuses.find(row => /권한|꺼짐|지원하지|찾지 못|열지 못|실패|시작하지 못/.test(String(row.status)));
  const activeSeen = statuses.some(row => row.active === true);
  const freshWifi = rows.filter(row => row.kind === 'wifi_scan' && row.fresh_results === true);
  const ble = rows.filter(row => row.kind === 'ble_observation');
  const startTime = Number(start.wall_time_ms);
  const endTime = Number(end?.wall_time_ms);
  return {
    file: path.basename(file),
    accepted: Boolean(label.zone_id),
    reason: label.zone_id ? null : 'zone_id가 없어 구역 지문으로 비교할 수 없음',
    parse_errors: errors,
    literal_delimiter_repaired,
    platform: start.platform || 'unknown',
    device: start.device || 'unknown',
    floor: String(label.floor || 'unknown'),
    zone: label.zone_id || null,
    detail: label.location || null,
    duration_s: Number.isFinite(startTime) && Number.isFinite(endTime) ? Math.max(0, (endTime - startTime) / 1000) : null,
    completed: Boolean(end),
    wifi_scans: rows.filter(row => row.kind === 'wifi_scan').length,
    fresh_wifi_scans: freshWifi.length,
    wifi_unique_aps: signalMap(rows, 'wifi').size,
    ble_status_count: statuses.length,
    ble_active_seen: activeSeen,
    ble_failure: failedStatus?.status || null,
    ble_observations: ble.length,
    ble_unique_transmitters: signalMap(rows, 'ble').size,
    signals: { wifi: signalMap(rows, 'wifi'), ble: signalMap(rows, 'ble') },
  };
}

function centroid(sessions, medium) {
  const readings = new Map();
  sessions.forEach(session => session.signals[medium].forEach((value, id) => {
    if (!readings.has(id)) readings.set(id, []);
    readings.get(id).push(value);
  }));
  return new Map([...readings].map(([id, values]) => [id, median(values)]));
}

function predict(session, candidates, medium) {
  const scores = candidates.map(candidate => {
    const shared = [...session.signals[medium]].filter(([id]) => candidate.values.has(id));
    if (shared.length < MIN_SHARED_SIGNALS) return null;
    const mae = mean(shared.map(([id, value]) => Math.abs(value - candidate.values.get(id))));
    return { zone: candidate.zone, mae, shared: shared.length };
  }).filter(Boolean).sort((a, b) => a.mae - b.mae || b.shared - a.shared);
  return scores[0] || null;
}

function leaveOneSessionOut(sessions, medium) {
  const eligible = sessions.filter(session => session.accepted && session.signals[medium].size >= MIN_SHARED_SIGNALS);
  const evaluated = [];
  eligible.forEach(target => {
    const peers = eligible.filter(session => session !== target && session.platform === target.platform && session.floor === target.floor);
    const zones = [...new Set(peers.map(session => session.zone))];
    if (zones.length < 2 || !peers.some(session => session.zone === target.zone)) return;
    const candidates = zones.map(zone => ({ zone, values: centroid(peers.filter(session => session.zone === zone), medium) }));
    const result = predict(target, candidates, medium);
    if (result) evaluated.push({ correct: result.zone === target.zone, ...result });
  });
  return {
    evaluated_sessions: evaluated.length,
    top1_accuracy: evaluated.length ? Number((evaluated.filter(row => row.correct).length / evaluated.length).toFixed(3)) : null,
    median_rssi_mae_db: median(evaluated.map(row => row.mae)),
    median_shared_signals: median(evaluated.map(row => row.shared)),
    limitation: evaluated.length ? null : `같은 플랫폼·층에서 구역 2개 이상과 각 구역의 반복 수집이 필요합니다.`,
  };
}

function zoneSummary(sessions, medium) {
  const byZone = new Map();
  sessions.filter(session => session.accepted).forEach(session => {
    const key = `${session.platform}|${session.floor}|${session.zone}`;
    if (!byZone.has(key)) byZone.set(key, []);
    byZone.get(key).push(session);
  });
  return [...byZone.entries()].map(([key, group]) => {
    const [platform, floor, zone] = key.split('|');
    const allSignals = new Map();
    group.forEach(session => session.signals[medium].forEach((value, id) => {
      if (!allSignals.has(id)) allSignals.set(id, []);
      allSignals.get(id).push(value);
    }));
    const stable = [...allSignals.values()].filter(values => values.length / group.length >= 0.67);
    return {
      platform, floor, zone, sessions: group.length,
      unique_signals: allSignals.size,
      signals_seen_in_67_percent_sessions: stable.length,
      median_signal_rssi_sd_db: median(stable.map(standardDeviation)),
      recommended_repeat_complete: group.length >= RECOMMENDED_SESSIONS_PER_ZONE,
    };
  }).sort((a, b) => a.floor.localeCompare(b.floor) || a.zone.localeCompare(b.zone));
}

function createReport(files) {
  const sessions = files.map(inspectSession);
  const accepted = sessions.filter(session => session.accepted);
  const report = {
    generated_at: new Date().toISOString(),
    purpose: 'AP·BLE 신호 환경의 반복성·구역 분리력 사전검증. 위치 보정 또는 Fusion 적용 결과가 아님.',
    thresholds: { min_shared_signals_for_classification: MIN_SHARED_SIGNALS, recommended_sessions_per_zone: RECOMMENDED_SESSIONS_PER_ZONE },
    input: { files: files.length, accepted_schema7_zone_sessions: accepted.length, skipped: sessions.filter(session => !session.accepted).length },
    sessions: sessions.map(({ signals, ...session }) => session),
    zones: { wifi: zoneSummary(accepted, 'wifi'), ble: zoneSummary(accepted, 'ble') },
    leave_one_session_out: { wifi: leaveOneSessionOut(accepted, 'wifi'), ble: leaveOneSessionOut(accepted, 'ble') },
  };
  return report;
}

function markdown(report) {
  const lines = [
    '# AP·BLE 기준점 신호 분석', '', report.purpose, '',
    `입력 ${report.input.files}개 · 구역 비교 가능 schema 7+ 세션 ${report.input.accepted_schema7_zone_sessions}개 · 제외 ${report.input.skipped}개`, '',
    '## 세션 상태', '', '|파일|층·구역|완료|AP 신선 스캔/고유|BLE 관측/고유|상태|', '|---|---|---|---:|---:|---|',
  ];
  report.sessions.forEach(session => {
    if (!session.accepted) {
      lines.push(`|${session.file}|—|—|—|—|제외: ${session.reason}|`);
      return;
    }
    const status = [session.literal_delimiter_repaired ? '저장 구분자 보정' : null, session.ble_failure || (session.ble_active_seen ? 'BLE 스캔 활성' : 'BLE 상태 미기록')].filter(Boolean).join('; ');
    lines.push(`|${session.file}|${session.floor} ${session.zone}|${session.completed ? '완료' : '미완료'}|${session.fresh_wifi_scans}/${session.wifi_unique_aps}|${session.ble_observations}/${session.ble_unique_transmitters}|${status}|`);
  });
  for (const medium of ['wifi', 'ble']) {
    const title = medium === 'wifi' ? 'Wi-Fi AP' : 'BLE';
    const validation = report.leave_one_session_out[medium];
    lines.push('', `## ${title} 반복성·구역 구분`, '', '|플랫폼|층|구역|세션|고유 신호|67% 반복 신호|중앙 RSSI 표준편차 dB|반복 3회|', '|---|---:|---|---:|---:|---:|---:|---|');
    report.zones[medium].forEach(zone => lines.push(`|${zone.platform}|${zone.floor}|${zone.zone}|${zone.sessions}|${zone.unique_signals}|${zone.signals_seen_in_67_percent_sessions}|${zone.median_signal_rssi_sd_db?.toFixed(2) ?? '—'}|${zone.recommended_repeat_complete ? '완료' : '더 필요'}|`));
    lines.push('', `회차 제외 구역 판별: ${validation.evaluated_sessions}개 평가 · Top-1 ${validation.top1_accuracy ?? '—'} · 중앙 공통 신호 ${validation.median_shared_signals ?? '—'}개 · 중앙 RSSI MAE ${validation.median_rssi_mae_db?.toFixed(2) ?? '—'} dB.`);
    if (validation.limitation) lines.push(`판정 보류: ${validation.limitation}`);
  }
  lines.push('', '## 해석 규칙', '', '- 이 결과는 신호 지문을 Fusion에 넣기 전의 품질 검사다. `Top-1` 수치가 있어도 실제 보행 위치 정확도가 증명되지는 않는다.', '- BLE 또는 AP가 한 번만 잡히거나 RSSI 변동이 크면 위치 앵커로 사용하지 않는다.', '- 보고서에는 원시 Wi-Fi BSSID와 BLE 식별자를 쓰지 않고 재현 가능한 익명 별칭만 내부 계산에 사용한다.');
  return `${lines.join('\n')}\n`;
}

function parseArguments(argv) {
  const values = argv.slice(2);
  const outIndex = values.indexOf('--out');
  const output = outIndex >= 0 ? values[outIndex + 1] : path.join(process.cwd(), 'indoor', 'data', 'analysis', 'radio-anchor-latest');
  const inputs = values.filter((value, index) => value !== '--out' && index !== outIndex + 1);
  return { output, inputs: inputs.length ? inputs : [path.join(os.homedir(), 'Downloads', 'IndoorPositioning')] };
}

function main() {
  const { output, inputs } = parseArguments(process.argv);
  const files = [...new Set(inputs.flatMap(walkJsonl))].sort();
  const report = createReport(files);
  fs.mkdirSync(output, { recursive: true });
  fs.writeFileSync(path.join(output, 'radio-anchor-report.json'), JSON.stringify(report, null, 2) + '\n');
  fs.writeFileSync(path.join(output, 'REPORT.md'), markdown(report));
  console.log(`분석 완료: ${report.input.accepted_schema7_zone_sessions}개 schema 7+ 구역 세션`);
  console.log(`보고서: ${path.join(output, 'REPORT.md')}`);
}

if (require.main === module) main();
module.exports = { alias, inspectSession, createReport, markdown, parseArguments };
