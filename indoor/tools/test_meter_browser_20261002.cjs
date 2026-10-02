const fs=require('node:fs'),assert=require('node:assert/strict'),{chromium}=require('playwright');
(async()=>{
  const browser=await chromium.launch({channel:'msedge',headless:true});
  const report={checks:[],pageErrors:[],consoleErrors:[],failedRequests:[]};
  try{
    const page=await browser.newPage();
    page.on('pageerror',e=>report.pageErrors.push(e.message));
    page.on('console',m=>{if(m.type()==='error')report.consoleErrors.push(m.text());});
    page.on('response',r=>{if(r.status()>=400)report.failedRequests.push({url:r.url(),status:r.status()});});
    await page.addInitScript(()=>{
      window.ready=false;window.records=[];
      window.RouteFusionHost={ready:()=>window.ready=true,failed:m=>{throw new Error(m);},publish:j=>window.records.push(JSON.parse(j))};
    });
    for(const coordinates of ['legacy','meters']){
      await page.goto(`http://127.0.0.1:4175/fusion-route-runtime.html?coordinates=${coordinates}`);
      await page.waitForFunction(()=>window.ready);
      for(let floor=1;floor<=10;floor++){
        const result=await page.evaluate(floor=>{
          const started=RouteFusion.start(floor,70.804,'samsung SM-S938N',`${floor}F_GUIDANCE_FUSION_V1`);
          const snapshot=RouteFusion.snapshot();RouteFusion.stop();return {started,snapshot};
        },floor);
        assert.ok(result.started);assert.equal(result.snapshot.floor,floor);
        assert.equal(result.snapshot.coordinateSystem,coordinates);
        assert.equal(result.snapshot.trackingState,'tracking');
        assert.ok(Number.isFinite(result.snapshot.x)&&Number.isFinite(result.snapshot.y));
        if(coordinates==='meters'){
          assert.equal(result.snapshot.metricPosition.units,'m');
          assert.ok(Math.abs(result.snapshot.metricPosition.x-50.1731274149)<.7);
          assert.ok(Math.abs(result.snapshot.x-70.804)<1);
        }
        report.checks.push({coordinates,floor,units:result.snapshot.positionUnits});
      }
      const ap=await page.evaluate(async()=>{
        RouteFusion.start(4,70.804,'samsung SM-S938N','F4_GUIDANCE_FUSION_V1');
        const refs=await (await fetch('data/positioning/wifi-references.json')).json();
        const ref=refs.references.find(r=>r.floor===4&&r.zone==='core_junction'&&r.anchor?.verified);
        const time=Date.now();
        const used=RouteFusion.wifi(time,{fresh:true,timestamp:time,rssi:ref.wifi});
        return {used,snapshot:RouteFusion.snapshot()};
      });
      assert.ok(ap.used);assert.equal(ap.snapshot.reason,'tracking_wifi_anchor_soft');
      assert.ok(ap.snapshot.zoneHypotheses[0].anchorId);
      report.checks.push({coordinates,apCoordinateConversion:true});
      const stairs=await page.evaluate(()=>{
        RouteFusion.start(4,70.804,'samsung SM-S938N','4F_CORE_TO_LEFT_STAIRS_REVERSE');
        const entered=RouteFusion.verticalEvidence(1000,{verified:true,entryConfirmed:true});
        const paused=RouteFusion.snapshot();
        const exited=RouteFusion.verticalEvidence(2000,{verified:true,beaconFloor:5});
        const resumed=RouteFusion.snapshot();return {entered,paused,exited,resumed};
      });
      assert.ok(stairs.entered);assert.ok(stairs.paused.locationLabel.includes('층간 이동'));
      assert.ok(stairs.exited);assert.equal(stairs.resumed.floor,5);
      report.checks.push({coordinates,verifiedVerticalBridge:true});
    }
    for(const floor of [1,2,3,4,5,10]){
      await page.goto(`http://127.0.0.1:4175/index.html?floor=${floor}`,{waitUntil:'networkidle'});
      assert.ok(await page.locator('svg').count()>0);
      report.checks.push({existing2d:floor});
    }
    for(const floor of [2,3]){
      await page.goto(`http://127.0.0.1:4175/navigation-review.html?floor=${floor}`,{waitUntil:'networkidle'});
      await page.waitForFunction(f=>window.navigationReview?.floor===f,floor);
      const blocked=await page.evaluate(()=>navigationReview.check([[800,732],[800,500]]));
      assert.ok(blocked.blocked);assert.ok((await page.locator('#status').textContent()).includes('측위 범위'));
      assert.ok((await page.locator('#caution').textContent()).includes('실제 공간이 막혀'));
      report.checks.push({navigationOverlay:floor,outOfScopeDoesNotMeanWall:true});
    }
    assert.deepEqual(report.pageErrors,[]);assert.deepEqual(report.consoleErrors,[]);assert.deepEqual(report.failedRequests,[]);
    fs.writeFileSync('indoor/data/analysis/meters-20261002/browser.json',JSON.stringify(report,null,2));
    console.log('PASS browser metric/legacy host, all floors, vertical bridge, existing 2D:',report.checks.length,'checks');
  }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
