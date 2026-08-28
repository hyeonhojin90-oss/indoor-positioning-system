const $ = (id) => document.getElementById(id);

const MAP_MIN_X = 0;
const MAP_MAX_X = 135.407;
const CORE_POSITION = { x: 70.804, y: -5.29 };
const STEP_LENGTH_M = 0.65;
const FLOOR_ROWS = { 4: 151, 3: 433 };
const FLOOR_BOXES = { 4: { y: 22, h: 252 }, 3: { y: 305, h: 252 } };

const state = {
  maps: {},
  position: { floor: 4, x: CORE_POSITION.x, y: CORE_POSITION.y },
  rawPosition: { floor: 4, x: CORE_POSITION.x, y: CORE_POSITION.y },
  targetKey: "4:4213",
  verticalMode: "stairs",
  visibleMapFloor: 4,
  mapMode: "2d",
  lastCorrection: null,
  route: null,
  sensor: {
    active: false,
    calibrated: false,
    compassHeading: null,
    headingOffset: 0,
    gravity: null,
    previousLinear: 0,
    lastStepAt: 0,
    stepCount: 0
  }
};

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function distance(a, b) {
  return Math.hypot(a.x - b.x, a.y - b.y);
}

function manhattanDistance(a, b) {
  return Math.abs(a.x - b.x) + Math.abs(a.y - b.y);
}

function mapX(x) {
  return 72 + ((MAP_MAX_X - x) / (MAP_MAX_X - MAP_MIN_X)) * 940;
}

function mapY(floor, y) {
  return FLOOR_ROWS[floor] - y * 10;
}

function composeFloor3(base, override) {
  const removeIds = new Set(override.remove_facility_ids || []);
  return {
    ...structuredClone(base),
    ...structuredClone(override),
    layout_dimensions: { ...base.layout_dimensions, ...override.layout_dimensions },
    floor_core: { ...base.floor_core, ...override.floor_core },
    facilities: base.facilities.filter((facility) => !removeIds.has(facility.id)),
    rooms: structuredClone(override.rooms),
    routing: { ...base.routing, ...override.routing }
  };
}

function createGraph() {
  return { nodes: new Map(), edges: new Map(), anchors: new Map() };
}

function addNode(graph, node) {
  graph.nodes.set(node.id, node);
  graph.edges.set(node.id, []);
  if (node.anchor) {
    if (!graph.anchors.has(node.floor)) graph.anchors.set(node.floor, []);
    graph.anchors.get(node.floor).push(node.id);
  }
}

function addEdge(graph, from, to, meta = {}) {
  const first = graph.nodes.get(from);
  const second = graph.nodes.get(to);
  if (!first || !second) return;
  const cost = meta.cost ?? (first.floor === second.floor ? manhattanDistance(first, second) : 8);
  const edge = { from, to, cost, ...meta };
  graph.edges.get(from).push(edge);
  graph.edges.get(to).push({ ...edge, from: to, to: from });
}

