const fs = require('fs');
const path = require('path');
const readline = require('readline');

function median(values) {
  if (!values.length) return null;
  const sorted = values.slice().sort((a, b) => a - b);
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
}

async function summarize(file) {
  const summary = {
    file: path.basename(file), bytes: fs.statSync(file).size, schema: null,
    started: false, ended: false, floor: null, routeId: null,
    labels: [], samples: 0, derived: 0, derivedKinds: {}, wifiScans: 0, freshWifi: 0,
    staleWifi: 0, bleObservations: 0, startSteps: null, endSteps: null,
    stepsSinceStart: null, durationMs: null, malformed: 0,
    sensorCounts: {}, pressureMedianHpa: null, magneticMedianUt: null,
  };
  const pressure = [];
  const magnetic = [];
  const input = fs.createReadStream(file, {encoding: 'utf8'});
  const lines = readline.createInterface({input, crlfDelay: Infinity});
  for await (const line of lines) {
    if (!line.trim()) continue;
    let row;
    try { row = JSON.parse(line); } catch { summary.malformed++; continue; }
    if (row.kind === 'session_start') {
      summary.started = true;
      summary.schema = row.schema_version ?? null;
      summary.startSteps = row.start_step_counter ?? null;
      summary.floor = row.label?.floor ?? null;
      summary.routeId = row.label?.route_id ?? null;
      if (row.label) summary.labels.push({kind: row.kind, elapsedMs: 0, ...row.label});
    } else if (row.kind === 'label') {
      if (row.label) summary.labels.push({kind: row.kind, elapsedMs: row.session_elapsed_ms ?? null, totalSteps: row.total_steps ?? null, ...row.label});
    } else if (row.kind === 'sample') {
      summary.samples++;
      const sensor = String(row.sensor || 'unknown');
      summary.sensorCounts[sensor] = (summary.sensorCounts[sensor] || 0) + 1;
      const values = Array.isArray(row.values) ? row.values.map(Number) : [];
      if (sensor === 'pressure_hpa' && Number.isFinite(values[0])) pressure.push(values[0]);
      if (sensor === 'magnetic_field_ut' && values.length >= 3 && values.slice(0, 3).every(Number.isFinite)) {
        magnetic.push(Math.hypot(values[0], values[1], values[2]));
      }
    }
    else if (row.kind === 'derived' || row.kind === 'derived_fusion' || row.kind === 'derived_fusion_final') {
      summary.derived++;
      summary.derivedKinds[row.kind] = (summary.derivedKinds[row.kind] || 0) + 1;
    }
    else if (row.kind === 'wifi_scan') {
      summary.wifiScans++;
      if (row.fresh_results === true) summary.freshWifi++;
      else summary.staleWifi++;
    } else if (row.kind === 'ble_observation') summary.bleObservations++;
    else if (row.kind === 'session_end') {
      summary.ended = true;
      summary.endSteps = row.total_steps ?? null;
      summary.stepsSinceStart = row.steps_since_start ?? null;
      summary.durationMs = row.session_elapsed_ms ?? null;
    }
  }
  summary.pressureMedianHpa = median(pressure);
  summary.magneticMedianUt = median(magnetic);
  return summary;
}

async function main() {
  const target = process.argv[2];
  if (!target) throw new Error('Usage: node summarize_android_jsonl_labels.cjs <file-or-directory> [output.json]');
  const stat = fs.statSync(target);
  const files = stat.isDirectory()
    ? fs.readdirSync(target).filter(name => name.endsWith('.jsonl')).sort().map(name => path.join(target, name))
    : [target];
  const summaries = [];
  for (const file of files) summaries.push(await summarize(file));
  const output = JSON.stringify(summaries, null, 2);
  if (process.argv[3]) fs.writeFileSync(process.argv[3], output + '\n');
  else process.stdout.write(output + '\n');
}

main().catch(error => { console.error(error); process.exitCode = 1; });
