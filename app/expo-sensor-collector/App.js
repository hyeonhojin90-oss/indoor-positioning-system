import { useEffect, useMemo, useRef, useState } from "react";
import {
  Alert,
  Platform,
  Pressable,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View
} from "react-native";
import { StatusBar } from "expo-status-bar";
import * as Device from "expo-device";
import { File, Paths } from "expo-file-system";
import * as Location from "expo-location";
import * as Sharing from "expo-sharing";
import {
  Accelerometer,
  Barometer,
  DeviceMotion,
  Gyroscope,
  Magnetometer,
  Pedometer
} from "expo-sensors";
import { CORE_CENTER_X, FLOOR_MAPS, FLOORS, ROUTES, reverseRoute } from "./routes";
import {
  BASELINE_SAMPLE_COUNT,
  createFloorTracker,
  updateFloorTracker
} from "./floorTracking";
import {
  MAP_MAX_X,
  createPositionTracker,
  updatePositionAcceleration,
  updatePositionHeading
} from "./positionTracking";
import {
  classifyCorridorDirection,
  rankStationaryCandidates
} from "./initialPositioning";
import referenceData from "./referenceFingerprints.json";
import navigationData from "../../indoor/web/data/navigation/areas-v1.json";
import * as Fusion from "../../indoor/web/src/positioning/fusion-engine";
import * as Zones from "../../indoor/web/src/positioning/zone-classifier";
import * as Runtime from "../../indoor/web/src/positioning/runtime";
import motionModels from "../../indoor/web/data/positioning/motion-models.json";
import {
  addBleSurveyListener,
  getBleSurveyState,
  isBleSurveyAvailable,
  startBleSurveyScan,
  stopBleSurveyScan
} from "./modules/ble-survey/src";

const SCHEMA_VERSION = 6;
const zoneReferences = Zones.fromLegacy(referenceData);
const FUSION_STATUS = {initialized:"초기 후보 설정",tracking:"추적 중",heading_unavailable:"새 방위 관측 대기",
  unverified_area:"미확인 영역·연결부 이동",recovery_required_wall:"벽 제약 충돌 · 위치 재확인 필요",
  experimental_floor_transition:"상대기압 층 갱신 (실험)",baseline:"기준 기압 수집",stable:"안정",
  within_floor_elevation:"IT홀 같은 층 높이차",unconfirmed_vertical_location:"수직 이동 위치 근거 부족",
  initial_floor_ambiguous:"초기 층 후보 복수",stairs_candidate:"계단 이동 후보",
  elevator_or_pressure_candidate:"엘리베이터/기압 변화 후보",floor_change_candidate_accepted:"층 변화 후보 반영",
  not_observed:"관측 대기",relative_zone_scores:"자기장 구역 상대 점수",no_reference_data:"해당 기기 참조 없음",
  no_usable_features:"사용 가능한 특징 없음",out_of_distribution:"참조 패턴 범위 밖",stale_observation:"오래된 관측 제외"};
const fusionStatusText = value => FUSION_STATUS[value] || value;
const GRAVITY = 9.80665;
const MAGNETIC_ANCHOR_TYPES = [
  "오른쪽 강의실 라인",
  "왼쪽 강의실 라인",
  "왼쪽 계단 앞",
  "왼쪽 계단 내부",
  "오른쪽 계단 앞",
  "오른쪽 계단 내부",
  "코어 교차점"
];
const ZONE_IDS = {"오른쪽 강의실 라인":"main_right","왼쪽 강의실 라인":"main_left",
  "왼쪽 계단 앞":"stairs_left","오른쪽 계단 앞":"stairs_right",
  "왼쪽 계단 내부":"stairs_left_inside","오른쪽 계단 내부":"stairs_right_inside","코어 교차점":"core_junction"};

const SENSOR_DEFINITIONS = [
  ["accelerometer", Accelerometer],
  ["gyroscope", Gyroscope],
  ["magnetometer", Magnetometer],
  ["barometer", Barometer],
  ["deviceMotion", DeviceMotion],
  ["pedometer", Pedometer]
];

function nowNs() {
  return Math.round(performance.now() * 1_000_000);
}

function fileTimestamp(date = new Date()) {
  const pad = (value) => String(value).padStart(2, "0");
  return `${date.getFullYear()}${pad(date.getMonth() + 1)}${pad(date.getDate())}_${pad(date.getHours())}${pad(date.getMinutes())}${pad(date.getSeconds())}`;
}

// Keep a stable comparison key across survey sessions without writing a raw
// CoreBluetooth peripheral identifier or a possibly personal advertised name.
function pseudonymousBleId(value) {
  let hash = 0x811c9dc5;
  const text = `IT_BUILDING_BLE_SURVEY_V1:${String(value || "")}`;
  for (let index = 0; index < text.length; index += 1) {
    hash ^= text.charCodeAt(index);
    hash = Math.imul(hash, 0x01000193);
  }
  return `ble_${(hash >>> 0).toString(16).padStart(8, "0")}`;
}

function SensorBadge({ label, supported }) {
  return (
    <View style={[styles.sensorBadge, supported === true && styles.sensorOk, supported === false && styles.sensorNo]}>
      <Text style={styles.sensorBadgeText}>{label}</Text>
      <Text style={styles.sensorBadgeState}>{supported === null ? "확인 중" : supported ? "지원" : "미지원"}</Text>
    </View>
  );
}

function ActionButton({ title, onPress, disabled, secondary, danger }) {
  return (
    <Pressable
      accessibilityRole="button"
      disabled={disabled}
      onPress={onPress}
      style={({ pressed }) => [
        styles.actionButton,
        secondary && styles.actionSecondary,
        danger && styles.actionDanger,
        disabled && styles.actionDisabled,
        pressed && !disabled && styles.actionPressed
      ]}
    >
      <Text style={[styles.actionText, secondary && styles.actionSecondaryText]}>{title}</Text>
    </Pressable>
  );
}

function floorMap(floor) {
  return FLOOR_MAPS.find((item) => Number(item.floor) === Number(floor));
}

function rightStairEntryX(floor) {
  return floorMap(floor)?.right_stair_entry_map_x ?? 0;
}

function measurableRooms(floor) {
  return (floorMap(floor)?.rooms || []).filter((room) =>
    !room.provisional && Number.isFinite(room.front_x ?? room.x)
  );
}

function startAnchors(floor) {
  const fixed = [
    { id: "CORE", label: "코어복도 출구 중앙점", x: CORE_CENTER_X },
    { id: "RIGHT_STAIRS", label: "오른쪽 계단 입구", x: rightStairEntryX(floor) },
    { id: "LEFT_STAIRS", label: "왼쪽 계단 입구", x: MAP_MAX_X }
  ];
  return [
    ...fixed,
    ...measurableRooms(floor).map((room) => ({
      id: `ROOM_${room.id}`,
      label: `${room.label || room.id} 앞`,
      x: room.front_x ?? room.x
    }))
  ];
}

function landmarkForLocation(floor, location) {
  return startAnchors(floor).find((anchor) => anchor.label === location) || null;
}

function routeStartAnchor(route) {
  if(route.collectionOnly)return null;
  const floor = route.startFloor ?? Number(route.floor);
  return landmarkForLocation(floor, route.start);
}

function routeDirectionSign(route) {
  const forward = route.id?.includes("_TO_LEFT_") ? 1 : -1;
  return route.travelDirection === "reverse" ? -forward : forward;
}

function predictedPlace(snapshot) {
  if (!snapshot) return "측정 시작 전";
  const label=snapshot.landmarks?.[0]?.label;
  return `${snapshot.floor}층 · ${label ? `${label} 근처` : snapshot.zoneLabel || "위치 확인 중"}`;
}

function nearestRooms(floor, x) {
  const roomLandmarks = measurableRooms(floor).map((room) => ({
      id: room.id,
      label: room.label || room.id,
      type: "room",
      side: room.side,
      distance: Math.abs((room.front_x ?? room.x) - x)
    }));
  const connectorLandmarks = [
    { id: "RIGHT_STAIRS", label: "오른쪽 계단 입구", type: "connector", x: rightStairEntryX(floor) },
    { id: "CORE", label: "코어복도 출구 중앙점", type: "connector", x: CORE_CENTER_X },
    { id: "LEFT_STAIRS", label: "왼쪽 계단 입구", type: "connector", x: MAP_MAX_X }
  ].map((landmark) => ({
    ...landmark,
    distance: Math.abs(landmark.x - x)
  }));

  return [...roomLandmarks, ...connectorLandmarks]
    .sort((a, b) => a.distance - b.distance)
    .slice(0, 2);
}

function closestVerticalConnector(x, floor = 4) {
  const connectors = [
    { id: "RIGHT_STAIRS", label: "오른쪽 계단", x: rightStairEntryX(floor) },
    { id: "CORE", label: "코어 엘리베이터·계단", x: CORE_CENTER_X },
    { id: "LEFT_STAIRS", label: "왼쪽 계단", x: MAP_MAX_X }
  ];
  return connectors.sort((a, b) => Math.abs(a.x - x) - Math.abs(b.x - x))[0];
}