function addFloorNodes(graph, floor, map) {
  const prefix = `${floor}F`;
  const hub = map.routing.hub_junction;
  const layout = map.layout_dimensions;
  const core = { id: `${prefix}:core`, floor, x: CORE_POSITION.x, y: CORE_POSITION.y, label: `${floor}F 중앙 코어 복도`, anchor: true, kind: "core" };
  const main = { id: `${prefix}:hub`, floor, x: hub.x, y: 0, label: `${floor}F 메인 복도`, anchor: true, kind: "hub" };
  addNode(graph, core);
  addNode(graph, main);
  addEdge(graph, core.id, main.id, { kind: "core-corridor", label: "코어 복도에서 메인 복도로 이동" });

  for (const room of map.rooms) {
    if (!Number.isFinite(room.x) || !Number.isFinite(room.y)) continue;
    const frontId = `${prefix}:room-front:${room.id}`;
    const doorId = `${prefix}:room:${room.id}`;
    addNode(graph, {
      id: frontId,
      floor,
      x: room.front_x ?? room.x,
      y: room.front_y ?? 0,
      label: `${room.label || room.id} 앞`,
      anchor: true,
      kind: "room-front",
      roomId: room.id
    });
    addNode(graph, {
      id: doorId,
      floor,
      x: room.x,
      y: room.y,
      label: room.label || room.id,
      kind: "room-door",
      roomId: room.id
    });
    addEdge(graph, main.id, frontId, { kind: "main-corridor", label: "메인 복도 이동" });
    addEdge(graph, frontId, doorId, { kind: "room-entry", label: `${room.label || room.id} 출입구로 이동` });
  }

  const verticalLinks = map.routing.vertical_links || [];
  for (const link of verticalLinks) {
    const nodeId = `${prefix}:vertical:${link.id}`;
    const isCoreLink = link.id.includes("CENTER") || link.id.includes("EV_CORE");
    const approachId = `${nodeId}:approach`;
    addNode(graph, {
      id: nodeId,
      floor,
      x: link.x,
      y: link.y,
      label: `${floor}F ${link.label}`,
      anchor: true,
      kind: "vertical",
      linkId: link.id
    });
    if (isCoreLink) {
      addEdge(graph, core.id, nodeId, { kind: "core-facility", label: `${link.label} 입구` });
    } else {
      addNode(graph, {
        id: approachId,
        floor,
        x: link.x,
        y: 0,
        label: `${floor}F ${link.label} 앞`,
        anchor: true,
        kind: "stair-approach"
      });
      addEdge(graph, main.id, approachId, { kind: "main-corridor", label: "메인 복도 이동" });
      addEdge(graph, approachId, nodeId, { kind: "stair-entry", label: "계단실 입구로 이동" });
    }
  }

  if (floor !== 3) return;
  const extension = map.floor3_extension;
  if (!extension) return;
  const branchX = map.routing.extension_junction?.x ?? extension.branch_map_x;
  const entryId = "3F:extension-entry";
  const freeId = "3F:free-space";
  const corridorId = "3F:extension-corridor";
  addNode(graph, { id: entryId, floor, x: branchX, y: 0, label: "자유공간 첫 입구", anchor: true, kind: "extension-entry" });
  addNode(graph, { id: freeId, floor, x: branchX, y: 4.6, label: "자유공간", anchor: true, kind: "free-space" });
  addNode(graph, { id: corridorId, floor, x: branchX, y: 8.3, label: "증축부 복도", anchor: true, kind: "extension-corridor" });
  addEdge(graph, main.id, entryId, { kind: "main-corridor", label: "3203 라인까지 메인 복도 이동" });
  addEdge(graph, entryId, freeId, { kind: "extension-entry", label: "열린 첫 입구로 자유공간 진입" });
  addEdge(graph, freeId, corridorId, { kind: "extension-corridor", label: "증축부 복도 방향으로 이동" });

  const extensionTargets = [
    { roomId: "3108", label: "3108 IT홀", x: branchX - 3.1, y: 8.3 },
    { roomId: "3104-1", label: "3104-1", x: branchX + 3.1, y: 11.2 },
    { roomId: "3104-2", label: "3104-2", x: branchX + 3.1, y: 7.1 }
  ];
  for (const room of extensionTargets) {
    const id = `${prefix}:room:${room.roomId}`;
    addNode(graph, { id, floor, ...room, kind: "room-door", roomId: room.roomId, estimated: true });
    addEdge(graph, corridorId, id, { kind: "extension-room", label: `${room.label} 출입구로 이동` });
  }
}

function addVerticalEdges(graph) {
  const links = state.maps[4].routing.vertical_links || [];
  for (const link of links) {
    const lower = `3F:vertical:${link.id}`;
    const upper = `4F:vertical:${link.id}`;
    const allow = state.verticalMode === "stairs" ? link.type === "stairs" : link.type === "elevator";
    if (!allow) continue;
    addEdge(graph, lower, upper, {
      kind: link.type === "stairs" ? "vertical-stairs" : "vertical-elevator",
      label: link.label,
      verticalLink: link,
      cost: link.type === "stairs" ? 8.4 : 10.5
    });
  }
}

