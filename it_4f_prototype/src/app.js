const SVG_WIDTH = 980;
const SVG_HEIGHT = 500;
const MAP_MIN_X = 0;
let MAP_MAX_X = 135.407;
const MAP_LEFT = 54;
const MAP_RIGHT = 54;
const MAP_CENTER_Y = 220;
let X_SCALE = (SVG_WIDTH - MAP_LEFT - MAP_RIGHT) / (MAP_MAX_X - MAP_MIN_X);
const Y_SCALE = 8;
const pageParams = new URLSearchParams(window.location.search);
const isEmbedded = pageParams.get("embed") === "1";
const requestedFloor = Number(pageParams.get("floor"));
const initialFloor = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10].includes(requestedFloor) ? requestedFloor : 3;
const requestedTarget = pageParams.get("target");

const state = {
  map: null,
  startX: 70.804,
  startY: -3,
  pdrX: 70.804,
  pdrY: -3,
  correctedX: 70.804,
  correctedY: -3,
  currentTarget: "4213",
  floor: 4,
  showLabels: true,
  log: []
};

const $ = (id) => document.getElementById(id);

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function mapToSvgX(x) {
  // Keep the 2D map aligned with the 3D evacuation-plan rotation normalization.
  return MAP_LEFT + (MAP_MAX_X - x) * X_SCALE;
}

function mapToSvgY(y) {
  return MAP_CENTER_Y - y * Y_SCALE;
}

function distance(a, b) {
  return Math.hypot(a.x - b.x, a.y - b.y);
}

function findRoom(roomId) {
  return state.map.rooms.find((room) => room.id === roomId);
}

function hubJunction() {
  return state.map.routing.hub_junction;
}

function hubDepth() {
  const layout = state.map.layout_dimensions;
  return layout ? layout.hub_length + layout.corridor_width / 2 : 7.7;
}

function appendPoint(points, point) {
  const last = points.at(-1);
  if (!last || Math.abs(last.x - point.x) > 0.01 || Math.abs(last.y - point.y) > 0.01) {
    points.push(point);
  }
}

function snapToNetwork(pos) {
  const hub = hubJunction();
  if (pos.y < -0.5) {
    return {
      x: hub.x,
      y: clamp(pos.y, -hubDepth(), 0)
    };
  }
  return {
    x: clamp(pos.x, MAP_MIN_X, MAP_MAX_X),
    y: 0
  };
}

function findNearestMagnetic(total) {
  const pdr = { x: state.pdrX, y: state.pdrY };
  const candidates = state.map.magnetic_fingerprints
    .filter((fp) => fp.id !== "EV_INSIDE")
    .map((fp) => {
      const difference = Math.abs(total - fp.total_avg);
      const sigma = Math.max(fp.total_std || 4, 1);
      const spatialDistance = distance(pdr, fp);
      return {
        ...fp,
        difference,
        spatialDistance,
        score: difference / sigma + spatialDistance / 20
      };
    })
    .filter((fp) => fp.spatialDistance <= 24 || fp.id.startsWith("4F_EV_FRONT"))
    .sort((a, b) => a.score - b.score);

  return candidates[0];
}

function routeToRoom(roomId) {
  const room = findRoom(roomId);
  if (!room) return [];

  const hub = hubJunction();
  const points = [];
  appendPoint(points, { x: state.correctedX, y: state.correctedY });

  if (state.correctedY < -0.01) {
    appendPoint(points, { x: hub.x, y: state.correctedY });
    appendPoint(points, { x: hub.x, y: 0 });
  } else if (Math.abs(state.correctedY) > 0.01) {
    appendPoint(points, { x: state.correctedX, y: 0 });
  }

  appendPoint(points, { x: room.front_x, y: 0 });
  appendPoint(points, { x: room.front_x, y: room.y });
  return points;
}

function routeLength(points) {
  return points.slice(1).reduce((sum, point, index) => sum + distance(points[index], point), 0);
}

function pushLog(message) {
  if (!$("eventLog")) return;
  const time = new Date().toLocaleTimeString("ko-KR", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit"
  });
  state.log.unshift(`[${time}] ${message}`);
  state.log = state.log.slice(0, 8);
  $("eventLog").textContent = state.log.join("\n");
}

