const fs=require("node:fs"),path=require("node:path"),assert=require("node:assert/strict");
// Set NODE_PATH to the installed Playwright module directory. Uses existing Edge.
const {chromium}=require("playwright");
const base=process.env.NAV_TEST_URL || "http://127.0.0.1:4175";
const output=path.resolve(__dirname,"../data/analysis/meters-20261002/navigation-browser");
(async()=>{
  const browser=await chromium.launch({channel:"msedge",headless:true});
  try {
    const page=await browser.newPage({viewport:{width:1450,height:1100}}),errors=[],failed=[],checks=[];
    page.on("pageerror",e=>errors.push(e.message));
    page.on("console",m=>{if(m.type()==="error")errors.push(m.text());});
    page.on("response",r=>{if(r.status()>=400)failed.push({url:r.url(),status:r.status()});});
    await page.goto(`${base}/navigation-review.html?floor=2`,{waitUntil:"networkidle"});
    await page.waitForFunction(()=>window.navigationReview?.floor===2);
    assert.equal(await page.locator(".nav-wall").count(),5);
    const expected2fStatus=["연결됩니다","연결됩니다","연결됩니다","통과 제한","연결됩니다"];
    for(let i=0;i<expected2fStatus.length;i++) {
      await page.selectOption("#route",String(i));await page.click("#showRoute");
      const result=await page.locator("#status").textContent();checks.push({floor:2,route:i,result});
      assert.ok(result.includes(expected2fStatus[i]));
    }
    await page.selectOption("#route","1");await page.click("#showRoute");
    fs.mkdirSync(output,{recursive:true});
    await page.screenshot({path:path.join(output,"navigation-2f.png"),fullPage:true});
    await page.uncheck("#overlay");assert.equal(await page.locator("[data-navigation-overlay]").isVisible(),false);
    await page.check("#overlay");
    await page.selectOption("#floor","3");await page.waitForFunction(()=>window.navigationReview?.floor===3);
    for(let i=0;i<2;i++) {
      await page.selectOption("#route",String(i));await page.click("#showRoute");
      const result=await page.locator("#status").textContent();checks.push({floor:3,route:i,result});
      assert.ok(result.includes(i===0?'연결됩니다':'측위 범위'));
    }
    await page.screenshot({path:path.join(output,"navigation-3f.png"),fullPage:true});
    // Existing pages must still load, including embedded original floor SVGs.
    for(const floor of [2,3,4]) {
      await page.goto(`${base}/index.html?floor=${floor}`,{waitUntil:"networkidle"});
      assert.equal(await page.locator('a[href="./navigation-review.html?floor=2"]').count(),1);
      checks.push({existing2d:floor,title:await page.title()});
    }
    assert.deepEqual(errors,[]);assert.deepEqual(failed,[]);
    const report={base,checks,consoleErrors:errors,failedRequests:failed};
    fs.writeFileSync(path.join(output,"browser.json"),JSON.stringify(report,null,2)+"\n");console.log(JSON.stringify(report,null,2));
  } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
