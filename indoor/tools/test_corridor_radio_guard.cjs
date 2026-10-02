const assert=require('node:assert/strict');
const Fusion=require('../web/src/positioning/fusion-engine');
const map=require('../web/data/navigation/areas-v1.json');

const time=10000;
const state=Fusion.create(map,{floor:4,x:64,y:0,count:160,seed:42});
assert.equal(Fusion.snapshot(state).zone,'main_right');
const wrong={floor:4,zone:'main_left',weight:.95,wifiScore:1,
  anchor:{id:'left_4122',label:'4122 앞',x:76,y:0,sigma_m:6}};
const right={floor:4,zone:'main_right',weight:.05,wifiScore:3,
  anchor:{id:'right_4209',label:'오른쪽 복도',x:63,y:0,sigma_m:6}};
const wifi={id:'wifi',timestamp:time,features:['wifi'],featureTimes:{wifi:time},
  wifiAbsoluteAccepted:true,quality:1,candidates:[wrong,right]};
assert.equal(Fusion.observeWifi(state,wifi,time),false);
const view=Fusion.snapshot(state);
assert.equal(view.zone,'main_right');
assert.deepEqual(view.zoneHypotheses,[],'a wrong-corridor winner must not qualify a weaker nearby AP candidate');
assert.equal(Fusion.observeWifi(state,{...wifi,id:'right-wifi',timestamp:time+1,featureTimes:{wifi:time+1},
  candidates:[{...right,wifiScore:1,weight:1}]},time+1),true);
assert.deepEqual(Fusion.snapshot(state).zoneHypotheses.map(c=>c.anchorId),['right_4209']);
const bleState=Fusion.create(map,{floor:4,x:64,y:0,count:160,seed:42});
const ble={id:'ble',timestamp:time,features:['ble'],featureTimes:{ble:time},
  quality:1,candidates:[wrong,right]};
assert.equal(Fusion.observeRadio(bleState,ble,time),true);
assert.deepEqual(Fusion.snapshot(bleState).radioHypotheses.map(c=>c.anchorId),['right_4209']);
const onlyWrong=Fusion.create(map,{floor:4,x:64,y:0,count:160,seed:42});
assert.equal(Fusion.observeWifi(onlyWrong,{...wifi,candidates:[wrong]},time),false);
assert.equal(Fusion.snapshot(onlyWrong).zoneHypotheses.length,0);
console.log('PASS moving on right corridor rejects left-corridor AP/BLE labels');