function addDynamicStart(graph) {
  const id = "current-position";
  const current = state.position;
  addNode(graph, {
    id,
    floor: current.floor,
    x: current.x,
    y: current.y,
    label: `${current.floor}F 현재 위치`,
    kind: "current"
  });
  const nearestAnchors = [...(graph.anchors.get(current.floor) || [])]
    .map((anchorId) => ({ anchorId, node: graph.nodes.get(anchorId) }))
    .sort((first, second) => manhattanDistance(current, first.node) - manhattanDistance(current, second.node))
    .slice(0, 3);
  for (const { anchorId } of nearestAnchors) {
    addEdge(graph, id, anchorId, { kind: "position-to-network", label: "가까운 복도 그래프 연결" });
  }
  return id;
}

function buildGraph() {
  const graph = createGraph();
  addFloorNodes(graph, 3, state.maps[3]);
  addFloorNodes(graph, 4, state.maps[4]);
  addVerticalEdges(graph);
  return graph;
}

function getTargetNodeId(targetKey) {
  const [floor, roomId] = targetKey.split(":");
  return `${floor}F:room:${roomId}`;
}

function shortestPath(graph, start, target) {
  const distances = new Map([[start, 0]]);
  const previous = new Map();
  const pending = new Set(graph.nodes.keys());

  while (pending.size) {
    let current = null;
    let currentDistance = Infinity;
    for (const id of pending) {
      const candidate = distances.get(id) ?? Infinity;
      if (candidate < currentDistance) {
        current = id;
        currentDistance = candidate;
      }
    }
    if (!current || currentDistance === Infinity) break;
    pending.delete(current);
    if (current === target) break;
    for (const edge of graph.edges.get(current) || []) {
      if (!pending.has(edge.to)) continue;
      const next = currentDistance + edge.cost;
      if (next < (distances.get(edge.to) ?? Infinity)) {
        distances.set(edge.to, next);
        previous.set(edge.to, { node: current, edge });
      }
    }
  }

  if (!previous.has(target) && start !== target) return null;
  const nodes = [target];
  const edges = [];
  let cursor = target;
  while (cursor !== start) {
    const item = previous.get(cursor);
    if (!item) return null;
    edges.unshift(item.edge);
    nodes.unshift(item.node);
    cursor = item.node;
  }
  return { nodes, edges, total: distances.get(target) ?? 0 };
}

function calculateRoute() {
  const graph = buildGraph();
  const start = addDynamicStart(graph);
  const target = getTargetNodeId(state.targetKey);
  const result = shortestPath(graph, start, target);
  state.route = result ? { ...result, graph } : null;
  return state.route;
}

function closestPointOnSegment(point, start, end) {
  const dx = end.x - start.x;
  const dy = end.y - start.y;
  const lengthSquared = dx * dx + dy * dy;
  const ratio = lengthSquared ? clamp(((point.x - start.x) * dx + (point.y - start.y) * dy) / lengthSquared, 0, 1) : 0;
  return { x: start.x + dx * ratio, y: start.y + dy * ratio };
}

function snapToNetwork(floor, point) {
  const map = state.maps[floor];
  const hub = map.routing.hub_junction;
  const layout = map.layout_dimensions;
  const segments = [
    [{ x: 0, y: 0 }, { x: layout.main_length, y: 0 }],
    [{ x: hub.x, y: -layout.hub_length - layout.corridor_width / 2 }, { x: hub.x, y: 0 }]
  ];
  if (floor === 3 && map.floor3_extension) {
    const branch = map.routing.extension_junction?.x ?? map.floor3_extension.branch_map_x;
    segments.push([{ x: branch, y: 0 }, { x: branch, y: 10.5 }]);
  }
  const candidates = segments.map(([start, end]) => closestPointOnSegment(point, start, end));
  return candidates.reduce((best, candidate) => distance(point, candidate) < distance(point, best) ? candidate : best);
}

