const assert=require('node:assert/strict');
const Policy=require('../../../indoor/web/src/positioning/radio-scan-policy');

{
  const state=Policy.create({floor:2,destinationId:'TDM'});
  assert.equal(Policy.enterExtension(state,1000),false);
  assert.equal(Policy.decide(state,10000).reason,'destination_uses_main_corridor_pdr');
}

{
  const state=Policy.create({floor:2,destinationId:'2105-2'});
  assert.equal(Policy.decide(state,1000).reason,'extension_entry_not_confirmed');
  assert.equal(Policy.enterExtension(state,1000),true);
  assert.equal(Policy.decide(state,7000).reason,'no_pdr_progress_after_entry');
  Policy.noteProgress(state);
  assert.equal(Policy.decide(state,5999).request,false);
  assert.equal(Policy.decide(state,6000).reason,'inner_corridor_primary_scan');
  Policy.markRequested(state,6000);
  assert.equal(Policy.decide(state,35999).reason,'wifi_scan_cooldown');
  assert.equal(Policy.decide(state,36000).reason,'inner_corridor_retry_scan');
  Policy.markRequested(state,36000);
  assert.equal(Policy.decide(state,66000).reason,'inner_corridor_retry_scan');
  Policy.stopGuidance(state);
  assert.equal(Policy.decide(state,96000).reason,'guidance_ended');
}

console.log('radio scan policy tests passed');
