const {chromium}=require('playwright');
const assert=require('node:assert/strict'),fs=require('node:fs');
const references=require('../web/data/positioning/wifi-references.json').references;
const core=references.find(r=>r.floor===4&&r.zone==='core_junction'&&r.anchor?.verified);
const rightStart=String(require('../web/data/maps/common-corridor-survey.json').map_breaks[0]);
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 const report={checks:[],errors:[],failedRequests:[]};
 try{
  const page=await browser.newPage();
  page.on('pageerror',e=>report.errors.push(e.message));
  page.on('response',r=>{if(r.status()>=400)report.failedRequests.push(r.url());});
  await page.addInitScript(()=>{window.records=[];window.SensorHost={start:()=>JSON.stringify({ok:true,device:'samsung SM-S938N'}),record:j=>records.push(JSON.parse(j)),stop:()=>{}};});
  await page.goto('http://127.0.0.1:4175/fusion-experiment.html');
  await page.waitForFunction(()=>!document.querySelector('#begin').disabled);
  assert.equal(await page.locator('#start option').nth(1).getAttribute('value'),rightStart);
  await page.click('#begin');
  assert.equal(await page.evaluate(()=>records[0].ap_enabled),true);
  const result=await page.evaluate(r=>{
    const time=Date.now();const scan={fresh:true,timestamp:time,rssi:r.wifi,quality:.5,steps_during_scan:1};
    receiveSensorBatch([{sensor:'wifi',time,scan}]);
    const first=records.at(-1);
    receiveSensorBatch([{sensor:'wifi',time:time+1,scan}]);
    return {first,last:records.at(-1)};
  },core);
  assert.equal(result.first.wifiDiagnostic.applied,true);
  assert.equal(result.first.wifiDiagnostic.quality,.5);
  assert.equal(result.last.wifiDiagnostic.applied,false);
  assert.equal(result.last.wifiDiagnostic.reason,'stale_or_duplicate');
  report.checks.push('mode4 AP reference loading, accepted fingerprint, moving-scan quality, duplicate rejection');
  await page.click('#stop');
  await page.selectOption('#start',rightStart); await page.click('#begin');
  const distant=await page.evaluate(r=>{
    const time=Date.now();
    receiveSensorBatch([{sensor:'wifi',time,scan:{fresh:true,timestamp:time,rssi:r.wifi,quality:1}}]);
    return records.at(-1);
  },core);
  assert.equal(distant.wifiDiagnostic.applied,false);
  assert.equal(distant.wifiDiagnostic.reason,'wifi_outside_pdr_gate');
  report.checks.push('distant core match rejected at right stair start; rejection reason reaches Android host');
  await page.click('#stop');
  await page.selectOption('#mode','pdr'); await page.click('#begin');
  assert.equal(await page.evaluate(()=>records.filter(r=>r.kind==='fusion_experiment_mode').at(-1).ap_enabled),false);
  await page.click('#stop');
  await page.selectOption('#mode','mag_ble'); await page.uncheck('#ap'); await page.click('#begin');
  assert.equal(await page.evaluate(()=>records.filter(r=>r.kind==='fusion_experiment_mode').at(-1).ap_enabled),false);
  await page.click('#stop');
  report.checks.push('AP disabled comparison and baseline preserved; stop/restart controls');
  assert.deepEqual(report.errors,[]); assert.deepEqual(report.failedRequests,[]);
  fs.mkdirSync('app/android-updates/20261002',{recursive:true});
  fs.writeFileSync('app/android-updates/20261002/browser-verification.json',JSON.stringify(report,null,2));
  console.log(JSON.stringify(report));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