function resetPosition() {
  const floor = Number($("startFloorSelect").value);
  state.position = { floor, x: CORE_POSITION.x, y: CORE_POSITION.y };
  state.rawPosition = { ...state.position };
  state.lastCorrection = null;
  state.sensor.stepCount = 0;
  setNativeMapFloor(floor);
  refresh("코어 복도 기준점으로 초기화했습니다.");
}

function setNativeMapFloor(floor) {
  state.visibleMapFloor = floor;
  document.querySelectorAll("[data-native-floor]").forEach((button) => {
    const active = Number(button.dataset.nativeFloor) === floor;
    button.classList.toggle("active", active);
    button.setAttribute("aria-selected", String(active));
  });
  document.querySelectorAll("[data-native-map-floor]").forEach((frame) => {
    frame.hidden = Number(frame.dataset.nativeMapFloor) !== floor;
  });
}

function syncAlgorithm3D() {
  const targetId = state.targetKey.split(":")[1];
  const frame = $("algorithm3dFrame");
  const source = `./clay.html?embed=algorithm&floor=both&target=${encodeURIComponent(targetId)}&from=pdr`;
  if (frame.dataset.source === source) return;
  frame.dataset.source = source;
  frame.src = source;
}

function setMapMode(mode) {
  state.mapMode = mode;
  const is3d = mode === "3d";
  document.querySelectorAll("[data-map-mode]").forEach((button) => {
    const active = button.dataset.mapMode === mode;
    button.classList.toggle("active", active);
    button.setAttribute("aria-selected", String(active));
  });
  $("nativeMapArea").hidden = is3d;
  $("algorithm3dArea").hidden = !is3d;
  if (is3d) syncAlgorithm3D();
}

function moveByHeading(distanceToMove, headingDegrees, source) {
  const radians = headingDegrees * Math.PI / 180;
  const raw = state.rawPosition;
  raw.x = clamp(raw.x + Math.cos(radians) * distanceToMove, MAP_MIN_X, MAP_MAX_X);
  raw.y += Math.sin(radians) * distanceToMove;
  const snapped = snapToNetwork(raw.floor, raw);
  state.position = { floor: raw.floor, ...snapped };
  state.lastCorrection = `${source} ${distanceToMove.toFixed(2)}m 이동 후 복도 스냅`;
  refresh();
}

function applyManualMove() {
  const steps = clamp(Number($("stepsInput").value) || 0, 0, 200);
  if (!steps) return;
  const direction = $("directionSelect").value;
  const heading = {
    "map-right": 180,
    "map-left": 0,
    "toward-main": 90,
    "toward-core": 270
  }[direction];
  moveByHeading(steps * STEP_LENGTH_M, heading, `${steps}걸음 수동 PDR`);
}

function findMagneticCandidate(total) {
  if (state.position.floor !== 4) return null;
  const fingerprints = state.maps[4].magnetic_fingerprints || [];
  return fingerprints
    .filter((fingerprint) => fingerprint.id !== "EV_INSIDE")
    .map((fingerprint) => {
      const difference = Math.abs(total - fingerprint.total_avg);
      const sigma = Math.max(fingerprint.total_std || 4, 1);
      const spatialDistance = distance(state.position, fingerprint);
      return { ...fingerprint, difference, spatialDistance, score: difference / sigma + spatialDistance / 20 };
    })
    .filter((fingerprint) => fingerprint.spatialDistance <= 30)
    .sort((first, second) => first.score - second.score)[0];
}

