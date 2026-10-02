const A=require('node:assert/strict'),F=require('../web/src/positioning/fusion-engine'),Z=require('../web/src/positioning/zone-classifier');
const data=require('../web/data/navigation/areas-v1.json');
const ref={floor:4,platform:'android',zone:'core_junction',wifi:{a:-50,b:-55,c:-60,d:-65},anchor:{id:'core',x:70.804,y:0,verified:false,sources:1}};
const classify=(rssi,t=10000)=>Z.classify({id:String(t),timestamp:t,platform:'android',wifi:{supported:true,fresh:true,timestamp:t,rssi}},[ref],t);
for(const rssi of [{z:-50},{a:-50,b:-55},{a:-30,b:-35,c:-40,d:-45}]){
 const state=F.create(data,{floor:4,x:75,y:0}),before=JSON.stringify(state.particles);
 const obs=classify(rssi);A.equal(F.observeWifi(state,obs,10000),false);A.equal(F.recover(state,obs,10000),false);A.equal(JSON.stringify(state.particles),before);
}
const state=F.create(data,{hypotheses:[{floor:4,x:75,y:0,weight:4},{floor:4,x:120,y:0,weight:1}],count:160});
const positions=state.particles.map(p=>[p.x,p.y]);
A.equal(F.observeWifi(state,classify(ref.wifi),10000),true);
A.deepEqual(state.particles.map(p=>[p.x,p.y]),positions,'AP must preserve support and must not reseed or resample');
A.ok(state.particles.filter(p=>p.x>115).every(p=>p.weight>0),'unknown region must retain mass');
const ble=F.create(data,{floor:4,x:125,y:0});const support=new Set(ble.particles.map(p=>`${p.x}:${p.y}`));
A.equal(F.observeRadio(ble,{id:'ble',timestamp:10000,features:['ble'],featureTimes:{ble:10000},quality:1,candidates:[{floor:4,zone:'stairs_left',weight:1,anchor:{x:135.407,y:0}}]},10000),true);
A.ok(ble.particles.every(p=>support.has(`${p.x}:${p.y}`)),'single candidate weight=1 must not generate anchor positions');
console.log('PASS unmatched AP neutrality, partial-support preservation, BLE no reseeding');
