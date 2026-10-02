(function(root,factory){
  if(typeof module==='object'&&module.exports)module.exports=factory();
  else root.IndoorRadioScanPolicy=factory();
})(globalThis,function(){
  'use strict';

  const FLOOR_TWO_EXTENSION_TARGETS=new Set(['2104-1','2104-2','2105-1','2105-2']);
  const DEFAULT_ENTRY_DELAY_MS=5000;
  const DEFAULT_WIFI_INTERVAL_MS=30000;

  function create(options={}){
    return {
      floor:Number(options.floor),
      destinationId:String(options.destinationId||''),
      entryDelayMs:Number.isFinite(options.entryDelayMs)?options.entryDelayMs:DEFAULT_ENTRY_DELAY_MS,
      wifiIntervalMs:Number.isFinite(options.wifiIntervalMs)?options.wifiIntervalMs:DEFAULT_WIFI_INTERVAL_MS,
      entryTime:null,
      entryProgressed:false,
      lastRequestTime:-Infinity,
      requestCount:0,
      guidanceActive:true,
    };
  }

  function isExtensionTarget(state){
    return state.floor===2&&FLOOR_TWO_EXTENSION_TARGETS.has(state.destinationId);
  }

  function enterExtension(state,time){
    if(!isExtensionTarget(state)||!Number.isFinite(time))return false;
    if(state.entryTime===null)state.entryTime=time;
    return true;
  }

  function noteProgress(state){
    if(state.entryTime===null)return false;
    state.entryProgressed=true;
    return true;
  }

  function decide(state,time){
    if(!state.guidanceActive)return {request:false,reason:'guidance_ended'};
    if(!isExtensionTarget(state))return {request:false,reason:'destination_uses_main_corridor_pdr'};
    if(state.entryTime===null)return {request:false,reason:'extension_entry_not_confirmed'};
    if(!state.entryProgressed)return {request:false,reason:'no_pdr_progress_after_entry'};
    const entryElapsed=time-state.entryTime;
    if(!Number.isFinite(entryElapsed)||entryElapsed<state.entryDelayMs){
      return {request:false,reason:'waiting_for_inner_corridor',remainingMs:Math.max(0,state.entryDelayMs-entryElapsed)};
    }
    const cooldown=time-state.lastRequestTime;
    if(cooldown<state.wifiIntervalMs){
      return {request:false,reason:'wifi_scan_cooldown',remainingMs:Math.max(0,state.wifiIntervalMs-cooldown)};
    }
    return {request:true,reason:state.requestCount===0?'inner_corridor_primary_scan':'inner_corridor_retry_scan'};
  }

  function markRequested(state,time){
    state.lastRequestTime=time;
    state.requestCount++;
  }

  function stopGuidance(state){state.guidanceActive=false;}

  return {DEFAULT_ENTRY_DELAY_MS,DEFAULT_WIFI_INTERVAL_MS,create,isExtensionTarget,enterExtension,noteProgress,decide,markRequested,stopGuidance};
});