function applyMagneticCorrection() {
  const total = Number($("magInput").value);
  if (!Number.isFinite(total)) {
    setStatus("자기장 Total 값을 입력하세요.", "warn");
    return;
  }
  if (state.position.floor !== 4) {
    setStatus("3층 자기장 지문값은 아직 측정 전이라 보정을 적용하지 않았습니다.", "warn");
    return;
  }
  const candidate = findMagneticCandidate(total);
  if (!candidate) {
    setStatus("현재 위치 근처에 비교 가능한 4층 자기장 지문값이 없습니다.", "warn");
    return;
  }
  const sigma = Math.max(candidate.total_std || 4, 1);
  const fieldFit = Math.exp(-0.5 * (candidate.difference / sigma) ** 2);
  const distanceFit = Math.exp(-candidate.spatialDistance / 20);
  const magneticWeight = clamp(fieldFit * distanceFit * 0.72, 0.05, 0.7);
  const raw = state.rawPosition;
  raw.x = raw.x * (1 - magneticWeight) + candidate.x * magneticWeight;
  raw.y = raw.y * (1 - magneticWeight) + candidate.y * magneticWeight;
  state.position = { floor: 4, ...snapToNetwork(4, raw) };
  state.lastCorrection = `${candidate.label} 기준 ${(magneticWeight * 100).toFixed(0)}% 보정`;
  refresh(state.lastCorrection);
}

function populateTargets() {
  const select = $("targetSelect");
  const groups = [3, 4].map((floor) => {
    const rooms = state.maps[floor].rooms.filter((room) => room.id);
    const options = rooms.map((room) => `<option value="${floor}:${room.id}">${floor}F · ${room.label || room.id}</option>`).join("");
    return `<optgroup label="${floor}층">${options}</optgroup>`;
  });
  select.innerHTML = groups.join("");
  select.value = state.targetKey;
}

function uniqueSteps(route) {
  const graph = route.graph;
  const labels = [];
  const start = graph.nodes.get(route.nodes[0]);
  labels.push(`${start.floor}F 현재 위치에서 출발`);
  for (const edge of route.edges) {
    const from = graph.nodes.get(edge.from);
    const to = graph.nodes.get(edge.to);
    if (edge.kind === "vertical-stairs") {
      const motion = to.floor > from.floor ? "올라" : "내려";
      labels.push(`중앙 메인계단: 12계단 ${motion} 중간참에서 반대편으로 돌아 다시 12계단 이동`);
      labels.push(`${to.floor}F 계단 출구로 도착`);
      continue;
    }
    if (edge.kind === "vertical-elevator") {
      labels.push("코어 엘레베이터로 층 이동");
      labels.push(`${to.floor}F 엘레베이터 앞에 도착`);
      continue;
    }
    if (to.kind === "hub") labels.push(`${to.floor}F 메인 복도로 진입`);
    if (to.kind === "extension-entry") labels.push("3203 라인의 열린 첫 입구로 진입");
    if (to.kind === "free-space") labels.push("자유공간 통과");
    if (to.kind === "extension-corridor") labels.push("증축부 복도로 이동");
    if (to.kind === "room-door") labels.push(`${to.label} 앞에 도착`);
  }
  return labels.filter((item, index) => index === 0 || item !== labels[index - 1]);
}

