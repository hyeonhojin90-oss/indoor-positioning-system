const assert = require('node:assert/strict');
const {ROUTES, reverseRoute} = require('../routes');
const fs = require('node:fs');
const vm = require('node:vm');
const app = fs.readFileSync(require('node:path').join(__dirname, '../App.js'), 'utf8');
const directionFunction = app.match(/function routeDirectionSign\(route\) \{[\s\S]*?\n\}/)[0];
const directionSign = vm.runInNewContext(`(${directionFunction})`);
const routes = ROUTES.filter(r => !r.mode && r.laps.length);
for (const route of routes) {
  const before = JSON.stringify(route);
  const reversed = reverseRoute(route);
  assert.equal(JSON.stringify(route), before, 'original route is immutable');
  assert.equal(reversed.start, route.laps.at(-1));
  assert.equal(reversed.destination, route.start);
  assert.deepEqual(reversed.laps, route.laps.slice(0,-1).reverse().concat(route.start));
  assert.equal(reversed.sourceRouteId, route.id);
  assert.equal(reversed.travelDirection, 'reverse');
  assert.equal(reversed.floor, route.floor);
  assert.equal(directionSign(reversed), -directionSign(route));
}
const right = reverseRoute(ROUTES.find(r => r.id === '4F_CORE_TO_RIGHT_STAIRS'));
assert.equal(right.start, '오른쪽 계단 입구');
assert.equal(right.laps.at(-1), '코어복도 출구 중앙점');
assert.equal(right.laps.length, 12);
assert.ok(ROUTES.find(r=>r.id==='4F_RIGHT_STAIR_INTERIOR').collectionOnly);
assert.ok(right.laps.includes('오른쪽 끝 화장실 통로 앞'));
assert.ok(ROUTES.find(r=>r.id==='4F_CORE_TO_LEFT_STAIRS').laps.every(l=>!l.includes('내부')));
console.log(`PASS reverse route endpoints, lap order, metadata and immutability: ${routes.length} routes`);
