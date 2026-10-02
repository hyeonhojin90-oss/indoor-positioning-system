#!/usr/bin/env node
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');

const ROOT = path.resolve(__dirname, '..', '..');
const RAW = path.join(ROOT, 'indoor', 'data', 'raw', 'android');
const MAPS = path.join(ROOT, 'indoor', 'web', 'data', 'maps');
const OUTPUT = path.join(ROOT, 'indoor', 'web', 'data', 'positioning', 'wifi-references.json');

const median = values => {
  const sorted = values.filter(Number.isFinite).sort((a, b) => a - b);
  if (!sorted.length) return null;
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
};

function walk(target) {
  if (!fs.existsSync(target)) return [];
  const stat = fs.statSync(target);
  if (stat.isFile()) return target.endsWith('.jsonl') ? [target] : [];
  return fs.readdirSync(target, { withFileTypes: true }).flatMap(entry => walk(path.join(target, entry.name)));
}

function parse(file) {
  const source = fs.readFileSync(file, 'utf8').replace(/^\uFEFF/, '').replace(/}(?:\\r)?\\n(?=\{)/g, '}\n');
  const rows = [];
  for (const line of source.split(/\r?\n/)) {
    if (!line.trim()) continue;
    try { rows.push(JSON.parse(line)); } catch { /* preserve raw file; skip only malformed row */ }
  }
  return rows;
}

function apId(bssid) {
  return `ap_${crypto.createHash('sha256').update(String(bssid)).digest('hex').slice(0, 10)}`;
}

function anchorDefinition(floor, storedZone) {
  const map = JSON.parse(fs.readFileSync(path.join(MAPS, `floor-${String(floor).padStart(2, '0')}.json`), 'utf8'));
  const base = JSON.parse(fs.readFileSync(path.join(MAPS, 'floor-04.json'), 'utf8'));
  const layout = map.layout_dimensions || base.layout_dimensions;
  const coreX = Number(map.routing?.hub_junction?.x ?? (Number(layout.left_corridor_length) + Number(layout.hub_outer_width) / 2));
  const roomX = id => Number(map.rooms?.find(room => String(room.id) === id)?.front_x);
  if (storedZone === 'core_junction') return { zone: 'core_junction', id: `F${floor}_CORE`, x: coreX, y: 0 };
  if (storedZone === 'stairs_right') return { zone: 'stairs_right', id: `F${floor}_RIGHT_STAIRS`, x: 0, y: 0 };
  if (storedZone === 'stairs_left') return { zone: 'stairs_left', id: `F${floor}_LEFT_STAIRS`, x: Number(layout.main_length || 135.407), y: 0 };
  if (floor === 2 && storedZone === 'f2_extension_entry') {
    const x = Number(map.floor2_extension?.survey?.entry_axis_map_x ?? roomX('2204'));
    return { zone: 'main_right', id: 'F2_EXTENSION_ENTRY', x, y: 0 };
  }
  if (floor === 3 && storedZone === 'f3_extension_entry') return { zone: 'main_right', id: 'F3_EXTENSION_ENTRY', x: roomX('3203'), y: 0 };
  return null;
}

const sessions = [];
const seenContent = new Set();
for (const file of walk(RAW).sort()) {
  const content = fs.readFileSync(file);
  const digest = crypto.createHash('sha256').update(content).digest('hex');
  if (seenContent.has(digest)) continue;
  seenContent.add(digest);
  const rows = parse(file);
  const start = rows.find(row => row.kind === 'session_start');
  const end = rows.find(row => row.kind === 'session_end');
  const label = start?.label || {};
  if (Number(start?.schema_version) < 7 || !end || !label.zone_id) continue;
  const floor = Number(label.floor);
  const anchor = anchorDefinition(floor, label.zone_id);
  if (!anchor || !Number.isFinite(anchor.x)) continue;
  const readings = new Map();
  rows.filter(row => row.kind === 'wifi_scan' && row.fresh_results === true).forEach(row => {
    (row.access_points || []).forEach(ap => {
      if (!ap.bssid || !Number.isFinite(ap.rssi_dbm)) return;
      const id = apId(ap.bssid);
      if (!readings.has(id)) readings.set(id, []);
      readings.get(id).push(ap.rssi_dbm);
    });
  });
  if (readings.size < 2) continue;
  sessions.push({
    floor,
    platform: start.platform || 'android',
    device: start.device || null,
    storedZone: label.zone_id,
    anchor,
    source: path.basename(file),
    wifi: Object.fromEntries([...readings].map(([id, values]) => [id, median(values)])),
  });
}

const groups = new Map();
for (const session of sessions) {
  const key = [session.floor, session.platform, session.device, session.storedZone].join('|');
  if (!groups.has(key)) groups.set(key, []);
  groups.get(key).push(session);
}

const references = [...groups.values()].map(group => {
  const first = group[0];
  const values = new Map();
  for (const session of group) for (const [id, rssi] of Object.entries(session.wifi)) {
    if (!values.has(id)) values.set(id, []);
    values.get(id).push(rssi);
  }
  const minimumPresence = Math.max(1, Math.ceil(group.length / 2));
  const wifi = Object.fromEntries([...values]
    .filter(([, readings]) => readings.length >= minimumPresence)
    .map(([id, readings]) => [id, median(readings)]));
  const sources = [...new Set(group.map(session => session.source))].sort();
  return {
    floor: first.floor,
    platform: first.platform,
    device: first.device,
    zone: first.anchor.zone,
    magnetic: null,
    spread: 6,
    wifi,
    sources,
    provenance: 'schema7-fresh-wifi-stationary-median',
    position: { x: first.anchor.x, y: first.anchor.y },
    anchor: {
      id: first.anchor.id,
      x: first.anchor.x,
      y: first.anchor.y,
      sigma_m: 6,
      verified: sources.length >= 3,
      sources: sources.length,
    },
  };
}).filter(reference => Object.keys(reference.wifi).length >= 2)
  .sort((a, b) => a.floor - b.floor || a.anchor.id.localeCompare(b.anchor.id));

fs.writeFileSync(OUTPUT, `${JSON.stringify({
  version: 1,
  generated_at: new Date().toISOString(),
  policy: 'Fresh stationary scans only; one scan is weak evidence, hard recovery still requires independently repeated verified anchors.',
  identifier: 'sha256 bssid prefix 10 with ap_ prefix',
  references,
}, null, 2)}\n`);
console.log(`wrote ${path.relative(ROOT, OUTPUT)}: ${references.length} references from ${sessions.length} unique sessions`);