function renderFloorMap(floor, route) {
  const map = state.maps[floor];
  const box = FLOOR_BOXES[floor];
  const hub = map.routing.hub_junction;
  const targetId = state.targetKey.split(":")[1];
  let html = `<g class="floor-map floor-${floor}">`;
  html += `<rect class="floor-frame" x="42" y="${box.y}" width="1036" height="${box.h}" rx="6"/>`;
  html += `<text class="floor-title" x="58" y="${box.y + 25}">${floor}F</text>`;
  html += `<text class="floor-subtitle" x="100" y="${box.y + 25}">${floor === 3 ? "증축부 포함" : "공통 기준층"}</text>`;
  html += `<line class="nav-corridor" x1="${mapX(0)}" y1="${mapY(floor, 0)}" x2="${mapX(map.layout_dimensions.main_length)}" y2="${mapY(floor, 0)}"/>`;
  html += `<line class="nav-core-corridor" x1="${mapX(hub.x)}" y1="${mapY(floor, -10)}" x2="${mapX(hub.x)}" y2="${mapY(floor, 0)}"/>`;
  html += `<text class="nav-core-label" x="${mapX(hub.x) + 8}" y="${mapY(floor, -7.7)}">코어</text>`;

  for (const room of map.rooms) {
    if (!Number.isFinite(room.x) || !Number.isFinite(room.y)) continue;
    const width = Math.max((room.width || 5) * 6.9 - 2, 16);
    const y = mapY(floor, room.y);
    const x = mapX(room.x) - width / 2;
    const target = room.id === targetId;
    html += `<rect class="nav-room ${target ? "target" : ""}" x="${x}" y="${y - 20}" width="${width}" height="40"/>`;
    if (width > 22 || target) html += `<text class="nav-room-label" x="${mapX(room.x)}" y="${y + 4}">${room.label || room.id}</text>`;
  }

  if (floor === 3 && map.floor3_extension) {
    const branch = map.routing.extension_junction?.x ?? map.floor3_extension.branch_map_x;
    const freeX = mapX(branch) - 28;
    const freeY = mapY(floor, 4.6) - 20;
    html += `<rect class="nav-extension free" x="${freeX}" y="${freeY}" width="56" height="40"/>`;
    html += `<text class="nav-extension-label" x="${mapX(branch)}" y="${freeY + 25}">자유공간</text>`;
    html += `<line class="nav-extension-corridor" x1="${mapX(branch)}" y1="${mapY(floor, 4.6)}" x2="${mapX(branch)}" y2="${mapY(floor, 11.2)}"/>`;
    for (const extensionRoom of [
      { id: "3108", label: "IT홀", x: branch - 3.1, y: 8.3 },
      { id: "3104-1", label: "3104-1", x: branch + 3.1, y: 11.2 },
      { id: "3104-2", label: "3104-2", x: branch + 3.1, y: 7.1 }
    ]) {
      const target = extensionRoom.id === targetId;
      html += `<rect class="nav-extension ${target ? "target" : ""}" x="${mapX(extensionRoom.x) - 23}" y="${mapY(floor, extensionRoom.y) - 17}" width="46" height="34"/>`;
      html += `<text class="nav-room-label" x="${mapX(extensionRoom.x)}" y="${mapY(floor, extensionRoom.y) + 4}">${extensionRoom.label}</text>`;
    }
  }

  for (const facility of map.facilities) {
    if (facility.type !== "stairs" && facility.type !== "elevator") continue;
    const className = facility.type === "stairs" ? "nav-facility stairs" : "nav-facility elevator";
    html += `<circle class="${className}" cx="${mapX(facility.x)}" cy="${mapY(floor, facility.y)}" r="5"/>`;
  }

  if (route) {
    for (const edge of route.edges) {
      const from = route.graph.nodes.get(edge.from);
      const to = route.graph.nodes.get(edge.to);
      if (from.floor !== floor || to.floor !== floor) continue;
      html += `<line class="nav-route" x1="${mapX(from.x)}" y1="${mapY(floor, from.y)}" x2="${mapX(to.x)}" y2="${mapY(floor, to.y)}"/>`;
    }
  }

  if (state.position.floor === floor) {
    html += `<circle class="nav-current" cx="${mapX(state.position.x)}" cy="${mapY(floor, state.position.y)}" r="8"/>`;
    html += `<text class="nav-current-label" x="${mapX(state.position.x) + 11}" y="${mapY(floor, state.position.y) - 9}">현재</text>`;
  }
  html += "</g>";
  return html;
}

function renderMap() {
  const route = calculateRoute();
  const targetNode = route?.graph.nodes.get(getTargetNodeId(state.targetKey));

  const [targetFloor, targetRoom] = state.targetKey.split(":");
  const targetLabel = targetNode?.label || targetRoom;
  $("routeTitle").textContent = `${state.position.floor}F 중앙 코어 복도에서 ${targetFloor}F ${targetLabel}까지`;
  const stairs = route?.edges.filter((edge) => edge.kind === "vertical-stairs").length || 0;
  const horizontal = (route?.edges || []).filter((edge) => !edge.kind.startsWith("vertical-")).reduce((sum, edge) => sum + edge.cost, 0);
  $("routeMeta").textContent = route
    ? `복도 기준 약 ${horizontal.toFixed(1)}m${stairs ? " · 층간 24계단" : ""}`
    : "현재 선택에서는 연결 경로를 찾지 못했습니다.";
  $("routeSteps").innerHTML = route ? uniqueSteps(route).map((step) => `<li>${step}</li>`).join("") : "";
}

