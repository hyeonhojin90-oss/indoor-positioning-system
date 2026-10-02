const {spawnSync}=require('node:child_process');
const path=require('node:path');
const root=path.resolve(__dirname,'..');
const tests=[
  ...['test_meter_scope_20261002','test_turn_buffer','test_wifi_anchor_fusion',
    'test_corridor_radio_guard','test_radio_unknown_support','test_magnetic_grid_runtime',
    'test_ble_four_signal_gate','test_heading_timestamp_skew'].map(t=>`indoor/tools/${t}.cjs`),
  ...['test-floor-tracking','test-position-tracking','test-initial-positioning',
    'test-fusion','test-radio-scan-policy','test-corridor-stride'].map(t=>`app/expo-sensor-collector/scripts/${t}.js`)
];
for(const test of tests){
  const result=spawnSync(process.execPath,[test],{cwd:root,stdio:'inherit'});
  if(result.error)throw result.error;
  if(result.status!==0)process.exit(result.status??1);
}
console.log(`PASS ${tests.length} indoor test scripts`);
