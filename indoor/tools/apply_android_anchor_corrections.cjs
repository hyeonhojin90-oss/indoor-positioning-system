#!/usr/bin/env node
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const readline = require('node:readline');

const sha256 = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');

async function rewrite(source, target, correction) {
  fs.mkdirSync(path.dirname(target), {recursive: true});
  const input = readline.createInterface({input: fs.createReadStream(source, {encoding: 'utf8'}), crlfDelay: Infinity});
  const output = fs.createWriteStream(target, {encoding: 'utf8'});
  let originalLabel = null;
  let changed = false;
  for await (const line of input) {
    if (!line.trim()) continue;
    const row = JSON.parse(line);
    if (!changed && row.kind === 'session_start' && row.label) {
      originalLabel = {...row.label};
      row.label = {...row.label, ...correction};
      changed = true;
    }
    output.write(JSON.stringify(row) + '\n');
  }
  await new Promise((resolve, reject) => output.end(error => error ? reject(error) : resolve()));
  if (!changed) throw new Error(`session_start label not found: ${source}`);
  return {originalLabel, correctedLabel: {...originalLabel, ...correction}};
}

async function main() {
  const configPath = process.argv[2];
  if (!configPath) throw new Error('Usage: node apply_android_anchor_corrections.cjs <config.json>');
  const config = JSON.parse(fs.readFileSync(configPath, 'utf8'));
  const base = path.dirname(configPath);
  const results = [];
  for (const item of config.corrections || []) {
    const source = path.resolve(base, item.source);
    const target = path.resolve(base, item.target);
    const {originalLabel, correctedLabel} = await rewrite(source, target, item.label || {});
    results.push({
      source_file: path.relative(process.cwd(), source),
      source_sha256: sha256(source),
      curated_file: path.relative(process.cwd(), target),
      curated_sha256: sha256(target),
      original_label: originalLabel,
      corrected_label: correctedLabel,
      reason: item.reason,
    });
  }
  const manifest = path.resolve(base, config.output || 'LABEL_CORRECTIONS.json');
  fs.writeFileSync(manifest, JSON.stringify({created_at: new Date().toISOString(), corrections: results}, null, 2) + '\n');
  console.log(`Corrected ${results.length} file(s): ${manifest}`);
}

main().catch(error => { console.error(error); process.exitCode = 1; });