function renderReadout() {
  const target = state.targetKey.split(":");
  const floorMessage = state.position.floor === 4
    ? "4층 자기장 지문 보정 가능"
    : "3층 자기장 지문 측정 필요";
  $("positionReadout").innerHTML = `
    <div><strong>현재 층</strong><span>${state.position.floor}F</span></div>
    <div><strong>복도 보정 좌표</strong><span>x ${state.position.x.toFixed(1)}, y ${state.position.y.toFixed(1)}</span></div>
    <div><strong>선택 목적지</strong><span>${target[0]}F · ${target[1]}</span></div>
    <div><strong>보정 상태</strong><span>${state.lastCorrection || floorMessage}</span></div>
  `;
}

function setStatus(message, mode = "ok") {
  const element = $("navStatus");
  element.textContent = message;
  element.className = `nav-status ${mode}`;
}

function refresh(statusMessage = "") {
  renderMap();
  renderReadout();
  if (statusMessage) setStatus(statusMessage, "ok");
}

function normalizeHeading(value) {
  return ((value % 360) + 360) % 360;
}

function compassHeading(event) {
  if (Number.isFinite(event.webkitCompassHeading)) return event.webkitCompassHeading;
  if (Number.isFinite(event.alpha)) return normalizeHeading(360 - event.alpha);
  return null;
}

function handleOrientation(event) {
  const heading = compassHeading(event);
  if (heading === null) return;
  state.sensor.compassHeading = heading;
  updateSensorReadout();
}

function handleMotion(event) {
  if (!state.sensor.active || !state.sensor.calibrated) return;
  const acceleration = event.accelerationIncludingGravity;
  if (!acceleration) return;
  const magnitude = Math.hypot(acceleration.x || 0, acceleration.y || 0, acceleration.z || 0);
  const sensor = state.sensor;
  sensor.gravity = sensor.gravity === null ? magnitude : sensor.gravity * 0.91 + magnitude * 0.09;
  const linear = magnitude - sensor.gravity;
  const timestamp = performance.now();
  if (linear > 1.18 && sensor.previousLinear <= 1.18 && timestamp - sensor.lastStepAt > 320) {
    sensor.lastStepAt = timestamp;
    sensor.stepCount += 1;
    const heading = normalizeHeading((sensor.compassHeading ?? 0) + sensor.headingOffset);
    moveByHeading(STEP_LENGTH_M, heading, "센서 PDR");
  }
  sensor.previousLinear = linear;
  updateSensorReadout();
}

async function startSensors() {
  try {
    const permissionRequests = [];
    if (typeof DeviceMotionEvent !== "undefined" && typeof DeviceMotionEvent.requestPermission === "function") {
      permissionRequests.push(DeviceMotionEvent.requestPermission());
    }
    if (typeof DeviceOrientationEvent !== "undefined" && typeof DeviceOrientationEvent.requestPermission === "function") {
      permissionRequests.push(DeviceOrientationEvent.requestPermission());
    }
    const results = await Promise.all(permissionRequests);
    if (results.some((result) => result !== "granted")) {
      setStatus("센서 권한이 허용되지 않았습니다. 수동 테스트는 계속 사용할 수 있습니다.", "warn");
      return;
    }
    if (!("DeviceMotionEvent" in window) || !("DeviceOrientationEvent" in window)) {
      setStatus("이 브라우저는 휴대폰 모션·방향 센서를 제공하지 않습니다.", "warn");
      return;
    }
    state.sensor.active = true;
    window.addEventListener("deviceorientation", handleOrientation, true);
    window.addEventListener("devicemotion", handleMotion, true);
    $("sensorButton").disabled = true;
    $("calibrateButton").disabled = false;
    $("sensorHelp").textContent = "메인 복도를 지도 오른쪽으로 바라본 뒤 방향 설정 버튼을 누르세요. 그 다음부터 감지된 걸음이 반영됩니다.";
    updateSensorReadout();
    setStatus("센서가 연결되었습니다. 방향을 한 번 설정하세요.");
  } catch (error) {
    setStatus("센서 연결에 실패했습니다. 수동 테스트를 사용하세요.", "warn");
  }
}