function renderRoom(room, target) {
  const width = Math.max((room.width || 4.5) * X_SCALE - 2, 28);
  const height = 50;
  const x = mapToSvgX(room.x) - width / 2;
  const y = mapToSvgY(room.y) - height / 2;
  const isTarget = target && room.id === target.id;
  const sideClass = room.side === "lower" ? "lower-room" : "upper-room";

  let html = `<g class="room-group ${sideClass}">`;
  html += `<rect class="room ${isTarget ? "target-room" : ""}" x="${x}" y="${y}" width="${width}" height="${height}" rx="3" />`;
  if (state.showLabels || isTarget) {
    html += `<text class="room-label" x="${mapToSvgX(room.x)}" y="${mapToSvgY(room.y) + 4}">${room.id}</text>`;
  }
  html += `<line class="door-line" x1="${mapToSvgX(room.front_x)}" y1="${mapToSvgY(room.front_y)}" x2="${mapToSvgX(room.x)}" y2="${mapToSvgY(room.y) - (room.side === "upper" ? 25 : -25)}" />`;
  html += "</g>";
  return html;
}

function renderFacility(facility) {
  const x = mapToSvgX(facility.x);
  // Keep the 2D core facilities on the same lower-row baseline as 4213.
  const y = mapToSvgY(facility.y < 0 ? -8 : facility.y);
  const dimensions = {
    elevator: { width: 26, height: 32 },
    stairs: { width: 30, height: 32 },
    restroom: { width: 18, height: 32 }
  };
  const { width, height } = dimensions[facility.type] || { width: 28, height: 32 };
  const labels = { elevator: "EV", stairs: "계단", restroom: "화장실" };
  const label = labels[facility.type] || facility.label;
  const labelY = facility.id === "4F_MAIN_RESTROOM" ? y + height / 2 + 13 : y + 5;
  return `
    <g class="facility ${facility.type}">
      <rect x="${x - width / 2}" y="${y - height / 2}" width="${width}" height="${height}" rx="4" />
      <text x="${x}" y="${labelY}">${label}</text>
    </g>
  `;
}

function renderSvg() {
  const map = state.map;
  const target = findRoom(state.currentTarget);
  const hub = hubJunction();
  const layout = map.layout_dimensions;
  const hubHalfWidth = layout.hub_width / 2;
  const hubLength = layout.hub_length;
  const coreStart = layout.corridor_width / 2;
  const coreEnd = coreStart + hubLength;

  let html = "";

  html += `<rect class="hub-zone" x="${mapToSvgX(hub.x + hubHalfWidth)}" y="${mapToSvgY(-coreStart)}" width="${layout.hub_width * X_SCALE}" height="${hubLength * Y_SCALE}" rx="3" />`;
  html += `<line class="corridor main-corridor" x1="${mapToSvgX(0)}" y1="${mapToSvgY(0)}" x2="${mapToSvgX(layout.main_length)}" y2="${mapToSvgY(0)}" />`;
  html += `<line class="corridor hub-corridor" x1="${mapToSvgX(hub.x)}" y1="${mapToSvgY(-coreEnd)}" x2="${mapToSvgX(hub.x)}" y2="${mapToSvgY(0)}" />`;
  html += `<path class="corner-wall" d="M ${mapToSvgX(hub.x - hubHalfWidth)} ${mapToSvgY(-coreStart)} V ${mapToSvgY(-coreEnd)} M ${mapToSvgX(hub.x + hubHalfWidth)} ${mapToSvgY(-coreStart)} V ${mapToSvgY(-coreEnd)}" />`;

  html += `<text class="corridor-label main-label" x="${mapToSvgX(hub.x)}" y="${mapToSvgY(0) - 13}">4층 메인 복도 · 코어 포함 ${layout.main_length.toFixed(2)}m</text>`;
  html += `<text class="corridor-label wing-label" x="${mapToSvgX(layout.left_corridor_length / 2)}" y="${mapToSvgY(0) + 30}">엘레베이터 기준 오른쪽 · 64.44m</text>`;
  html += `<text class="corridor-label wing-label" x="${mapToSvgX(hub.x + layout.hub_outer_width / 2 + layout.right_corridor_length / 2)}" y="${mapToSvgY(0) + 30}">엘레베이터 기준 왼쪽 · 58.24m</text>`;
  html += `<text class="side-label" x="${mapToSvgX(layout.left_corridor_length / 2)}" y="${mapToSvgY(-8) + 40}">오른쪽 복도 · 4213~4204</text>`;
  html += `<text class="side-label" x="${mapToSvgX(hub.x + layout.hub_outer_width / 2 + layout.right_corridor_length / 2)}" y="${mapToSvgY(8) - 32}">왼쪽 복도 · 4120~4128 / 4218~4228</text>`;

  for (const room of map.rooms) {
    html += renderRoom(room, target);
  }

  for (const facility of map.facilities) {
    html += renderFacility(facility);
  }

  $("mapSvg").innerHTML = html;
}

