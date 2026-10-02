const assert=require('node:assert/strict');
const Z=require('../web/src/positioning/zone-classifier');
const R=require('../web/src/positioning/runtime');
const data=require('../web/data/navigation/areas-v1.json');
const refs=[{floor:4,platform:'android',zone:'core_junction',ble:{a:-50,b:-55,c:-60,d:-65},anchor:{id:'core',x:70.804,y:0}}];
const classify=rssi=>Z.classify({timestamp:5000,platform:'android',ble:{supported:true,timestamp:5000,rssi}},refs,5000);
assert.equal(classify({a:-50,b:-55,c:-60}).reason,'no_usable_features');
assert.equal(classify({a:-50,b:-55,c:-60,d:-65}).candidates[0].zone,'core_junction');
assert.equal(classify({a:-50,b:-55,c:-60,x:-65}).reason,'no_usable_features','four observed IDs must share four reference IDs');
for(const n of [3,4]){
 const r=R.create(data,{},refs,{floor:4,x:70.804,y:0,platform:'android',bleEnabled:true});
 for(const t of [1000,1100])for(const [id,rssi] of Object.entries(refs[0].ble).slice(0,n))R.ble(r,t,{anonymous_id:id,rssi_dbm:rssi});
 R.ble(r,4100,{anonymous_id:'a',rssi_dbm:-50});
 assert.equal(r.engine.observationReason,n===4?'relative_zone_scores':'insufficient_ble_window');
}
console.log('PASS: BLE 3/4 common-ID boundary and runtime window gate');