function calibrateHeading() {
  if (!Number.isFinite(state.sensor.compassHeading)) {
    setStatus("방향값을 아직 받지 못했습니다. 휴대폰을 잠시 움직인 뒤 다시 시도하세요.", "warn");
    return;
  }
  state.sensor.headingOffset = normalizeHeading(180 - state.sensor.compassHeading);
  state.sensor.calibrated = true;
  $("sensorHelp").textContent = "방향이 지도 오른쪽으로 설정되었습니다. 휴대폰을 들고 걸으면 걸음마다 복도 좌표에 스냅됩니다.";
  updateSensorReadout();
  setStatus("센서 방향을 지도 오른쪽으로 설정했습니다.");
}

function updateSensorReadout() {
  const sensor = state.sensor;
  if (!sensor.active) {
    $("sensorReadout").textContent = "센서 대기 중";
    return;
  }
  const heading = Number.isFinite(sensor.compassHeading) ? `${sensor.compassHeading.toFixed(0)}°` : "방향 수신 중";
  $("sensorReadout").textContent = `방향 ${heading} · 감지 걸음 ${sensor.stepCount} · ${sensor.calibrated ? "지도 방향 설정됨" : "방향 설정 필요"}`;
}

function bindEvents() {
  $("startFloorSelect").addEventListener("change", resetPosition);
  $("targetSelect").addEventListener("change", (event) => {
    state.targetKey = event.target.value;
    setNativeMapFloor(Number(event.target.value.split(":")[0]));
    if (state.mapMode === "3d") syncAlgorithm3D();
    refresh("목적지를 변경했습니다.");
  });
  $("verticalModeSelect").addEventListener("change", (event) => {
    state.verticalMode = event.target.value;
    refresh(event.target.value === "stairs" ? "중앙 메인계단 경로를 적용했습니다." : "엘레베이터 경로를 적용했습니다.");
  });
  $("resetPositionButton").addEventListener("click", resetPosition);
  $("moveButton").addEventListener("click", applyManualMove);
  $("magButton").addEventListener("click", applyMagneticCorrection);
  $("sensorButton").addEventListener("click", startSensors);
  $("calibrateButton").addEventListener("click", calibrateHeading);
  document.querySelectorAll("[data-native-floor]").forEach((button) => {
    button.addEventListener("click", () => setNativeMapFloor(Number(button.dataset.nativeFloor)));
  });
  document.querySelectorAll("[data-map-mode]").forEach((button) => {
    button.addEventListener("click", () => setMapMode(button.dataset.mapMode));
  });
}

async function init() {
  const version = Date.now();
  const [floor4Response, floor3Response] = await Promise.all([
    fetch(`./data/maps/floor-04.json?v=${version}`),
    fetch(`./data/maps/floor-03.json?v=${version}`)
  ]);
  const floor4 = await floor4Response.json();
  const floor3Override = await floor3Response.json();
  state.maps[4] = floor4;
  state.maps[3] = composeFloor3(floor4, floor3Override);
  populateTargets();
  bindEvents();
  setMapMode("2d");
  refresh("중앙 코어 복도를 출발 기준점으로 설정했습니다.");
}

init().catch((error) => {
  console.error(error);
  document.body.innerHTML = `<main><pre>${error.stack || error}</pre></main>`;
});