function updateReadout(extra = "") {
  if (!$("readout")) return;
  const route = routeToRoom(state.currentTarget);
  const targetDistance = route.length ? routeLength(route).toFixed(1) : "-";

  $("readout").innerHTML = `
    <div><strong>목적지</strong><span>${state.currentTarget}</span></div>
    <div><strong>PDR 위치</strong><span>x=${state.pdrX.toFixed(1)}, y=${state.pdrY.toFixed(1)}</span></div>
    <div><strong>보정 위치</strong><span>x=${state.correctedX.toFixed(1)}, y=${state.correctedY.toFixed(1)}</span></div>
    <div><strong>남은 안내 거리</strong><span>${targetDistance} m 좌표 기준</span></div>
    ${extra ? `<div><strong>최근 보정</strong><span>${extra}</span></div>` : ""}
  `;
}

function resetPosition() {
  state.pdrX = state.startX;
  state.pdrY = state.startY;
  state.correctedX = state.startX;
  state.correctedY = state.startY;
  pushLog("4층 엘레베이터 앞 허브로 초기화");
  renderSvg();
  updateReadout();
}

function advancePdr(distanceToMove, direction) {
  let remaining = distanceToMove;
  const hub = hubJunction();

  if (state.pdrY < 0) {
    const toMainCorridor = -state.pdrY;
    const verticalMove = Math.min(remaining, toMainCorridor);
    state.pdrX = hub.x;
    state.pdrY += verticalMove;
    remaining -= verticalMove;
  }

  if (remaining > 0) {
    const sign = direction === "left" ? -1 : 1;
    state.pdrX = clamp(state.pdrX + remaining * sign, MAP_MIN_X, MAP_MAX_X);
    state.pdrY = 0;
  }
}

function applyPdr() {
  const steps = Number($("stepsInput").value || 0);
  const direction = $("directionSelect").value;
  const stepLength = state.map.routing.step_length_m;
  advancePdr(steps * stepLength, direction);
  state.correctedX = state.pdrX;
  state.correctedY = state.pdrY;
  pushLog(`PDR 이동: ${direction === "left" ? "왼쪽" : "오른쪽"} ${steps}걸음`);
  renderSvg();
  updateReadout("PDR만 반영됨");
}

function applyMagneticCorrection() {
  const total = Number($("magInput").value || 0);
  if (!total) {
    pushLog("자기장 Total 값을 먼저 입력해야 함");
    return;
  }

  const candidate = findNearestMagnetic(total);
  if (!candidate) {
    pushLog("현재 PDR 위치 주변에 비교할 자기장 기준점이 없음");
    return;
  }

  const sigma = Math.max(candidate.total_std || 4, 1);
  const measurementFit = Math.exp(-0.5 * (candidate.difference / sigma) ** 2);
  const spatialFit = Math.exp(-candidate.spatialDistance / 20);
  const magneticConfidence = clamp(measurementFit * spatialFit * 0.75, 0.05, 0.7);
  const pdrWeight = 1 - magneticConfidence;
  const blended = {
    x: state.pdrX * pdrWeight + candidate.x * magneticConfidence,
    y: state.pdrY * pdrWeight + candidate.y * magneticConfidence
  };
  const corrected = snapToNetwork(blended);

  state.correctedX = corrected.x;
  state.correctedY = corrected.y;

  const message = `${candidate.label} 후보, 차이 ${candidate.difference.toFixed(1)} μT, 거리 ${candidate.spatialDistance.toFixed(1)} m, 가중치 ${(magneticConfidence * 100).toFixed(0)}%`;
  pushLog(`자기장 보정: ${message}`);
  renderSvg();
  updateReadout(message);
}

function populateRooms() {
  const select = $("targetSelect");
  if (!select) return;
  select.innerHTML = state.map.rooms
    .map((room) => `<option value="${room.id}">${room.label || room.id}</option>`)
    .join("");
  select.value = state.currentTarget;
}

function setHidden(element, hidden) {
  if (element) element.hidden = hidden;
}