export default function App() {
  const [screenMode, setScreenMode] = useState("positioning");
  const [collectionKind, setCollectionKind] = useState("route");
  const [magneticAnchorType, setMagneticAnchorType] = useState("오른쪽 강의실 라인");
  const [magneticAnchorDetail, setMagneticAnchorDetail] = useState("");
  const [freeLaps, setFreeLaps] = useState([]);
  const [selectedFloor, setSelectedFloor] = useState("4");
  const [positionStartFloor, setPositionStartFloor] = useState("4");
  const [positionAnchorId, setPositionAnchorId] = useState("CORE");
  const [groundTruthFloor, setGroundTruthFloor] = useState("4");
  const [groundTruthAnchorId, setGroundTruthAnchorId] = useState("CORE");
  const [positionDirectionSign, setPositionDirectionSign] = useState(-1);
  const [routeIndex, setRouteIndex] = useState(0);
  const [routeReversed, setRouteReversed] = useState(false);
  const [availability, setAvailability] = useState(Object.fromEntries(SENSOR_DEFINITIONS.map(([key]) => [key, null])));
  const [collecting, setCollecting] = useState(false);
  const [sessionReady, setSessionReady] = useState(false);
  const [lapIndex, setLapIndex] = useState(0);
  const [stepCount, setStepCount] = useState(0);
  const [sampleCount, setSampleCount] = useState(0);
  const [livePressure, setLivePressure] = useState(null);
  const [liveMagnetic, setLiveMagnetic] = useState(null);
  const [floorTracking, setFloorTracking] = useState(null);
  const [livePosition, setLivePosition] = useState(null);
  const [fusionPosition, setFusionPosition] = useState(null);
  const [liveHeading, setLiveHeading] = useState(null);
  const [bleState, setBleState] = useState(getBleSurveyState().state);
  const [bleDeviceCount, setBleDeviceCount] = useState(0);
  const [bleStrongest, setBleStrongest] = useState(null);
  const [initialScan, setInitialScan] = useState(null);
  const [initialScanStatus, setInitialScanStatus] = useState("대기");
  const [showPositionCorrection, setShowPositionCorrection] = useState(false);
  const [status, setStatus] = useState("센서 지원 여부를 확인하는 중입니다.");

  const recordsRef = useRef([]);
  const subscriptionsRef = useRef([]);
  const bleSubscriptionsRef = useRef([]);
  const bleDevicesRef = useRef(new Map());
  const bleLastLoggedAtRef = useRef(new Map());
  const bleLastUiUpdateRef = useRef(0);
  const sessionRef = useRef(null);
  const stepsRef = useRef(0);
  // Native pedometer values remain a diagnostic reference. PDR movement uses
  // the accelerometer detector until a repeatable comparison proves otherwise.
  const pedometerSessionRef = useRef(null);
  const pedometerQueryTimerRef = useRef(null);
  const pedometerQueryPendingRef = useRef(false);
  const sampleCountRef = useRef(0);
  const lastUiUpdateRef = useRef(0);
  const lastMagneticUiUpdateRef = useRef(0);
  const floorTrackingRef = useRef(null);
  const livePositionRef = useRef(null);
  const absoluteHeadingRef = useRef(null);
  const fusionRef = useRef(null);
  const freeLapRef = useRef(0);
  const lastFusionPublishRef = useRef(0);
  const anchors = useMemo(() => startAnchors(positionStartFloor), [positionStartFloor]);
  const selectedAnchor = anchors.find((item) => item.id === positionAnchorId) || anchors[0];
  const groundTruthAnchors = useMemo(() => startAnchors(groundTruthFloor), [groundTruthFloor]);
  const selectedGroundTruth = groundTruthAnchors.find((item) => item.id === groundTruthAnchorId) || groundTruthAnchors[0];
  const positioningRoute = useMemo(() => ({
    id: `FREE_${positionStartFloor}_${selectedAnchor.id}`,
    title: "자유 이동 실내측위",
    floor: positionStartFloor,
    start: selectedAnchor.label,
    destination: "자유 이동",
    laps: [],
    mode: "free_positioning",
    startFloor: Number(positionStartFloor),
    destinationFloor: null,
    startX: selectedAnchor.x,
    initialDirectionSign: positionDirectionSign
  }), [positionStartFloor, positionDirectionSign, selectedAnchor]);
  const visibleRoutes = useMemo(() => ROUTES.filter((item) => item.mode !== "floor_tracking" && item.floor === selectedFloor), [selectedFloor]);
  const zoneAnchorRoute = useMemo(() => {
    const detail = magneticAnchorDetail.trim();
    const start = detail ? `${magneticAnchorType} · ${detail}` : magneticAnchorType;
    return {
      id: `F${selectedFloor}_MULTISENSOR_ZONE_ANCHOR`,
      title: "센서 기준점",
      floor: selectedFloor,
      start,
      destination: "다중 센서 구역 지문",
      laps: [],
      mode: "multisensor_zone_anchor",
      zoneId: ZONE_IDS[magneticAnchorType]
    };
  }, [selectedFloor, magneticAnchorType, magneticAnchorDetail]);
  const bleSurveyRoute = useMemo(() => {
    const detail = magneticAnchorDetail.trim();
    const start = detail ? `${magneticAnchorType} · ${detail}` : magneticAnchorType;
    return {
      id: `F${selectedFloor}_BLE_ENVIRONMENT_SURVEY`,
      title: "BLE 환경 조사",
      floor: selectedFloor,
      start,
      destination: "주변 BLE 송신기 관측",
      laps: [],
      mode: "ble_environment_survey",
      zoneId: ZONE_IDS[magneticAnchorType]
    };
  }, [selectedFloor, magneticAnchorType, magneticAnchorDetail]);
  const forwardRoute = visibleRoutes[routeIndex] || visibleRoutes[0];
  const route = screenMode === "positioning"
    ? positioningRoute
    : screenMode === "bleSurvey"
    ? bleSurveyRoute
    : collectionKind === "anchor"
    ? zoneAnchorRoute
    : (routeReversed ? reverseRoute(forwardRoute) : forwardRoute);

  const deviceMetadata = useMemo(() => ({
    platform: Platform.OS,
    collector: isBleSurveyAvailable() ? "ios-development-build" : "expo-go",
    device_id: "IOS_IPHONE13PRO_A",
    device_model: Device.modelName || "unknown",
    device_model_id: Device.modelId || "unknown",
    os_name: Device.osName || "iOS",
    os_version: Device.osVersion || "unknown"
  }), []);

  useEffect(() => {
    let cancelled = false;
    Promise.all(SENSOR_DEFINITIONS.map(async ([key, sensor]) => [key, await sensor.isAvailableAsync()]))
      .then((entries) => {
        if (cancelled) return;
        const result = Object.fromEntries(entries);
        setAvailability(result);
        const unavailable = entries.filter(([, supported]) => !supported).map(([key]) => key);
        setStatus(unavailable.length ? `미지원 센서: ${unavailable.join(", ")}` : "필요한 센서가 모두 지원됩니다. 경로를 확인하고 측정을 시작하세요.");
      })
      .catch((error) => setStatus(`센서 확인 실패: ${error.message}`));
    return () => {
      cancelled = true;
      stopSubscriptions();
    };
  }, []);

  function commonRecord(kind) {
    const wallTime = Date.now();
    return {
      kind,
      wall_time_ms: wallTime,
      sensor_timestamp_ns: nowNs(),
      session_elapsed_ms: sessionRef.current ? wallTime - sessionRef.current.startedAt : 0
    };
  }

  function appendRecord(record) {
    recordsRef.current.push(record);
    if (record.kind === "sample") {
      sampleCountRef.current += 1;
      const now = Date.now();
      if (now - lastUiUpdateRef.current > 300) {
        lastUiUpdateRef.current = now;
        setSampleCount(sampleCountRef.current);
      }
    }
  }

  function appendSample(sensor, values, extra = {}) {
    appendRecord({ ...commonRecord("sample"), sensor, values, ...extra });
  }

  function positionSnapshot(state) {
    if (!state) return null;
    return { ...state, nearest: nearestRooms(state.floor, state.x) };
  }

  function publishFusion() {
    if (!fusionRef.current) return;
    lastFusionPublishRef.current=Date.now();
    const baseline = Runtime.snapshot(fusionRef.current.baseline,FLOOR_MAPS);
    const sequenceOn = Runtime.snapshot(fusionRef.current.sequenceOn,FLOOR_MAPS);
    setFusionPosition({ baseline, sequenceOn });
    appendRecord({...commonRecord("derived_fusion"), ...baseline,
      comparison_variant:"map_constraints_sequence_off", role:"experimental_shadow_not_ground_truth"});
    appendRecord({...commonRecord("derived_fusion"), ...sequenceOn,
      comparison_variant:"map_constraints_sequence_on", role:"experimental_shadow_not_ground_truth"});
  }

  function comparisonAtTruth(snapshot, truth) {
    if (!snapshot) return null;
    return {
      floor: snapshot.floor,
      x: snapshot.x,
      y: snapshot.y,
      zone: snapshot.zone,
      reason: snapshot.reason,
      same_floor: Number(snapshot.floor) === Number(truth.floor),
      x_error_map_units: Number(snapshot.floor) === Number(truth.floor) ? Math.abs(snapshot.x - truth.x) : null
    };
  }

  function recordGroundTruth() {
    const activeRoute = sessionRef.current?.route;
    if (!collecting || !fusionRef.current || !selectedGroundTruth) return;
    const truth = { floor:Number(groundTruthFloor), id:selectedGroundTruth.id, label:selectedGroundTruth.label, x:selectedGroundTruth.x, y:0 };
    const index=++freeLapRef.current;
    appendComparisonLabel(truth, activeRoute, "ground_truth", "user_visible_confirmed", {lap_index:index,lap_total:null});
    setFreeLaps(items=>[...items,{index,floor:truth.floor,label:truth.label}]);
    setStatus(`랩 ${index} 저장 · ${truth.floor}층 ${truth.label} · 측정은 계속됩니다.`);
  }

  function appendComparisonLabel(truth, activeRoute, event, source, lap = {}) {
    const off = fusionRef.current ? Runtime.snapshot(fusionRef.current.baseline,FLOOR_MAPS) : null;
    const on = fusionRef.current ? Runtime.snapshot(fusionRef.current.sequenceOn,FLOOR_MAPS) : null;
    const legacy = livePositionRef.current ? positionSnapshot(livePositionRef.current) : null;
    appendRecord({
      ...commonRecord("label"),
      steps_since_start: stepsRef.current,
      label: { floor:String(truth.floor), location:truth.label, destination:activeRoute.destination, event, route_id:activeRoute.id,
        landmark_id:truth.id, map_x:truth.x, map_y:truth.y, source, ...lap },
      comparison: {
        legacy_pdr: legacy ? {floor:legacy.floor,x:legacy.x,same_floor:Number(legacy.floor)===truth.floor,
          x_error_map_units:Number(legacy.floor)===truth.floor ? Math.abs(legacy.x-truth.x) : null} : null,
        map_constraints_sequence_off: comparisonAtTruth(off,truth),
        map_constraints_sequence_on: comparisonAtTruth(on,truth)
      }
    });
  }

  function forEachFusion(callback) {
    if (!fusionRef.current) return;
    callback(fusionRef.current.baseline);
    callback(fusionRef.current.sequenceOn);
  }

  function stopSubscriptions() {
    if (pedometerQueryTimerRef.current) {
      clearInterval(pedometerQueryTimerRef.current);
      pedometerQueryTimerRef.current = null;
    }
    subscriptionsRef.current.forEach((subscription) => subscription?.remove?.());
    subscriptionsRef.current = [];
    stopBleSurveyScan();
    bleSubscriptionsRef.current.forEach((subscription) => subscription?.remove?.());
    bleSubscriptionsRef.current = [];
  }

  async function startBleEnvironmentSurvey(sessionId) {
    if (!isBleSurveyAvailable()) {
      throw new Error("BLE 환경조사는 Expo Go가 아닌 설치형 iPhone 개발 앱에서만 실행됩니다.");
    }
    bleDevicesRef.current = new Map();
    bleLastLoggedAtRef.current = new Map();
    setBleDeviceCount(0);
    setBleStrongest(null);
    const stateListener = addBleSurveyListener("onBluetoothState", (event) => {
      setBleState(event?.state || "unknown");
    });
    const advertisementListener = addBleSurveyListener("onAdvertisement", (event) => {
      if (sessionRef.current?.id !== sessionId || !event?.peripheralId) return;
      const observedAt = Date.now();
      const pseudonymousId = pseudonymousBleId(event.peripheralId);
      const rssi = Number(event.rssi);
      if (!Number.isFinite(rssi)) return;
      const observation = {
        id: pseudonymousId,
        rssi,
        txPower: Number.isFinite(Number(event.txPower)) ? Number(event.txPower) : null,
        serviceUuids: Array.isArray(event.serviceUUIDs) ? event.serviceUUIDs : [],
        overflowServiceUuids: Array.isArray(event.overflowServiceUUIDs) ? event.overflowServiceUUIDs : [],
        manufacturerDataPresent: Boolean(event.manufacturerDataPresent),
        connectable: typeof event.connectable === "boolean" ? event.connectable : null,
        lastSeenAt: observedAt,
        advertisedName: event.name || ""
      };
      bleDevicesRef.current.set(pseudonymousId, observation);
      const lastLoggedAt = bleLastLoggedAtRef.current.get(pseudonymousId) || 0;
      if (observedAt - lastLoggedAt >= 1000) {
        bleLastLoggedAtRef.current.set(pseudonymousId, observedAt);
        appendSample("ble_advertisement", [rssi], {
          ble: {
            peripheral_id: pseudonymousId,
            tx_power_dbm: observation.txPower,
            service_uuids: observation.serviceUuids,
            overflow_service_uuids: observation.overflowServiceUuids,
            manufacturer_data_present: observation.manufacturerDataPresent,
            connectable: observation.connectable
          }
        });
      }
      if (observedAt - bleLastUiUpdateRef.current >= 500) {
        bleLastUiUpdateRef.current = observedAt;
        const devices = [...bleDevicesRef.current.values()];
        devices.sort((left, right) => right.rssi - left.rssi);
        setBleDeviceCount(devices.length);
        setBleStrongest(devices[0] ? {
          id: devices[0].id,
          rssi: devices[0].rssi,
          advertisedName: devices[0].advertisedName || "이름 없음"
        } : null);
      }
    });
    bleSubscriptionsRef.current = [stateListener, advertisementListener];
    const result = await startBleSurveyScan();
    setBleState(result?.state || "powered_on");
  }

  function startPedometerQueryDiagnostic(startedAt, sessionId) {
    if (Platform.OS !== "ios" || typeof Pedometer.getStepCountAsync !== "function") return;
    const poll = async () => {
      if (pedometerQueryPendingRef.current || sessionRef.current?.id !== sessionId || pedometerSessionRef.current?.endedAt != null) return;
      pedometerQueryPendingRef.current = true;
      const queriedAt = Date.now();
      try {
        const result = await Pedometer.getStepCountAsync(new Date(startedAt), new Date(queriedAt));
        if (sessionRef.current?.id === sessionId && pedometerSessionRef.current?.endedAt == null) {
          const steps = result?.steps ?? null;
          if (pedometerSessionRef.current) pedometerSessionRef.current.liveQuerySteps = steps;
          appendSample("pedometer_query_steps", [steps], {
            query_window_start_ms: startedAt,
            query_window_end_ms: queriedAt
          });
        }
      } catch (error) {
        if (sessionRef.current?.id === sessionId && pedometerSessionRef.current?.endedAt == null) {
          appendRecord({ ...commonRecord("pedometer_query_error"), message: error.message });
        }
      } finally {
        pedometerQueryPendingRef.current = false;
      }
    };
    poll();
    pedometerQueryTimerRef.current = setInterval(poll, 2500);
  }

  async function requestMotionPermission() {
    const requests = [];
    if (DeviceMotion.requestPermissionsAsync) requests.push(DeviceMotion.requestPermissionsAsync());
    if (Pedometer.requestPermissionsAsync) requests.push(Pedometer.requestPermissionsAsync());
    const results = await Promise.all(requests);
    return results.every((result) => result?.granted !== false);
  }

  function trackingRouteFromNode(node, source) {
    const direction = classifyCorridorDirection(absoluteHeadingRef.current?.heading);
    return {
      id: `AUTO_${node.floor}F_${node.node_id || node.id}`,
      title: "내부 자동 추정 후 자유 이동",
      floor: String(node.floor),
      start: node.label,
      destination: "자유 이동",
      laps: [],
      mode: "free_positioning",
      startFloor: Number(node.floor),
      destinationFloor: null,
      startX: node.map_x ?? node.x,
      initialDirectionSign: direction.sign,
      initializationSource: source,
      initializationResult: initialScan
    };
  }

  async function scanIndoorPosition() {
    if (collecting || initialScanStatus === "측정 중") return;
    setInitialScan(null);
    setShowPositionCorrection(false);
    setInitialScanStatus("측정 중");
    setStatus("현재 자리에서 휴대폰을 평소처럼 들고 5초간 멈춰 계세요.");
    const magneticValues = [];
    const pressureValues = [];
    const temporary = [];
    try {
      Magnetometer.setUpdateInterval(100);
      Barometer.setUpdateInterval(250);
      if (availability.magnetometer) {
        temporary.push(Magnetometer.addListener(({ x, y, z }) => magneticValues.push(Math.hypot(x, y, z))));
      }
      if (availability.barometer) {
        temporary.push(Barometer.addListener(({ pressure }) => pressureValues.push(pressure)));
      }
      const permission = await Location.requestForegroundPermissionsAsync();
      if (permission.granted) {
        temporary.push(await Location.watchHeadingAsync(({ magHeading, accuracy }) => {
          absoluteHeadingRef.current = { heading: magHeading, accuracy };
          setLiveHeading({ heading: magHeading, accuracy });
        }));
      }
      await new Promise((resolve) => setTimeout(resolve, 5000));
      temporary.forEach((subscription) => subscription?.remove?.());
      const result = rankStationaryCandidates({
        platform: Platform.OS,
        magneticValues,
        pressureValues,
        references: referenceData.fingerprints,
        transferModels: referenceData.transfer_models
      });
      const scan = {
        ...result,
        heading: absoluteHeadingRef.current,
        magneticSampleCount: magneticValues.length,
        pressureSampleCount: pressureValues.length,
        platformCoverage: referenceData.coverage[Platform.OS] || []
      };
      setInitialScan(scan);
      setInitialScanStatus(result.candidates.length ? "후보 생성 완료" : "후보 없음");
      setStatus(result.candidates.length
        ? `내부 위치 후보를 만들었습니다. 현재 정지 지문 단독 검증 정확도가 낮으므로 실제 위치와 반드시 비교하세요.`
        : `현재 기기의 참조 지문이 없거나 자기장 샘플이 부족합니다. 실제 위치를 선택해 추적을 시작하세요.`);
    } catch (error) {
      temporary.forEach((subscription) => subscription?.remove?.());
      setInitialScanStatus("실패");
      setStatus(`내부 위치 분석 실패: ${error.message}`);
    }
  }

  function confirmInitialCandidate() {
    const candidate = initialScan?.candidates?.[0];
    if (!candidate) return;
    startCollection(trackingRouteFromNode(candidate, "stationary_candidate_confirmed"));
  }

  function startFromCorrectedPosition() {
    startCollection(trackingRouteFromNode({
      floor: Number(positionStartFloor),
      node_id: selectedAnchor.id,
      label: selectedAnchor.label,
      map_x: selectedAnchor.x
    }, "user_corrected"));
  }

  async function subscribeSensors() {
    Accelerometer.setUpdateInterval(50);
    Gyroscope.setUpdateInterval(50);
    Magnetometer.setUpdateInterval(100);
    Barometer.setUpdateInterval(250);
    DeviceMotion.setUpdateInterval(50);

    try {
      const permission = await Location.requestForegroundPermissionsAsync();
      if (permission.granted) {
        subscriptionsRef.current.push(await Location.watchHeadingAsync(({ magHeading, accuracy }) => {
          absoluteHeadingRef.current = { heading: magHeading, accuracy };
          appendSample("heading_degrees", [magHeading], {accuracy});
          forEachFusion((runtime) => Runtime.heading(runtime,Date.now(),magHeading,accuracy));
          setLiveHeading({ heading: magHeading, accuracy });
          if (livePositionRef.current) {
            const direction = classifyCorridorDirection(magHeading);
            livePositionRef.current = { ...livePositionRef.current, currentDirectionSign: direction.sign };
          }
        }));
      }
    } catch (error) {
      appendRecord({ ...commonRecord("heading_unavailable"), message: error.message });
    }

    if (availability.accelerometer) {
      subscriptionsRef.current.push(Accelerometer.addListener(({ x, y, z }) => {
        const values = [x * GRAVITY, y * GRAVITY, z * GRAVITY];
        appendSample("accelerometer_mps2", values, { source_unit: "g", converted_unit: "m/s2" });
        if (livePositionRef.current) {
          const result = updatePositionAcceleration(livePositionRef.current, Date.now(), values);
          livePositionRef.current = result.state;
          if (result.detected) {
            if (fusionRef.current) {
              forEachFusion((runtime) => Runtime.step(runtime,Date.now(),result.peak));
              publishFusion();
            }
            const snapshot = positionSnapshot(result.state);
            setLivePosition(snapshot);
            appendRecord({
              ...commonRecord("derived_position"),
              floor: snapshot.floor,
              map_x: snapshot.x,
              detected_steps: snapshot.detectedSteps,
              direction_sign: snapshot.currentDirectionSign,
              acceleration_peak_mps2: result.peak,
              nearest_rooms: snapshot.nearest
            });
          }
        }
      }));
    }
    if (availability.gyroscope) {
      subscriptionsRef.current.push(Gyroscope.addListener(({ x, y, z }) => appendSample("gyroscope_rads", [x, y, z])));
    }
    if (availability.magnetometer) {
      subscriptionsRef.current.push(Magnetometer.addListener(({ x, y, z }) => {
        appendSample("magnetic_field_ut", [x, y, z]);
        const total = Math.hypot(x, y, z);
        const now = Date.now();
        if (fusionRef.current) {
          forEachFusion((runtime) => Runtime.magnetic(runtime,now,[x,y,z]));
          if(now-lastFusionPublishRef.current>1000)publishFusion();
        }
        if (now - lastMagneticUiUpdateRef.current > 250) {
          lastMagneticUiUpdateRef.current = now;
          setLiveMagnetic(total);
        }
      }));
    }
    if (availability.barometer) {
      subscriptionsRef.current.push(Barometer.addListener(({ pressure, relativeAltitude }) => {
        if (fusionRef.current) {
          forEachFusion((runtime) => Runtime.pressure(runtime,Date.now(),pressure));
          if (Date.now()-lastFusionPublishRef.current>1000) publishFusion();
        }
        let trackerSnapshot = null;
        if (floorTrackingRef.current) {
          const previousFloor = floorTrackingRef.current.confirmedFloor;
          floorTrackingRef.current = updateFloorTracker(floorTrackingRef.current, pressure);
          trackerSnapshot = floorTrackingRef.current;
          setFloorTracking({ ...trackerSnapshot });
          if (trackerSnapshot.baselinePressure === null) {
            setStatus(`${trackerSnapshot.startFloor}층 기준 기압 수집 중 · ${trackerSnapshot.baselineProgress}/${BASELINE_SAMPLE_COUNT} · 완료될 때까지 움직이지 마세요.`);
          } else if (trackerSnapshot.changed) {
            let connector = null;
            if (livePositionRef.current) {
              connector = closestVerticalConnector(livePositionRef.current.x, livePositionRef.current.floor);
              livePositionRef.current = {
                ...livePositionRef.current,
                floor: trackerSnapshot.confirmedFloor,
                x: connector.x
              };
              setLivePosition(positionSnapshot(livePositionRef.current));
            }
            appendRecord({
              ...commonRecord("floor_transition"),
              from_floor: previousFloor,
              to_floor: trackerSnapshot.confirmedFloor,
              candidate_floor: trackerSnapshot.candidateFloor,
              pressure_hpa: pressure,
              pressure_delta_hpa: trackerSnapshot.pressureDelta,
              connector: connector
            });
            if (trackerSnapshot.destinationFloor != null && trackerSnapshot.confirmedFloor === trackerSnapshot.destinationFloor) {
              setStatus(`${trackerSnapshot.destinationFloor}층 추정 완료 · 실제 도착 랩을 기록하세요.`);
            } else {
              setStatus(`${trackerSnapshot.confirmedFloor}층으로 갱신 · ${connector?.label || "연결부"} 기준으로 위치를 이어갑니다.`);
            }
          } else if (trackerSnapshot.baselineProgress >= BASELINE_SAMPLE_COUNT && previousFloor === trackerSnapshot.confirmedFloor) {
            setStatus(trackerSnapshot.destinationFloor != null && trackerSnapshot.confirmedFloor === trackerSnapshot.destinationFloor
              ? `${trackerSnapshot.destinationFloor}층 추정 완료 · 실제 도착 후 도착 기록을 누르세요.`
              : `기준 완료 · 현재 확정 ${trackerSnapshot.confirmedFloor}층, 후보 ${trackerSnapshot.candidateFloor}층`);
          }
        }
        appendSample("pressure_hpa", [pressure], {
          relative_altitude_m: relativeAltitude ?? null,
          floor_tracking: trackerSnapshot ? {
            baseline_pressure_hpa: trackerSnapshot.baselinePressure,
            smoothed_pressure_hpa: trackerSnapshot.smoothedPressure,
            pressure_delta_hpa: trackerSnapshot.pressureDelta,
            raw_floor: trackerSnapshot.rawFloor,
            candidate_floor: trackerSnapshot.candidateFloor,
            confirmed_floor: trackerSnapshot.confirmedFloor,
            candidate_streak: trackerSnapshot.candidateStreak
          } : null
        });
        setLivePressure(pressure);
      }));
    }
    if (availability.deviceMotion) {
      subscriptionsRef.current.push(DeviceMotion.addListener((measurement) => {
        const rotation = measurement.rotation || {};
        const rotationRate = measurement.rotationRate || {};
        if (livePositionRef.current && rotation.alpha != null && !absoluteHeadingRef.current) {
          livePositionRef.current = updatePositionHeading(livePositionRef.current, rotation.alpha);
        }
        appendSample("device_motion_rotation_rads", [rotation.alpha ?? null, rotation.beta ?? null, rotation.gamma ?? null], {
          rotation_rate: [rotationRate.alpha ?? null, rotationRate.beta ?? null, rotationRate.gamma ?? null],
          orientation: measurement.orientation ?? null
        });
      }));
    }
    if (availability.pedometer) {
      subscriptionsRef.current.push(Pedometer.watchStepCount(({ steps }) => {
        stepsRef.current = steps;
        if (pedometerSessionRef.current) pedometerSessionRef.current.watchSteps = steps;
        setStepCount(steps);
        appendSample("step_counter", [steps]);
      }));
    }
  }

  async function startCollection(routeOverride = null) {
    if (collecting) return;
    const selectedRoute = routeOverride?.mode ? routeOverride : route;
    try {
      const granted = await requestMotionPermission();
      if (!granted) {
        setStatus("동작 및 피트니스 권한이 필요합니다.");
        return;
      }
      const startedAt = Date.now();
      const sessionId = `ios_${fileTimestamp(new Date(startedAt))}`;
      sessionRef.current = { id: sessionId, startedAt, route: selectedRoute };
      pedometerSessionRef.current = {
        startedAt,
        endedAt: null,
        watchSteps: null,
        liveQuerySteps: null,
        querySteps: null,
        queryError: null
      };
      recordsRef.current = [];
      sampleCountRef.current = 0;
      stepsRef.current = 0;
      setSampleCount(0);
      setStepCount(0);
      setLapIndex(0);
      freeLapRef.current=0;
      setFreeLaps([]);
      setSessionReady(false);
      const startAnchor = selectedRoute.mode === "free_positioning"
        ? {id:selectedRoute.id,label:selectedRoute.start,x:selectedRoute.startX}
        : selectedRoute.mode === "ble_environment_survey" ? null : routeStartAnchor(selectedRoute);
      const comparisonStart = startAnchor ? {
        floor:selectedRoute.startFloor ?? Number(selectedRoute.floor),
        x:startAnchor.x,
        direction:selectedRoute.initialDirectionSign ?? routeDirectionSign(selectedRoute)
      } : null;
      fusionRef.current=comparisonStart ? {
        baseline: Runtime.create(navigationData,motionModels,zoneReferences,{
          floor:comparisonStart.floor,x:comparisonStart.x,y:0,platform:Platform.OS,device:Device.modelName,
          initialDirectionSign:comparisonStart.direction,sequenceEnabled:false
        }),
        sequenceOn: Runtime.create(navigationData,motionModels,zoneReferences,{
          floor:comparisonStart.floor,x:comparisonStart.x,y:0,platform:Platform.OS,device:Device.modelName,
          initialDirectionSign:comparisonStart.direction,sequenceEnabled:true
        })
      } : null;
      setFusionPosition(fusionRef.current ? {
        baseline:Runtime.snapshot(fusionRef.current.baseline,FLOOR_MAPS),
        sequenceOn:Runtime.snapshot(fusionRef.current.sequenceOn,FLOOR_MAPS)
      } : null);
      if (comparisonStart) {
        setGroundTruthFloor(String(comparisonStart.floor));
        setGroundTruthAnchorId("CORE");
      }
      // Await a new heading from this session, never reuse a stale scan heading.
      absoluteHeadingRef.current=null;
      if (selectedRoute.mode === "floor_tracking" || selectedRoute.mode === "free_positioning") {
        floorTrackingRef.current = createFloorTracker(selectedRoute.startFloor, selectedRoute.destinationFloor);
        setFloorTracking({ ...floorTrackingRef.current });
      } else {
        floorTrackingRef.current = null;
        setFloorTracking(null);
      }
      if (comparisonStart) {
        livePositionRef.current = createPositionTracker({
          floor: comparisonStart.floor,
          x: comparisonStart.x,
          initialDirectionSign: comparisonStart.direction
        });
        setLivePosition(positionSnapshot(livePositionRef.current));
      } else {
        livePositionRef.current = null;
        setLivePosition(null);
      }
      appendRecord({
        ...commonRecord("session_start"),
        schema_version: SCHEMA_VERSION,
        session_id: sessionId,
        ...deviceMetadata,
        sensor_availability: availability,
        sampling_interval_ms: { accelerometer: 50, gyroscope: 50, magnetometer: 100, barometer: 250, device_motion: 50 },
        label: {
          floor: selectedRoute.floor,
          location: selectedRoute.start,
          destination: selectedRoute.destination,
          event: "시작",
          route_id: selectedRoute.id,
          zone_id: selectedRoute.zoneId || null,
          lap_total: selectedRoute.laps.length
        },
        experiment_mode: selectedRoute.mode || "route_collection",
        route_direction: selectedRoute.travelDirection || "forward",
        source_route_id: selectedRoute.sourceRouteId || selectedRoute.id,
        start_floor: selectedRoute.startFloor ?? Number(selectedRoute.floor),
        destination_floor: selectedRoute.destinationFloor ?? (selectedRoute.mode === "free_positioning" ? null : Number(selectedRoute.floor)),
        positioning_config: comparisonStart ? {
          start_map_x: comparisonStart.x,
          initial_direction_sign: comparisonStart.direction,
          initialization_source: selectedRoute.initializationSource || "manual_control",
          initialization_result: selectedRoute.initializationResult || null,
          map_axis: "x=0 right stairs, x=135.407 left stairs",
          horizontal_model: "main_corridor_1d",
          comparison_engine: Fusion.VERSION,
          comparison_variants: ["legacy_pdr", "map_constraints_sequence_off", "map_constraints_sequence_on"],
          navigation_version: navigationData.version,
          comparison_role: "experimental_shadow_not_ground_truth",
          comparison_start_map_y: 0,
          comparison_enabled_for_known_route: selectedRoute.mode !== "free_positioning"
        } : null,
        sensor_scope: ["multisensor_zone_anchor", "ble_environment_survey"].includes(selectedRoute.mode) ? [
          "accelerometer_mps2",
          "gyroscope_radps",
          "magnetic_field_ut",
          "pressure_hpa",
          "device_motion_rotation_rads",
          "step_counter"
        ] : null,
        radio_observation: selectedRoute.mode === "ble_environment_survey" ? {
          nearby_wifi_scan_supported: false,
          nearby_ble_scan_supported: isBleSurveyAvailable(),
          radio_source: "iOS CoreBluetooth nearby BLE advertisements",
          identifier_storage: "pseudonymous_ble_id_only",
          advertised_name_storage: "not_written_to_jsonl"
        } : selectedRoute.mode === "multisensor_zone_anchor" ? {
          nearby_wifi_scan_supported: false,
          reason: "iOS does not expose general nearby AP BSSID/RSSI scan results",
          android_pairing_required: true
        } : null
      });
      if (selectedRoute.initializationSource === "stationary_candidate_confirmed") {
        appendRecord({
          ...commonRecord("user_confirmed"),
          predicted_candidate: selectedRoute.initializationResult?.candidates?.[0] || null,
          selected_position: {
            floor: selectedRoute.startFloor,
            node_id: selectedRoute.id.replace(/^AUTO_\d+F_/, ""),
            label: selectedRoute.start,
            map_x: selectedRoute.startX
          }
        });
      } else if (selectedRoute.initializationSource === "user_corrected") {
        appendRecord({
          ...commonRecord("user_corrected"),
          predicted_candidate: selectedRoute.initializationResult?.candidates?.[0] || null,
          selected_position: {
            floor: selectedRoute.startFloor,
            node_id: selectedRoute.id.replace(/^AUTO_\d+F_/, ""),
            label: selectedRoute.start,
            map_x: selectedRoute.startX
          }
        });
      }
      await subscribeSensors();
      startPedometerQueryDiagnostic(startedAt, sessionId);
      if (selectedRoute.mode === "ble_environment_survey") {
        await startBleEnvironmentSurvey(sessionId);
      }
      setCollecting(true);
      setStatus(selectedRoute.mode === "free_positioning"
        ? `${selectedRoute.startFloor}층 ${selectedRoute.start}에서 자유 추적 시작 · 기준 기압 ${BASELINE_SAMPLE_COUNT}개가 모일 때까지 잠시 멈춰 계세요.`
        : selectedRoute.mode === "floor_tracking"
        ? `${selectedRoute.startFloor}층 기준 기압 수집 준비 · ${BASELINE_SAMPLE_COUNT}개가 모일 때까지 움직이지 마세요.`
        : selectedRoute.mode === "multisensor_zone_anchor"
        ? `${selectedRoute.floor}층 ${selectedRoute.start} 센서 기준점 측정 중 · 같은 위치와 자세로 10~20초 유지하세요.`
        : selectedRoute.mode === "ble_environment_survey"
        ? `${selectedRoute.floor}층 ${selectedRoute.start} BLE 환경 조사 중 · 같은 위치에서 30초 이상 유지하세요.`
        : `측정 중 · 다음 랩: ${selectedRoute.laps[0]}`);
    } catch (error) {
      stopSubscriptions();
      fusionRef.current=null;
      setStatus(`측정 시작 실패: ${error.message}`);
    }
  }

  function recordLap() {
    if (!collecting || lapIndex >= route.laps.length) return;
    const location = route.laps[lapIndex];
    const isArrival = lapIndex === route.laps.length - 1;
    const landmark = landmarkForLocation(route.floor, location);
    if (landmark && fusionRef.current) {
      appendComparisonLabel({floor:Number(route.floor),id:landmark.id,label:landmark.label,x:landmark.x,y:0}, route,
        isArrival ? "도착" : "랜드마크", "guided_route_lap", {lap_index:lapIndex+1,lap_total:route.laps.length});
    } else appendRecord({
      ...commonRecord("label"),
      steps_since_start: stepsRef.current,
      label: {
        floor: route.floor,
        location,
        destination: route.destination,
        event: isArrival ? "도착" : "랜드마크",
        route_id: route.id,
        lap_index: lapIndex + 1,
        lap_total: route.laps.length
      }
    });
    const next = lapIndex + 1;
    setLapIndex(next);
    setStatus(isArrival ? "도착 랩을 기록했습니다. 측정 종료를 눌러 파일을 확정하세요." : `랩 기록 완료 · 다음: ${route.laps[next]}`);
  }

  async function stopCollection() {
    if (!collecting) return;
    const activeRoute = sessionRef.current?.route || route;
    const endedAt = Date.now();
    if (pedometerSessionRef.current) pedometerSessionRef.current.endedAt = endedAt;
    const pedometerAudit = {
      watch_steps: pedometerSessionRef.current?.watchSteps ?? stepsRef.current,
      live_query_steps: pedometerSessionRef.current?.liveQuerySteps ?? null,
      query_steps: null,
      query_window_start_ms: sessionRef.current?.startedAt ?? null,
      query_window_end_ms: endedAt,
      query_error: null,
      query_supported: Platform.OS === "ios" && typeof Pedometer.getStepCountAsync === "function"
    };
    stopSubscriptions();
    // iOS Core Motion can return a count for this exact session window. This
    // avoids treating the delayed first watch callback as a session baseline.
    if (pedometerAudit.query_supported && pedometerAudit.query_window_start_ms != null) {
      try {
        const result = await Pedometer.getStepCountAsync(
          new Date(pedometerAudit.query_window_start_ms),
          new Date(pedometerAudit.query_window_end_ms)
        );
        pedometerAudit.query_steps = result?.steps ?? null;
      } catch (error) {
        pedometerAudit.query_error = error.message;
      }
    }
    if (pedometerSessionRef.current) {
      pedometerSessionRef.current = { ...pedometerSessionRef.current, ...pedometerAudit };
    }
    appendRecord({
      ...commonRecord("session_end"),
      session_id: sessionRef.current?.id,
      steps_since_start: stepsRef.current,
      pedometer_audit: pedometerAudit,
      sample_count: sampleCountRef.current,
      final_fusion: fusionRef.current ? Runtime.snapshot(fusionRef.current.baseline,FLOOR_MAPS) : null,
      final_fusion_sequence_on: fusionRef.current ? Runtime.snapshot(fusionRef.current.sequenceOn,FLOOR_MAPS) : null,
      completed_laps: activeRoute.mode === "free_positioning" ? freeLapRef.current : lapIndex,
      expected_laps: activeRoute.mode === "free_positioning" ? null : activeRoute.laps.length,
      completed: lapIndex === activeRoute.laps.length,
      final_position: livePositionRef.current ? {
        floor: livePositionRef.current.floor,
        map_x: livePositionRef.current.x,
        detected_steps: livePositionRef.current.detectedSteps,
        nearest_rooms: nearestRooms(livePositionRef.current.floor, livePositionRef.current.x)
      } : null
    });
    setCollecting(false);
    setSessionReady(true);
    setSampleCount(sampleCountRef.current);
    setStatus(activeRoute.mode === "free_positioning"
      ? `위치 추적 종료 · ${sampleCountRef.current.toLocaleString()}개 샘플 · 마지막 추정 ${livePositionRef.current?.floor ?? "-"}층`
      : activeRoute.mode === "ble_environment_survey"
      ? `BLE 환경 조사 종료 · ${bleDevicesRef.current.size}개 송신기 · ${sampleCountRef.current.toLocaleString()}개 샘플`
      : activeRoute.mode === "multisensor_zone_anchor"
      ? `센서 기준점 측정 종료 · ${sampleCountRef.current.toLocaleString()}개 샘플 · AP 지문은 Android 자료와 결합하세요.`
      : `측정 종료 · ${sampleCountRef.current.toLocaleString()}개 샘플 · ${lapIndex}/${activeRoute.laps.length}랩`);
  }

  async function shareSession() {
    if (!sessionReady || !recordsRef.current.length) return;
    try {
      const filename = `indoor_positioning_${sessionRef.current?.id || fileTimestamp()}.jsonl`;
      const file = new File(Paths.cache, filename);
      if (file.exists) file.delete();
      file.create();
      file.write(`${recordsRef.current.map((record) => JSON.stringify(record)).join("\n")}\n`);
      if (!(await Sharing.isAvailableAsync())) {
        Alert.alert("파일 생성 완료", file.uri);
        return;
      }
      await Sharing.shareAsync(file.uri, {
        mimeType: "application/x-ndjson",
        dialogTitle: "iOS 실내측위 JSONL 저장"
      });
    } catch (error) {
      setStatus(`파일 공유 실패: ${error.message}`);
    }
  }

  const nextLap = route.laps[lapIndex];
  const corridorPercent = livePosition ? (1 - livePosition.x / MAP_MAX_X) * 100 : 50;
  const predictionSummary = (
    <View>
      <Text style={styles.cardTitle}>현재 예상 위치</Text>
      {collecting && fusionPosition ? <>
        <Text style={styles.predictionPrimary}>예상 층 · 기존 {livePosition?.floor ?? "-"}층 / OFF {fusionPosition.baseline.floor}층 / ON {fusionPosition.sequenceOn.floor}층</Text>
        <Text style={styles.routeMeta}>기존 PDR: {livePosition?.floor}층 · {livePosition?.nearest?.[0]?.label || "위치 확인 중"} 근처</Text>
        <Text style={styles.routeMeta}>패턴 OFF: {predictedPlace(fusionPosition.baseline)}</Text>
        <Text style={styles.routeMeta}>패턴 ON: {predictedPlace(fusionPosition.sequenceOn)}</Text>
        <Text style={styles.routeMeta}>자기장 패턴 보정 {fusionPosition.sequenceOn.sequenceStats?.applied ?? 0}회 / 비교 {fusionPosition.sequenceOn.sequenceStats?.evaluated ?? 0}회 · 두 버전 모두 자기장 구역 관측 사용</Text>
      </> : <Text style={styles.routeMeta}>{collecting ? "시작 좌표 미연결 · 예측 불가 (센서·랩은 저장됩니다)" : "측정 시작 후 세 방식의 예상 위치가 표시됩니다."}</Text>}
    </View>
  );

  return (
    <SafeAreaView style={styles.safeArea}>
      <StatusBar style="dark" />
      <ScrollView contentContainerStyle={styles.container}>
        <Text style={styles.eyebrow}>iOS 연구 데이터 · schema {SCHEMA_VERSION}</Text>
        <Text style={styles.title}>실내측위 센서 수집기</Text>
        <Text style={styles.subtitle}>{deviceMetadata.device_model} · {deviceMetadata.os_name} {deviceMetadata.os_version}</Text>

        <View style={styles.modeTabs}>
          <Pressable
            disabled={collecting}
            onPress={() => { setScreenMode("positioning"); setRouteIndex(0); setLapIndex(0); }}
            style={[styles.modeTab, screenMode === "positioning" && styles.modeTabSelected]}
          >
            <Text style={[styles.modeTabText, screenMode === "positioning" && styles.modeTabTextSelected]}>자유 이동 비교</Text>
          </Pressable>
          <Pressable
            disabled={collecting}
            onPress={() => { setScreenMode("collection"); setRouteIndex(0); setLapIndex(0); }}
            style={[styles.modeTab, screenMode === "collection" && styles.modeTabSelected]}
          >
            <Text style={[styles.modeTabText, screenMode === "collection" && styles.modeTabTextSelected]}>경로 라벨 비교</Text>
          </Pressable>
          <Pressable
            disabled={collecting}
            onPress={() => { setScreenMode("bleSurvey"); setLapIndex(0); }}
            style={[styles.modeTab, screenMode === "bleSurvey" && styles.modeTabSelected]}
          >
            <Text style={[styles.modeTabText, screenMode === "bleSurvey" && styles.modeTabTextSelected]}>BLE 환경 조사</Text>
          </Pressable>
        </View>

        <View style={styles.modeDescription}>
          <Text style={styles.modeDescriptionText}>{screenMode === "positioning"
            ? "내부 자동 추정은 현재 자리에서 5초간 정지 센서를 분석합니다. 예상 위치가 맞으면 그 노드에서 자유 추적을 시작하고, 틀리면 실제 위치를 선택해 비교 로그를 남깁니다."
            : screenMode === "bleSurvey"
            ? "설치형 iPhone 앱에서 주변 BLE 송신기의 RSSI를 같은 위치에서 수집합니다. 앱은 원시 식별자·광고 이름을 JSONL에 저장하지 않으며, AP 스캔을 대신하는 기능도 아닙니다."
            : collectionKind === "route"
            ? "알려진 경로를 걸으며 각 강의실 랩을 실제 위치로 기록합니다. 기존 PDR·새 엔진 OFF·ON 예측도 동시에 표시·저장됩니다."
            : "정지한 위치의 센서 기준점을 수집합니다. 이동 경로 비교와는 목적이 다릅니다."}</Text>
        </View>

        {screenMode === "positioning" && (
          <View style={styles.card}>
            {predictionSummary}
          </View>
        )}

        <View style={styles.card}>
          <Text style={styles.cardTitle}>센서 지원</Text>
          <View style={styles.sensorGrid}>
            <SensorBadge label="가속도" supported={availability.accelerometer} />
            <SensorBadge label="자이로" supported={availability.gyroscope} />
            <SensorBadge label="자기장" supported={availability.magnetometer} />
            <SensorBadge label="기압계" supported={availability.barometer} />
            <SensorBadge label="모션" supported={availability.deviceMotion} />
            <SensorBadge label="걸음" supported={availability.pedometer} />
            <SensorBadge label="BLE" supported={isBleSurveyAvailable() && bleState !== "unsupported"} />
          </View>
        </View>

        <View style={styles.card}>
          <Text style={styles.cardTitle}>{screenMode === "positioning" ? "자유 위치 추적·실제 위치 라벨" : screenMode === "bleSurvey" ? "BLE 환경 조사 위치" : "보정 수집 경로"}</Text>
          {screenMode === "positioning" ? (
            <>
              <Text style={styles.sectionLabel}>현재 위치 예상 확인 후 자유 이동</Text>
              {(
                <>
                  <Text style={styles.routeMeta}>참조 범위: iPhone 직접 4층 오른쪽 + Galaxy 변환 1~5층</Text>
                  <Text style={styles.routeMeta}>전 층 독립 검증: 층 86.1% · 정확한 노드 25.0% · 상위 3개 38.9%</Text>
                  <ActionButton title={initialScanStatus === "측정 중" ? "5초간 분석 중..." : "현재 위치 5초 분석"} onPress={scanIndoorPosition} disabled={collecting || initialScanStatus === "측정 중" || !availability.magnetometer} />
                  {initialScan?.candidates?.length > 0 && (
                    <View style={styles.predictionBox}>
                      <Text style={styles.nearestTitle}>여기로 예상됩니다</Text>
                      <Text style={styles.predictionPrimary}>{initialScan.candidates[0].floor}층 · {initialScan.candidates[0].label} 앞쪽</Text>
                      <Text style={styles.nearestSecondary}>판정 신뢰도: {initialScan.confidence === "medium" ? "보통" : "낮음"} · 자기장 차이 {initialScan.candidates[0].magneticDifferenceUt.toFixed(1)} μT</Text>
                      <Text style={styles.nearestSecondary}>측정 방위: {liveHeading ? `${liveHeading.heading.toFixed(0)}° · ${classifyCorridorDirection(liveHeading.heading).label}` : "권한 또는 측정값 없음"}</Text>
                      <Text style={styles.sectionLabel}>다른 후보</Text>
                      {initialScan.candidates.slice(1).map((candidate, index) => (
                        <Text key={`${candidate.floor}-${candidate.node_id}`} style={styles.nearestSecondary}>{index + 2}. {candidate.floor}층 {candidate.label}{candidate.transferred_from ? " · Galaxy 변환" : ""} · Δ{candidate.magneticDifferenceUt.toFixed(1)} μT</Text>
                      ))}
                      <ActionButton title="맞아요 · 여기서 추적 시작" onPress={confirmInitialCandidate} disabled={collecting} />
                      <ActionButton title="아니에요 · 현재 위치 선택" onPress={() => setShowPositionCorrection(true)} disabled={collecting} secondary />
                    </View>
                  )}
                  {(showPositionCorrection || initialScanStatus === "후보 없음") && (
                    <View style={styles.correctionBox}>
                      <Text style={styles.sectionLabel}>실제 현재 층</Text>
                      <View style={styles.floorGrid}>
                        {FLOORS.map((floor) => (
                          <Pressable key={floor} disabled={collecting} onPress={() => { setPositionStartFloor(floor); setPositionAnchorId("CORE"); }} style={[styles.floorOption, positionStartFloor === floor && styles.floorSelected]}>
                            <Text style={[styles.floorText, positionStartFloor === floor && styles.floorSelectedText]}>{floor}층</Text>
                          </Pressable>
                        ))}
                      </View>
                      <Text style={styles.sectionLabel}>실제 강의실·시설</Text>
                      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.anchorScroller}>
                        {anchors.map((anchor) => (
                          <Pressable key={anchor.id} disabled={collecting} onPress={() => setPositionAnchorId(anchor.id)} style={[styles.anchorOption, selectedAnchor.id === anchor.id && styles.routeSelected]}>
                            <Text style={[styles.anchorText, selectedAnchor.id === anchor.id && styles.routeSelectedText]}>{anchor.label}</Text>
                          </Pressable>
                        ))}
                      </ScrollView>
                      <ActionButton title="선택한 실제 위치에서 추적 시작" onPress={startFromCorrectedPosition} disabled={collecting} />
                    </View>
                  )}
                </>
              )}
            </>
          ) : screenMode === "bleSurvey" ? (
            <>
              <Text style={styles.sectionLabel}>층 선택</Text>
              <View style={styles.floorGrid}>
                {FLOORS.map((floor) => (
                  <Pressable
                    key={floor}
                    disabled={collecting}
                    onPress={() => { setSelectedFloor(floor); setLapIndex(0); }}
                    style={[styles.floorOption, selectedFloor === floor && styles.floorSelected]}
                  >
                    <Text style={[styles.floorText, selectedFloor === floor && styles.floorSelectedText]}>{floor}층</Text>
                  </Pressable>
                ))}
              </View>
              <Text style={styles.sectionLabel}>구역 라벨</Text>
              {MAGNETIC_ANCHOR_TYPES.map((type) => (
                <Pressable key={type} disabled={collecting} onPress={() => setMagneticAnchorType(type)} style={[styles.routeOption, magneticAnchorType === type && styles.routeSelected]}>
                  <Text style={[styles.routeText, magneticAnchorType === type && styles.routeSelectedText]}>{type}</Text>
                </Pressable>
              ))}
              <Text style={styles.sectionLabel}>세부 위치 메모 (선택)</Text>
              <TextInput
                editable={!collecting}
                value={magneticAnchorDetail}
                onChangeText={setMagneticAnchorDetail}
                placeholder="예: 4층 코어 중앙 · 메인계단 입구 앞"
                style={styles.textInput}
              />
              <View style={styles.warningBox}>
                <Text style={styles.warningText}>{isBleSurveyAvailable()
                  ? "BLE 송신기별 RSSI를 1초 단위로 저장합니다. 같은 지점에서 30초 이상, 휴대폰 자세를 크게 바꾸지 말고 측정하세요."
                  : "이 화면은 Expo Go에서는 스캔할 수 없습니다. 아래 전용 iPhone 개발 앱을 설치한 뒤 사용하세요."}</Text>
              </View>
            </>
          ) : (
            <>
              <Text style={styles.sectionLabel}>수집 종류</Text>
              <View style={styles.directionRow}>
                <Pressable disabled={collecting} onPress={() => setCollectionKind("route")} style={[styles.directionOption, collectionKind === "route" && styles.routeSelected]}>
                  <Text style={[styles.anchorText, collectionKind === "route" && styles.routeSelectedText]}>경로 라벨 비교</Text>
                </Pressable>
                <Pressable disabled={collecting} onPress={() => setCollectionKind("anchor")} style={[styles.directionOption, collectionKind === "anchor" && styles.routeSelected]}>
                  <Text style={[styles.anchorText, collectionKind === "anchor" && styles.routeSelectedText]}>센서 기준점</Text>
                </Pressable>
              </View>
              <Text style={styles.sectionLabel}>층 선택</Text>
              <View style={styles.floorGrid}>
                {FLOORS.map((floor) => (
                  <Pressable
                    key={floor}
                    disabled={collecting}
                    onPress={() => { setSelectedFloor(floor); setRouteIndex(0); setLapIndex(0); }}
                    style={[styles.floorOption, selectedFloor === floor && styles.floorSelected]}
                  >
                    <Text style={[styles.floorText, selectedFloor === floor && styles.floorSelectedText]}>{floor}층</Text>
                  </Pressable>
                ))}
              </View>
              {collectionKind === "route" ? (
                <>
                  <Text style={styles.sectionLabel}>경로 선택</Text>
                  <View style={styles.directionRow}>
                    <ActionButton title="정방향" onPress={() => { setRouteReversed(false); setLapIndex(0); }} disabled={collecting} secondary={routeReversed} />
                    <ActionButton title="역방향" onPress={() => { setRouteReversed(true); setLapIndex(0); }} disabled={collecting} secondary={!routeReversed} />
                  </View>
                  <Text style={styles.routeMeta}>{routeReversed ? "역방향" : "정방향"}: {route.start} → {route.destination}</Text>
                  <Text style={styles.routeMeta}>랩 순서: {route.laps.join(" → ")}</Text>
                  {visibleRoutes.map((item, index) => (
                    <Pressable
                      key={item.id}
                      disabled={collecting}
                      onPress={() => { setRouteIndex(index); setLapIndex(0); }}
                      style={[styles.routeOption, routeIndex === index && styles.routeSelected]}
                    >
                      <Text style={[styles.routeText, routeIndex === index && styles.routeSelectedText]}>{item.title}</Text>
                    </Pressable>
                  ))}
                  <Text style={styles.routeMeta}>시작: {route.start}</Text>
                  <Text style={styles.routeMeta}>도착: {route.destination}</Text>
                  <Text style={styles.routeMeta}>랩: {route.laps.length}개</Text>
                </>
              ) : (
                <>
                  <Text style={styles.sectionLabel}>구역 라벨</Text>
                  {MAGNETIC_ANCHOR_TYPES.map((type) => (
                    <Pressable key={type} disabled={collecting} onPress={() => setMagneticAnchorType(type)} style={[styles.routeOption, magneticAnchorType === type && styles.routeSelected]}>
                      <Text style={[styles.routeText, magneticAnchorType === type && styles.routeSelectedText]}>{type}</Text>
                    </Pressable>
                  ))}
                  <Text style={styles.sectionLabel}>세부 위치 메모 (선택)</Text>
                  <TextInput
                    editable={!collecting}
                    value={magneticAnchorDetail}
                    onChangeText={setMagneticAnchorDetail}
                    placeholder="예: 4204 앞 · 비워도 측정 가능"
                    style={styles.textInput}
                  />
                  <View style={styles.warningBox}>
                    <Text style={styles.warningText}>가속도·자이로·걸음·자기장·기압·방향을 모두 저장합니다. iPhone은 일반 주변 AP의 BSSID·RSSI를 읽을 수 없어, 같은 라벨의 Android AP 자료와 분석 단계에서 결합합니다.</Text>
                  </View>
                </>
              )}
            </>
          )}
        </View>

        {screenMode === "collection" && collectionKind === "route" && (
          <View style={styles.card}>
            {predictionSummary}
            <Text style={styles.routeMeta}>{route.start} → {route.destination} · {lapIndex}/{route.laps.length} 랩</Text>
          </View>
        )}

        <View style={styles.card}>
          <Text style={styles.cardTitle}>현재 측정 · 기존 PDR 기준선</Text>
          {screenMode === "collection" && collectionKind === "route" && (
            <>
              <View style={styles.metricRow}><Text style={styles.metricLabel}>다음 랩</Text><Text style={styles.metricValue}>{nextLap || "모두 기록됨"}</Text></View>
              <View style={styles.metricRow}><Text style={styles.metricLabel}>진행</Text><Text style={styles.metricValue}>{lapIndex}/{route.laps.length}</Text></View>
            </>
          )}
          <View style={styles.metricRow}><Text style={styles.metricLabel}>iOS 보행계</Text><Text style={styles.metricValue}>{stepCount}</Text></View>
          {(screenMode === "positioning" || (screenMode === "collection" && collectionKind === "route" && fusionPosition)) && <View style={styles.metricRow}><Text style={styles.metricLabel}>PDR 검출 걸음</Text><Text style={styles.metricValue}>{livePosition?.detectedSteps ?? 0}</Text></View>}
          <View style={styles.metricRow}><Text style={styles.metricLabel}>샘플</Text><Text style={styles.metricValue}>{sampleCount.toLocaleString()}</Text></View>
          <View style={styles.metricRow}><Text style={styles.metricLabel}>기압</Text><Text style={styles.metricValue}>{livePressure === null ? "-" : `${livePressure.toFixed(2)} hPa`}</Text></View>
          <View style={styles.metricRow}><Text style={styles.metricLabel}>자기장</Text><Text style={styles.metricValue}>{liveMagnetic === null ? "-" : `${liveMagnetic.toFixed(1)} μT`}</Text></View>
          {screenMode === "bleSurvey" && (
            <>
              <View style={styles.metricRow}><Text style={styles.metricLabel}>BLE 상태</Text><Text style={styles.metricValue}>{bleState}</Text></View>
              <View style={styles.metricRow}><Text style={styles.metricLabel}>관측 송신기</Text><Text style={styles.metricValue}>{bleDeviceCount}개</Text></View>
              <View style={styles.metricRow}><Text style={styles.metricLabel}>가장 강한 신호</Text><Text style={styles.metricValue}>{bleStrongest ? `${bleStrongest.advertisedName} · ${bleStrongest.rssi} dBm` : "대기"}</Text></View>
            </>
          )}
          {(screenMode === "positioning" || (screenMode === "collection" && collectionKind === "route" && fusionPosition)) && <View style={styles.metricRow}><Text style={styles.metricLabel}>절대 방위</Text><Text style={styles.metricValue}>{liveHeading ? `${liveHeading.heading.toFixed(0)}° · 정확도 ${liveHeading.accuracy}` : "-"}</Text></View>}
          {(route.mode === "floor_tracking" || route.mode === "free_positioning") && (
            <>
              <View style={styles.metricRow}><Text style={styles.metricLabel}>기준 기압</Text><Text style={styles.metricValue}>{floorTracking?.baselinePressure == null ? `${floorTracking?.baselineProgress || 0}/${BASELINE_SAMPLE_COUNT} 수집 중` : `${floorTracking.baselinePressure.toFixed(2)} hPa`}</Text></View>
              <View style={styles.metricRow}><Text style={styles.metricLabel}>기압 변화</Text><Text style={styles.metricValue}>{floorTracking ? `${floorTracking.pressureDelta.toFixed(2)} hPa` : "-"}</Text></View>
              <View style={styles.metricRow}><Text style={styles.metricLabel}>층 후보</Text><Text style={styles.metricValue}>{floorTracking ? `${floorTracking.candidateFloor}층 · ${floorTracking.candidateStreak}/3` : "-"}</Text></View>
              <View style={styles.metricRow}><Text style={styles.metricLabel}>확정 현재 층</Text><Text style={[styles.metricValue, styles.floorEstimate]}>{floorTracking ? `${floorTracking.confirmedFloor}층` : `${route.startFloor}층`}</Text></View>
            </>
          )}
          {(screenMode === "positioning" || (screenMode === "collection" && collectionKind === "route" && fusionPosition)) && (
            <>
              <View style={styles.metricRow}><Text style={styles.metricLabel}>복도 좌표</Text><Text style={styles.metricValue}>{livePosition ? `x=${livePosition.x.toFixed(1)}` : "시작 전"}</Text></View>
              <View style={styles.corridorBar}>
                <View style={[styles.positionMarker, { left: `${corridorPercent}%` }]} />
              </View>
              <View style={styles.corridorLabels}><Text style={styles.corridorLabel}>왼쪽 계단</Text><Text style={styles.corridorLabel}>코어</Text><Text style={styles.corridorLabel}>오른쪽 계단</Text></View>
              <View style={styles.nearestBox}>
                <Text style={styles.nearestTitle}>가까운 위치 기준점 후보</Text>
                {(livePosition?.nearest || []).map((room, index) => (
                  <Text key={room.id} style={index === 0 ? styles.nearestPrimary : styles.nearestSecondary}>
                    {index + 1}. {room.label} · 지도상 {room.distance.toFixed(1)}
                  </Text>
                ))}
                {!livePosition && <Text style={styles.nearestSecondary}>시험을 시작하면 표시됩니다.</Text>}
              </View>
              <Text style={styles.limitText}>현재 후보는 메인복도 1차원 정합 결과입니다. 코어 안쪽·증축부·야외 공간에서는 정확도가 낮습니다.</Text>
            </>
          )}
        </View>

        {(screenMode === "positioning" || (screenMode === "collection" && collectionKind === "route" && fusionPosition)) && (
          <View style={styles.card}>
            <Text style={styles.cardTitle}>새 구역·2D 추적 엔진 · 비교 시험</Text>
            <Text style={styles.routeMeta}>같은 센서로 기존 기준선과 동시에 실행합니다. 지도 좌표는 실측 cm가 아니며 아래 결과는 정답이 아닙니다.</Text>
            {fusionPosition ? <>
              <Text style={styles.nearestPrimary}>패턴 OFF · {fusionPosition.baseline.floor}층 {fusionPosition.baseline.zoneLabel} · x={fusionPosition.baseline.x.toFixed(1)}, y={fusionPosition.baseline.y.toFixed(1)}</Text>
              <Text style={styles.nearestPrimary}>패턴 ON · {fusionPosition.sequenceOn.floor}층 {fusionPosition.sequenceOn.zoneLabel} · x={fusionPosition.sequenceOn.x.toFixed(1)}, y={fusionPosition.sequenceOn.y.toFixed(1)}</Text>
              <Text style={styles.routeMeta}>기존 PDR은 위 ‘가까운 위치 기준점 후보’에 별도 표시됩니다. OFF/ON 모두 동일 센서·지도 제약을 사용합니다.</Text>
              <Text style={styles.routeMeta}>ON 패턴: {fusionPosition.sequenceOn.sequenceDiagnostic?.applicationReason || "sequence_warmup"} · 누적 적용 {fusionPosition.sequenceOn.sequenceStats?.applied ?? 0}회 / 비교 {fusionPosition.sequenceOn.sequenceStats?.evaluated ?? 0}회</Text>
              <Text style={styles.routeMeta}>엔진 {fusionPosition.sequenceOn.version} · 지도 {fusionPosition.sequenceOn.navigationVersion}</Text>
              <Text style={styles.routeMeta}>보행 품질: {(fusionPosition.baseline.motionQuality*100).toFixed(0)}% · 앵커 복구 {fusionPosition.baseline.recoveryCount}회</Text>
              {(fusionPosition.sequenceOn.landmarks || []).map(p=><Text key={p.id} style={styles.nearestSecondary}>{p.label} · 지도상 {p.distance.toFixed(1)}</Text>)}
              {(fusionPosition.baseline.zone === "unknown" || fusionPosition.sequenceOn.zone === "unknown") && <Text style={styles.warningText}>미확인 영역은 이동 불가를 뜻하지 않으며, 복도 중심선 보정 전에는 방위 오차로 나타날 수 있습니다.</Text>}
            </> : <Text style={styles.routeMeta}>예상 위치를 확인하거나 경로 측정을 시작하면 표시됩니다.</Text>}
            <Text style={styles.limitText}>OFF와 ON의 차이만 자기장 8걸음 패턴입니다. ON도 후보 점수·분리도가 충분할 때만 반영합니다. 보폭은 두 엔진 모두 고정값이며 iPhone은 일반 주변 AP를 수집하지 않습니다.</Text>
          </View>
        )}

        {screenMode === "positioning" && collecting && selectedGroundTruth && (
          <View style={styles.card}>
            <Text style={styles.cardTitle}>자유 이동 랩 {freeLaps.length+1} 기록</Text>
            <Text style={styles.routeMeta}>실제로 서 있는 강의실 앞·코어 교차점·계단 입구를 선택한 뒤 기록하세요. 이 순간의 기존/OFF/ON 예측도 함께 저장됩니다.</Text>
            <View style={styles.floorGrid}>
              {FLOORS.map((floor) => (
                <Pressable key={floor} onPress={() => { setGroundTruthFloor(floor); setGroundTruthAnchorId("CORE"); }} style={[styles.floorOption, groundTruthFloor === floor && styles.floorSelected]}>
                  <Text style={[styles.floorText, groundTruthFloor === floor && styles.floorSelectedText]}>{floor}층</Text>
                </Pressable>
              ))}
            </View>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.anchorScroller}>
              {groundTruthAnchors.map((anchor) => (
                <Pressable key={anchor.id} onPress={() => setGroundTruthAnchorId(anchor.id)} style={[styles.anchorOption, selectedGroundTruth.id === anchor.id && styles.routeSelected]}>
                  <Text style={[styles.anchorText, selectedGroundTruth.id === anchor.id && styles.routeSelectedText]}>{anchor.label}</Text>
                </Pressable>
              ))}
            </ScrollView>
            {predictionSummary}
            <ActionButton title={`랩 ${freeLaps.length+1} 저장 · ${selectedGroundTruth.label}`} onPress={recordGroundTruth} secondary />
            <Text style={styles.routeMeta}>저장 후 계속 이동하세요. 라벨은 평가용으로만 기록하며 예측 위치를 초기화하지 않습니다.</Text>
          </View>
        )}

        {screenMode === "positioning" && freeLaps.length>0 && (
          <View style={styles.card}>
            <Text style={styles.cardTitle}>저장된 랩 · {freeLaps.length}개</Text>
            {freeLaps.map(lap=><Text key={lap.index} style={styles.routeMeta}>{lap.index}. {lap.floor}층 {lap.label}</Text>)}
          </View>
        )}

        <View style={styles.actions}>
          {screenMode === "collection" && <ActionButton title={collectionKind === "anchor" ? "센서 기준점 측정 시작" : `${routeReversed ? "역방향" : "정방향"} · 시작 라벨 저장 및 측정 시작`} onPress={() => startCollection()} disabled={collecting || Object.values(availability).some((value) => value === null)} />}
          {screenMode === "collection" && collectionKind === "route" && <ActionButton title={nextLap ? `현재 지점 기록 · ${nextLap}` : "모든 랩 기록 완료"} onPress={recordLap} disabled={!collecting || !nextLap} secondary />}
          {screenMode === "bleSurvey" && <ActionButton title={isBleSurveyAvailable() ? "BLE 환경 조사 시작" : "전용 iPhone 앱 설치 후 사용"} onPress={() => startCollection()} disabled={collecting || !isBleSurveyAvailable() || Object.values(availability).some((value) => value === null)} />}
          <ActionButton title={screenMode === "positioning" ? "실내측위 시험 종료" : screenMode === "bleSurvey" ? "BLE 환경 조사 종료" : "측정 종료"} onPress={stopCollection} disabled={!collecting} danger />
          <ActionButton title={screenMode === "positioning" ? "시험 로그 저장·공유" : screenMode === "bleSurvey" ? "BLE JSONL 저장·공유" : "JSONL 저장·공유"} onPress={shareSession} disabled={!sessionReady || collecting} secondary />
        </View>

        <View style={styles.statusBox}><Text style={styles.statusText}>{status}</Text></View>
        <Text style={styles.notice}>{screenMode === "positioning"
          ? "시험 시작 직후 기준 기압 5개가 수집될 때까지 멈춘 뒤 이동하세요. 층·강의실 결과와 실제 위치를 비교해 주세요."
          : screenMode === "bleSurvey"
          ? "BLE 수집은 Wi-Fi AP 스캔이 아닙니다. 고정 송신기인지 현장 분석으로 먼저 확인하고, 사람의 휴대폰·이어폰처럼 이동하는 신호는 지문 기준점에서 제외합니다."
          : collectionKind === "anchor"
          ? "같은 지점·휴대폰 방향으로 10~20초씩 3회 측정하세요. AP는 같은 라벨의 Android 로그에서 수집합니다."
          : "같은 경로를 같은 자세로 3회 측정하세요. iOS 데이터는 Android 원본과 분리해 비교 분석합니다."}</Text>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: "#f3f5f9" },
  container: { padding: 18, paddingBottom: 48, gap: 14 },
  eyebrow: { color: "#376ed8", fontSize: 13, fontWeight: "800", letterSpacing: 0.5 },
  title: { color: "#15213a", fontSize: 28, fontWeight: "900" },
  subtitle: { color: "#697386", fontSize: 14, marginTop: -8 },
  textInput: { minHeight: 48, borderWidth: 1, borderColor: "#b7c0d0", borderRadius: 12, backgroundColor: "#fff", paddingHorizontal: 14, color: "#15213a", fontSize: 15 },
  warningBox: { borderRadius: 12, backgroundColor: "#fff4d6", padding: 12 },
  warningText: { color: "#6f5513", fontSize: 13, lineHeight: 19 },
  modeTabs: { flexDirection: "row", borderRadius: 14, backgroundColor: "#e5e9f1", padding: 4, gap: 4 },
  modeTab: { flex: 1, minHeight: 46, borderRadius: 11, alignItems: "center", justifyContent: "center", paddingHorizontal: 8 },
  modeTabSelected: { backgroundColor: "#3478f6" },
  modeTabText: { color: "#57647a", fontSize: 14, fontWeight: "900", textAlign: "center" },
  modeTabTextSelected: { color: "white" },
  modeDescription: { borderRadius: 14, backgroundColor: "#e7edfb", padding: 14 },
  modeDescriptionText: { color: "#344668", fontSize: 13, lineHeight: 19 },
  card: { backgroundColor: "white", borderRadius: 18, padding: 16, gap: 10, shadowColor: "#1d2b4b", shadowOpacity: 0.06, shadowRadius: 12, elevation: 2 },
  cardTitle: { color: "#17233d", fontSize: 18, fontWeight: "900" },
  sensorGrid: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  sensorBadge: { width: "31%", minWidth: 92, borderRadius: 12, backgroundColor: "#eef1f6", paddingHorizontal: 10, paddingVertical: 9 },
  sensorOk: { backgroundColor: "#e5f7ec" },
  sensorNo: { backgroundColor: "#fdeaea" },
  sensorBadgeText: { color: "#28354f", fontSize: 13, fontWeight: "700" },
  sensorBadgeState: { color: "#56647d", fontSize: 12, marginTop: 3 },
  routeOption: { borderWidth: 1, borderColor: "#d8deea", borderRadius: 12, padding: 13 },
  routeSelected: { borderColor: "#3978ed", backgroundColor: "#eaf1ff" },
  routeText: { color: "#4e5b72", fontWeight: "700" },
  routeSelectedText: { color: "#245fce" },
  sectionLabel: { color: "#697386", fontSize: 13, fontWeight: "800", marginTop: 2 },
  anchorScroller: { gap: 8, paddingRight: 8 },
  anchorOption: { borderWidth: 1, borderColor: "#d8deea", borderRadius: 12, paddingHorizontal: 13, paddingVertical: 11 },
  anchorText: { color: "#4e5b72", fontSize: 13, fontWeight: "800" },
  directionRow: { flexDirection: "row", gap: 8 },
  directionOption: { flex: 1, borderWidth: 1, borderColor: "#d8deea", borderRadius: 12, paddingHorizontal: 8, paddingVertical: 12, alignItems: "center" },
  floorGrid: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  floorOption: { width: "17%", minWidth: 48, borderWidth: 1, borderColor: "#d8deea", borderRadius: 10, paddingVertical: 9, alignItems: "center" },
  floorSelected: { borderColor: "#3978ed", backgroundColor: "#eaf1ff" },
  floorText: { color: "#4e5b72", fontSize: 13, fontWeight: "800" },
  floorSelectedText: { color: "#245fce" },
  floorEstimate: { color: "#167746", fontSize: 20 },
  routeMeta: { color: "#697386", fontSize: 13 },
  metricRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: "#dde2eb", paddingVertical: 6, gap: 16 },
  metricLabel: { color: "#647087", fontSize: 14 },
  metricValue: { color: "#1d2a43", fontSize: 14, fontWeight: "800", flexShrink: 1, textAlign: "right" },
  corridorBar: { height: 8, borderRadius: 4, backgroundColor: "#dce3ef", marginTop: 8, marginHorizontal: 5 },
  positionMarker: { position: "absolute", top: -6, width: 20, height: 20, marginLeft: -10, borderRadius: 10, backgroundColor: "#3478f6", borderWidth: 3, borderColor: "white" },
  corridorLabels: { flexDirection: "row", justifyContent: "space-between" },
  corridorLabel: { color: "#778196", fontSize: 11, fontWeight: "700" },
  nearestBox: { borderRadius: 14, backgroundColor: "#edf3ff", padding: 13, gap: 5, marginTop: 4 },
  nearestTitle: { color: "#586985", fontSize: 12, fontWeight: "900" },
  nearestPrimary: { color: "#175bc5", fontSize: 18, fontWeight: "900" },
  nearestSecondary: { color: "#4f607b", fontSize: 13, fontWeight: "700" },
  predictionBox: { borderRadius: 15, backgroundColor: "#edf3ff", padding: 14, gap: 9, marginTop: 4 },
  predictionPrimary: { color: "#175bc5", fontSize: 21, fontWeight: "900" },
  correctionBox: { borderRadius: 15, backgroundColor: "#f7f8fb", borderWidth: 1, borderColor: "#d8deea", padding: 13, gap: 9, marginTop: 4 },
  limitText: { color: "#8a6270", fontSize: 12, lineHeight: 17 },
  actions: { gap: 10 },
  actionButton: { borderRadius: 14, backgroundColor: "#3478f6", minHeight: 52, alignItems: "center", justifyContent: "center", paddingHorizontal: 14 },
  actionSecondary: { backgroundColor: "white", borderWidth: 1, borderColor: "#b8c6df" },
  actionDanger: { backgroundColor: "#d95252" },
  actionDisabled: { opacity: 0.42 },
  actionPressed: { transform: [{ scale: 0.99 }] },
  actionText: { color: "white", fontSize: 15, fontWeight: "900", textAlign: "center" },
  actionSecondaryText: { color: "#315b9f" },
  statusBox: { borderRadius: 14, backgroundColor: "#e7edfb", padding: 14 },
  statusText: { color: "#344668", fontSize: 14, lineHeight: 20 },
  notice: { color: "#778196", fontSize: 12, lineHeight: 18 }
});
