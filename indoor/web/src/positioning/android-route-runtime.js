(async function () {
  'use strict';

  let runtime = null;
  let navigation = null;
  let models = null;
  let references = [];
  let magneticGrid = null;
  let maps = [];
  let ready = false;
  let lastPublish = 0;
  let lastInputTime = null;
  const coordinateSystem=new URLSearchParams(location.search).get('coordinates')==='meters'?'meters':'legacy';
  function hostView(view){
    return coordinateSystem==='meters'?{...view,metricPosition:{x:view.x,y:view.y,units:'m'},
      x:view.displayPosition.x,y:view.displayPosition.y,positionUnits:'legacy_display'}:view;
  }

  const read = async path => {
    const response = await fetch(path);
    if (!response.ok) throw new Error(`${path}: ${response.status}`);
    return response.json();
  };

  function publish(time, force = false) {
    if (!runtime || (!force && time - lastPublish < 500)) return;
    lastPublish = time;
    const view = IndoorRuntime.snapshot(runtime, maps);
    window.RouteFusionHost?.publish(JSON.stringify({
      kind: 'derived_fusion',
      wall_time_ms: time,
      published_wall_time_ms: Date.now(),
      last_input_time_ms: lastInputTime,
      last_step_time_ms: runtime.lastStep,
      comparison_variant: runtime.magneticGrid
        ? 'mode4_grid_primary_v2_fallback_ble_ap' : 'mode4_mag_v2_ble_ap',
      ...hostView(view),
    }));
  }

  function receive(row) {
    if (!runtime || !row || !Number.isFinite(row.time)) return;
    const time = row.time;
    lastInputTime = Math.max(lastInputTime ?? -Infinity, time);
    const values = row.values;
    if (row.sensor === 'heading_degrees') IndoorRuntime.heading(runtime, time, values?.[0], row.accuracy);
    else if (row.sensor === 'accelerometer_mps2') IndoorRuntime.acceleration(runtime, time, values || []);
    else if (row.sensor === 'magnetic_field_ut') IndoorRuntime.magnetic(runtime, time, values || []);
    else if (row.sensor === 'pressure_hpa') IndoorRuntime.pressure(runtime, time, values?.[0]);
    else if (row.sensor === 'ble') IndoorRuntime.ble(runtime, time, row.observation);
    publish(time);
  }

  function routeStart(floor, fallbackX, routeId) {
    const map = IndoorNavigation.compile(navigation, floor);
    const reversed = /_REVERSE$/.test(routeId || '');
    // Reverse walks are labelled at the corridor-side stair entrance, not at
    // the center of the whole stair area. Use the surveyed corridor endpoints.
    if (reversed && /TO_RIGHT_STAIRS/.test(routeId || ''))
      return { x: map.distanceMetric.mapBreaks[0], y: 0 };
    if (reversed && /TO_LEFT_STAIRS/.test(routeId || ''))
      return { x: map.distanceMetric.mapBreaks.at(-1), y: 0 };
    let areaId = null;
    if (/2F_EXTENSION_V3/.test(routeId || '')) areaId = reversed ? 'extension' : 'entry';
    else if (/3F_IT_HALL/.test(routeId || '')) areaId = reversed ? 'it_hall' : 'entry';
    else if (!/^1F_/.test(routeId || '')) areaId = 'core_junction';
    const area = map.areas.find(candidate => candidate.id === areaId && Array.isArray(candidate.rect));
    if (/2F_EXTENSION_V3/.test(routeId || '') && map.survey) {
      const corridor = map.areas.find(candidate => candidate.id === 'extension');
      return {x:(corridor.rect[0]+corridor.rect[2])/2,
        // The labelled start is the portal centerline. Seed 1 cm inside the
        // mapped entry so an extension-bound heading is not flattened onto
        // the main-corridor axis before branch particles can survive.
        y:reversed ? corridor.rect[3] : 1.18};
    }
    if (area) return {
      x: (area.rect[0] + area.rect[2]) / 2,
      y: (area.rect[1] + area.rect[3]) / 2,
    };
    return { x: fallbackX, y: 0 };
  }

  window.RouteFusion = {
    start(floor, x, device, routeId) {
      if (!ready || !Number.isFinite(floor) || !Number.isFinite(x)) return false;
      const start = routeStart(floor, x, routeId);
      const useGrid = floor === 4 && /TO_RIGHT_STAIRS/.test(routeId || '') && !!magneticGrid;
      runtime = IndoorRuntime.create(navigation, models, references, {
        coordinateSystem,inputCoordinates:'legacy',
        floor,
        x: start.x,
        y: start.y,
        platform: 'android',
        device,
        magneticZoneEnabled: false,
        magneticGridEnabled: useGrid,
        magneticGrid: useGrid ? magneticGrid : null,
        sequenceEnabled: true,
        sequenceFallbackEnabled: useGrid,
        bleEnabled: true,
      });
      runtime.routeId = routeId || '';
      lastPublish = 0;
      lastInputTime = null;
      publish(Date.now(), true);
      return true;
    },
    receive,
    captureLap(index, pressedAtMs) {
      if (!runtime || !Number.isInteger(index) || !Number.isFinite(pressedAtMs)) return false;
      window.RouteFusionHost?.publish(JSON.stringify({
        kind: 'lap_fusion_snapshot',
        wall_time_ms: Date.now(),
        lap_wall_time_ms: pressedAtMs,
        lap_index: index,
        last_input_time_ms: lastInputTime,
        last_step_time_ms: runtime.lastStep,
        ...hostView(IndoorRuntime.snapshot(runtime, maps)),
      }));
      return true;
    },
    wifi(time, scan) {
      if (!runtime) return false;
      const used = IndoorRuntime.wifi(runtime, time, scan);
      publish(time, true);
      return used;
    },
    verticalEvidence(time,evidence){
      if(!runtime)return false;
      const used=IndoorRuntime.verticalEvidence(runtime,evidence,time);publish(time,true);return used;
    },
    snapshot() {
      if (!runtime) return null;
      publish(Date.now(), true);
      return hostView(IndoorRuntime.snapshot(runtime, maps));
    },
    stop() {
      if (runtime) publish(Date.now(), true);
      runtime = null;
      lastPublish = 0;
    },
  };

  try {
    const wifiReferences = await read('data/positioning/wifi-references.json').catch(() => ({ references: [] }));
    let zoneReferences;
    let bleReferences;
    [navigation, models, zoneReferences, bleReferences, ...maps] = await Promise.all([
      read('data/navigation/areas-v1.json'),
      read('data/positioning/motion-models.json'),
      read('data/positioning/zone-references.json'),
      read('data/positioning/ble-references.json'),
      ...Array.from({ length: 10 }, (_, index) => read(`data/maps/floor-${String(index + 1).padStart(2, '0')}.json`)),
    ]);
    references = [
      ...(zoneReferences.references || []),
      ...(bleReferences.references || []),
      ...(wifiReferences.references || []),
    ];
    // The measured grid currently covers only the 4F right main corridor.
    // If the asset is unavailable, retain the existing V2 route behavior.
    magneticGrid = await read('data/positioning/grid-4f-right.json').catch(() => null);
    ready = true;
    window.RouteFusionHost?.ready();
  } catch (error) {
    window.RouteFusionHost?.failed(error?.message || String(error));
  }
})();