function updateNotes(floor) {
  const notes = $("mapNotes");
  if (!notes) return;
  const items = floor === 1
    ? [
      "코어, 메인계단, 좌우 사이드계단과 화장실 통로는 위층과 같은 고정 좌표를 사용합니다.",
      "왼쪽복도 위쪽은 1128·1125·1122·1119, 아래쪽은 1228·1225·1221로 표시합니다.",
      "오른쪽복도 위쪽은 코어와 떨어진 1107·1105-2·1105-1·1103·1101 강의실 행입니다.",
      "오른쪽복도 아래쪽은 코어부터 1213·1210·1209·1204 순서이며 1213과 1210 사이 문 하나를 표시합니다.",
      "노란 박스에서는 야외 복도 위쪽만 하나의 행정실로 통합하고, 메인입구는 1119 오른쪽 빈 구간의 외벽에 표시합니다."
    ]
    : floor === 2
    ? [
      "코어, 메인계단, 좌우 사이드계단과 화장실 통로는 3층·4층과 같은 고정 좌표를 사용합니다.",
      "왼쪽복도 위쪽은 2128·2125·2122·2119, 아래쪽은 2228·2225·2221로 표시합니다.",
      "오른쪽복도 아래쪽은 코어부터 2211·2210·2210-1·2205·2204 순서입니다.",
      "2107은 개방공간이며 S-space, ㄷ자 책상 학습공간, TDM과 증축부 진입 동선으로 이어집니다.",
      "진입구는 오른쪽 메인복도에서 안쪽으로 들어가 단일 기둥과 TDM 사이를 통과합니다."
    ]
    : floor === 3
    ? [
      "3층은 4층 공통틀 위에 자유공간, 증축부 복도, IT홀, 3104-1·2를 추가한 구조입니다.",
      "3203 라인의 첫 입구만 자유공간으로 열리고, 나머지 경계는 벽으로 막힌 것으로 표시합니다.",
      "IT홀 입구와 증축부 복도 흐름은 피난안내도 기준을 우선합니다."
    ]
    : floor === 5
    ? [
      "5층은 빨간박스 공통 본동 틀을 사용하고, 기존 노란 증축 외형과 복도 위 빈 공간을 야외공간으로 통합 표시합니다.",
      "코어, 화장실, 엘레베이터, 메인계단, 좌우 사이드계단은 4층과 같은 고정 좌표를 유지합니다.",
      "5111 끝선은 야외공간 왼쪽선에 맞추고, 야외 출입문은 복도 위쪽 경계와 오른쪽 복도 끝에 표시합니다.",
      "5205와 5205-1은 편의점으로 통합 표기합니다.",
      "5227 계열 등 사진 판독이 흐린 구간은 추후 현장 확인 후 세부 조정 대상으로 둡니다."
    ]
    : floor === 6
    ? [
      "6층부터 10층까지는 4층 공통 본동 틀을 그대로 사용하고, 코어와 좌우 계단 위치를 고정합니다.",
      "왼쪽복도 위쪽 강의실은 메인 화장실 오른쪽선에서, 아래쪽 강의실은 코어 왼쪽선에서 시작합니다.",
      "오른쪽복도 위쪽 강의실은 메인계단 왼쪽선에서, 아래쪽 강의실은 코어 오른쪽선에서 시작합니다.",
      "6층은 증축부 없이 호실 번호와 방 폭만 피난안내도에 맞춰 조정하는 표준층입니다."
    ]
    : floor === 7
    ? [
      "7층은 6층에서 확정한 공통 코어·계단 틀을 그대로 사용한 2D 초안입니다.",
      "왼쪽 위 행은 메인 화장실 오른쪽선, 오른쪽 위 행은 메인계단 왼쪽선에 맞춥니다.",
      "7202는 오른쪽 계단 옆 통로를 통해 진입하는 하나의 강의실로 표시합니다.",
      "호실 순서와 통로를 통한 7202 진입 구조는 제공된 7층 피난안내도 사진으로 대조했습니다."
    ]
    : floor === 8
    ? [
      "8층은 6층에서 확정한 공통 코어·계단 틀을 그대로 사용한 2D 구조도입니다.",
      "좌측 위 행은 메인 화장실 오른쪽선, 우측 위 행은 메인계단 왼쪽선에서 시작합니다.",
      "8210은 8108 끝선에 맞추고, 8202는 오른쪽 계단 옆 통로를 통해 진입합니다.",
      "호실 순서와 통로를 통한 8202 진입 구조는 제공된 8층 피난안내도 사진으로 대조했습니다."
    ]
    : [
      "4층은 긴 메인 복도와 아래쪽 엘레베이터·계단 허브가 연결되는 구조로 단순화했습니다.",
      "4218~4228 및 4120~4128은 엘레베이터에서 내려 왼쪽, 4213~4204는 오른쪽 구간입니다.",
      "방 폭과 위치는 피난안내도 비율과 GLB 복도 길이를 함께 반영한 1차 정합값입니다."
    ];
  notes.innerHTML = items.map((item) => `<li>${item}</li>`).join("");
}

