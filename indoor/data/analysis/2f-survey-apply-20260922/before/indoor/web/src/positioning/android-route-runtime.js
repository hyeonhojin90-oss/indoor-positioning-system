(async function () {
  'use strict';

  let runtime = null;
  let navigation = null;
  let models = null;
  let references = [];
  let maps = [];
  let ready = false;
  let lastPublish = 0;

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
      comparison_variant: 'mode4_mag_v2_ble_ap',
      ...view,
    }));
  }

  function receive(row) {
    if (!runtime || !row || !Number.isFinite(row.time)) return;
    const time = row.time;
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
    let areaId = null;
    if (/2F_EXTENSION_V3/.test(routeId || '')) areaId = reversed ? 'extension' : 'entry';
    else if (/3F_IT_HALL/.test(routeId || '')) areaId = reversed ? 'it_hall' : 'entry';
    else if (reversed && /TO_RIGHT_STAIRS/.test(routeId || '')) areaId = 'stairs_right';
    else if (reversed && /TO_LEFT_STAIRS/.test(routeId || '')) areaId = 'stairs_left';
    else if (!/^1F_/.test(routeId || '')) areaId = 'core_junction';
    const area = map.areas.find(candidate => candidate.id === areaId && Array.isArray(candidate.rect));
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
      runtime = IndoorRuntime.create(navigation, models, references, {
        floor,
        x: start.x,
        y: start.y,
        platform: 'android',
        device,
        magneticZoneEnabled: false,
        sequenceEnabled: true,
        bleEnabled: true,
      });
      runtime.routeId = routeId || '';
      lastPublish = 0;
      publish(Date.now(), true);
      return true;
    },
    receive,
    wifi(time, scan) {
      if (!runtime) return false;
      const used = IndoorRuntime.wifi(runtime, time, scan);
      publish(time, true);
      return used;
    },
    snapshot() {
      if (!runtime) return null;
      publish(Date.now(), true);
      return IndoorRuntime.snapshot(runtime, maps);
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
    ready = true;
    window.RouteFusionHost?.ready();
  } catch (error) {
    window.RouteFusionHost?.failed(error?.message || String(error));
  }
})();
