(async function(){
  'use strict';const $=id=>document.getElementById(id);let runtime=null,lastPublish=0,models,nav,refs,maps,grid,bleStatus='BLE 대기',wifiStatus='AP 이벤트 대기',apEnabled=false;
  for(let f=1;f<=10;f++){const o=document.createElement('option');o.value=f;o.textContent=`${f}층`;if(f===4)o.selected=true;$('floor').append(o);}
  function publish(time){if(!runtime||time-lastPublish<500)return;lastPublish=time;
    const view=IndoorRuntime.snapshot(runtime,maps);$('pose').textContent=`${view.floor}층 · ${view.zoneLabel}`;
    $('rooms').textContent=view.landmarks.map(r=>r.label).join(' / ');
    $('details').textContent=`걸음 ${view.steps} · x ${view.x.toFixed(1)}, y ${view.y.toFixed(1)} · 보행 품질 ${(view.motionQuality*100).toFixed(0)}% · 자기장 격자 ${view.magneticGridStats.applied}/${view.magneticGridStats.evaluated} · V2 ${view.sequenceStats.applied}/${view.sequenceStats.evaluated} · BLE ${view.bleStats.applied}/${view.bleStats.evaluated} · ${bleStatus} · ${apEnabled?wifiStatus:'AP 비교 비활성'}`;
    $('status').textContent=`${view.reason} / ${view.verticalStatus} / ${view.sequenceReason} / ${view.observationReason}`;
    window.SensorHost?.record(JSON.stringify({kind:'derived_fusion',wall_time_ms:time,...view}));
  }
  window.receiveSensorBatch=function(rows){if(!runtime)return;
    for(const row of rows){const t=row.time,v=row.values;
      if(row.sensor==='heading_degrees')IndoorRuntime.heading(runtime,t,v[0],row.accuracy);
      else if(row.sensor==='accelerometer_mps2')IndoorRuntime.acceleration(runtime,t,v);
      else if(row.sensor==='magnetic_field_ut')IndoorRuntime.magnetic(runtime,t,v);
      else if(row.sensor==='pressure_hpa')IndoorRuntime.pressure(runtime,t,v[0]);
      else if(row.sensor==='wifi'&&apEnabled){IndoorRuntime.wifi(runtime,t,row.scan);lastPublish=0;}
      else if(row.sensor==='wifi_status'){wifiStatus=row.status;lastPublish=0;}
      else if(row.sensor==='ble')IndoorRuntime.ble(runtime,t,row.observation);
      else if(row.sensor==='ble_status')bleStatus=`${row.snapshot.status} · 송신기 ${row.snapshot.transmitter_count}개`;
      publish(t);
    }
  };
  window.experimentInterrupted=function(message){runtime=null;$('begin').disabled=false;$('stop').disabled=true;$('floor').disabled=false;$('start').disabled=false;$('mode').disabled=false;$('ap').disabled=false;$('status').textContent=message;};
  try{
    const read=async p=>{const r=await fetch(p);if(!r.ok)throw Error(`${p}: ${r.status}`);return r.json();};
    let bleRefs;[nav,models,refs,bleRefs,...maps]=await Promise.all([read('data/navigation/areas-v1.json'),read('data/positioning/motion-models.json'),read('data/positioning/zone-references.json'),read('data/positioning/ble-references.json'),...Array.from({length:10},(_,i)=>read(`data/maps/floor-${String(i+1).padStart(2,'0')}.json`))]);
    refs={references:[...refs.references,...bleRefs.references]};
    const wifiRefs=await read('data/positioning/wifi-references.json');
    refs.references.push(...wifiRefs.references);
    grid=await read('data/positioning/grid-4f-right.json').catch(()=>null);
    function updateStartLines(){
      const map=IndoorNavigation.compile(nav,Number($('floor').value));
      // Physical distance zero corresponds to the surveyed legacy map endpoint.
      $('start').options[1].value=String(map.distanceMetric.mapBreaks[0]);
      $('start').options[2].value=String(map.distanceMetric.mapBreaks.at(-1));
    }
    $('floor').onchange=updateStartLines;updateStartLines();
    $('pose').textContent='시작 위치 선택';$('status').textContent=window.SensorHost?'Android 센서 연결 준비 완료':'웹 미리보기입니다. 실제 센서는 Android 앱에서 연결됩니다.';
    $('begin').disabled=!window.SensorHost;
    $('begin').onclick=()=>{
      const floor=Number($('floor').value),x=Number($('start').value);
      const result=JSON.parse(window.SensorHost.start(floor,x));
      if(!result.ok){$('status').textContent=result.message;return;}
      const mode=$('mode').value,mag=mode==='mag'||mode==='mag_ble',ble=mode==='ble'||mode==='mag_ble';bleStatus=ble?'BLE 시작 중':'BLE 보정 비활성';
      apEnabled=mode==='mag_ble'&&$('ap').checked;wifiStatus='AP 이벤트 대기';
      const useGrid=mag&&floor===4&&!!grid;
      runtime=IndoorRuntime.create(nav,models,refs.references,{floor,x,y:0,platform:'android',device:result.device,
        magneticZoneEnabled:false,sequenceEnabled:mag,bleEnabled:ble,
        magneticGridEnabled:useGrid,magneticGrid:useGrid?grid:null,sequenceFallbackEnabled:useGrid});
      window.SensorHost.record(JSON.stringify({kind:'fusion_experiment_mode',wall_time_ms:Date.now(),mode,ap_enabled:apEnabled,ap_policy:'event_ap_v1',magnetic_sequence_v2:mag,magnetic_grid_enabled:useGrid,ble_enabled:ble}));
      lastPublish=0;for(const id of ['begin','floor','start','mode','ap'])$(id).disabled=true;$('stop').disabled=false;
    };
    $('stop').onclick=()=>{if(runtime)window.SensorHost.record(JSON.stringify({kind:'derived_fusion_final',...IndoorRuntime.snapshot(runtime,maps)}));
      window.SensorHost.stop();window.experimentInterrupted('측정 종료 · Downloads/IndoorPositioning 저장');};
  }catch(e){$('status').textContent=e.message;console.error(e);}
})();