async function loadInlinePlan(floor) {
  const host = $(`floor${floor}Host`);
  if (!host || host.dataset.loaded === "true") return;
  const [htmlResponse, cssResponse, floorCssResponse] = await Promise.all([
  fetch(`./floor${floor === 10 ? 6 : floor}-plan.html?v=${floor === 10 ? "floor10-full-core-stair-1" : floor === 1 || floor === 2 ? "right-stair-layout-3" : floor === 3 ? "right-stair-extension-align-1" : floor === 5 ? "right-stair-layout-5f-1" : floor === 7 ? "floor7-evac-verified-1" : "embed-source-7"}`),
    fetch("./src/floor3-plan.css?v=right-stair-extension-align-1"),
    floor === 1
    ? fetch("./src/floor1-plan.css?v=right-stair-layout-3")
      : floor === 2
      ? fetch("./src/floor2-plan.css?v=right-stair-layout-3")
        : floor === 5
          ? fetch("./src/floor5-plan.css?v=right-stair-layout-5f-1")
          : floor >= 6
            ? fetch("./src/floor6-plan.css?v=standard-shell-6f-1")
          : Promise.resolve(null)
  ]);
  let html = await htmlResponse.text();
  if (floor === 10) {
    const labels = {
      "6128":"10128", "6126":"10126", "6125":"10125", "6123":"10123", "6122":"10122", "6120":"10120", "6119":"10119", "6117":"10117",
      "6228":"10228", "6226":"10228-1", "6225":"10225", "6221":"10221",
      "6114":"10114", "6112":"10112", "6111":"10111", "6109":"10109", "6108-1":"10106", "6108":"10108", "6103":"10103",
      "6213":"10213", "6212":"10212", "6210":"10210", "6203":"10206", "6202":"10202", "6층":"10층"
    };
    Object.entries(labels).forEach(([from, to]) => { html = html.split(from).join(to); });
    html = html.split("10108-1").join("10106");
  }
  const css = await cssResponse.text();
  const floorCss = floorCssResponse ? await floorCssResponse.text() : "";
  const doc = new DOMParser().parseFromString(html, "text/html");
  const svg = doc.querySelector("#floorPlan");
  if (!svg) {
    host.innerHTML = `<div class="loading-note">${floor}층 2D 지도를 찾지 못했습니다.</div>`;
    return;
  }
  if (floor === 9) {
    const endFacilities = svg.querySelector(".end-facilities");
    if (endFacilities && !endFacilities.querySelector(".floor9-stair-detail")) {
      endFacilities.insertAdjacentHTML("beforeend", `
        <g class="floor9-stair-detail">
          <text class="floor6-stair-zone" transform="translate(1344 323) rotate(-90)">계단 입구</text>
          <path class="stair-step" d="M1359 304h60m-60 8h60m-60 8h60m-60 8h60m-60 8h60m-60 8h60" />
          <text class="floor6-stair-zone" transform="translate(1389 323) rotate(-90)">12+12계단</text>
          <text class="floor6-stair-zone" transform="translate(1443 323) rotate(-90)">중간참</text>
        </g>
      `);
    }
  }
  const inlineHeight = floor === 1 ? 1030 : floor === 2 ? 1055 : floor === 5 ? 1180 : floor >= 6 ? 780 : 920;
  const inlineWidth = floor >= 6 ? 1500 : 1380;
  svg.setAttribute("viewBox", floor === 1 ? "0 45 1380 1030" : floor === 2 ? "0 35 1380 1055" : floor === 5 ? "0 0 1380 1180" : floor >= 6 ? "0 0 1500 780" : "0 60 1380 920");
  svg.removeAttribute("aria-labelledby");
  svg.setAttribute("aria-label", `IT융합대학 ${floor}층 평면 구조`);
  const style = document.createElementNS("http://www.w3.org/2000/svg", "style");
  style.textContent = `${css}\n${floorCss}\n#floorPlan{width:100%;height:auto;aspect-ratio:${inlineWidth}/${inlineHeight};}${floor === 10 ? "\n#floorPlan .floor6-room-10202{fill:#f4d7ef!important;}#floorPlan .floor6-10202-boundary{fill:none;stroke:#697888;stroke-width:2.5;}#floorPlan .floor6-10202-door{stroke:#66c8ea;stroke-width:6;stroke-linecap:round;}#floorPlan .floor6-10202-label{fill:#834570;font-size:12px;font-weight:850;}" : ""}`;
  svg.insertBefore(style, svg.firstChild);
  host.replaceChildren(svg);
  host.dataset.loaded = "true";
}

function setFloorView(floor) {
  state.floor = floor;
  document.querySelectorAll("[data-floor-tab]").forEach((button) => {
    const active = button.dataset.floorTab === String(floor);
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", String(active));
  });
  document.querySelectorAll("[data-floor-view]").forEach((view) => {
    view.hidden = view.dataset.floorView !== String(floor);
  });
  setHidden($("targetField"), floor !== 4);
  setHidden($("resetButton"), floor !== 4);
  setHidden($("labelToggle")?.closest("label"), floor !== 4);
  if ($("pageSubtitle")) {
    $("pageSubtitle").textContent = floor === 1
      ? "1층 본동 강의실과 야외 복도, 행정실 배치를 확인합니다."
      : floor === 2
        ? "2층 2D 구조 검토도를 메인 2D 화면에서 함께 확인합니다."
      : floor === 3
        ? "3층 2D 구조 검토도를 메인 2D 화면에서 함께 확인합니다."
        : floor === 5
        ? "5층 공통 본동 틀 안의 오른쪽 라인, 야외공간, 야외문 배치를 확인합니다."
        : floor === 6
        ? "6층 표준 본동의 고정 코어와 강의실 행 시작선을 확인합니다."
        : floor === 7
        ? "7층 표준 본동의 호실 폭·끝선·7202 통로 진입 구조 초안을 확인합니다."
        : floor === 8
        ? "8층 표준 본동의 호실 폭·끝선·8202 통로 진입 구조를 확인합니다."
        : "4층 평면 배치와 목적지 경로를 확인합니다.";
  }
  if ($("mapBadge")) $("mapBadge").textContent = floor === 1 ? "1F structure" : floor === 2 ? "2F structure" : floor === 3 ? "3F structure" : floor === 5 ? "5F structure" : floor === 6 ? "6F structure" : floor === 7 ? "7F draft" : floor === 8 ? "8F structure" : "4F map graph v0.4";
  if (floor === 1 || floor === 2 || floor === 3 || floor === 5 || floor >= 6) loadInlinePlan(floor);
  updateNotes(floor);
}

async function init() {
  const response = await fetch("./data/it_4f_map.json");
  state.map = await response.json();
  if (requestedTarget && findRoom(requestedTarget)) state.currentTarget = requestedTarget;
  if (isEmbedded) document.body.classList.add("embedded-map");
  MAP_MAX_X = state.map.layout_dimensions.main_length;
  X_SCALE = (SVG_WIDTH - MAP_LEFT - MAP_RIGHT) / (MAP_MAX_X - MAP_MIN_X);
  const start = state.map.routing.start_position;
  state.startX = start.x;
  state.startY = start.y;
  $("mapSvg").setAttribute("viewBox", `0 0 ${SVG_WIDTH} ${SVG_HEIGHT}`);
  populateRooms();

  $("targetSelect")?.addEventListener("change", (event) => {
    state.currentTarget = event.target.value;
    pushLog(`목적지 변경: ${state.currentTarget}`);
    renderSvg();
    updateReadout();
  });

  $("moveButton")?.addEventListener("click", applyPdr);
  $("magButton")?.addEventListener("click", applyMagneticCorrection);
  $("resetButton")?.addEventListener("click", resetPosition);
  $("labelToggle")?.addEventListener("change", (event) => {
    state.showLabels = event.target.checked;
    renderSvg();
  });
  document.querySelectorAll("[data-floor-tab]").forEach((button) => {
    button.addEventListener("click", () => setFloorView(Number(button.dataset.floorTab)));
  });

  resetPosition();
  setFloorView(initialFloor);
}

init().catch((error) => {
  document.body.innerHTML = `<pre>${error.stack || error}</pre>`;
});
