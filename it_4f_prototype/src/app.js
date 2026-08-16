const state = {
  map: null,
  startX: 62,
  pdrX: 62,
  pdrY: 0,
  correctedX: 62,
  correctedY: 0,
  currentTarget: "4213",
  showLabels: true,
  log: []
};

const $ = (id) => document.getElementById(id);

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function mapToSvgX(x) {
  return 40 + x * 7.0;
}

function mapToSvgY(y) {
  return 230 - y * 7.0;
}

function distance(a, b) {
  return Math.hypot(a.x - b.x, a.y - b.y);
}

function findRoom(roomId) {
  return state.map.rooms.find((room) => room.id === roomId);
}

function findNearestMagnetic(total) {
  const candidates = state.map.magnetic_fingerprints
    .filter((fp) => fp.id !== "EV_INSIDE")
    .map((fp) => ({
      ...fp,
      score: Math.abs(total - fp.total_avg)
    }))
    .sort((a, b) => a.score - b.score);
  return candidates[0];
}

function snapToMainCorridor(pos) {
  return {
    x: clamp(pos.x, 0, 107),
    y: 0
  };
}

function routeToRoom(roomId) {
  const room = findRoom(roomId);
  if (!room) return [];
  return [
    { x: state.correctedX, y: 0 },
    { x: room.front_x, y: room.front_y },
    { x: room.x, y: room.y }
  ];
}

function pushLog(message) {
  const time = new Date().toLocaleTimeString("ko-KR", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit"
  });
  state.log.unshift(`[${time}] ${message}`);
  state.log = state.log.slice(0, 8);
  $("eventLog").textContent = state.log.join("\n");
}

function renderSvg() {
  const map = state.map;
  const target = findRoom(state.currentTarget);
  const route = routeToRoom(state.currentTarget);

  let html = "";

  html += `<line class="corridor" x1="${mapToSvgX(0)}" y1="${mapToSvgY(0)}" x2="${mapToSvgX(107)}" y2="${mapToSvgY(0)}" />`;
  html += `<text class="corridor-label" x="${mapToSvgX(52)}" y="${mapToSvgY(0) - 12}">4층 메인 복도</text>`;
  html += `<text class="corridor-label" x="${mapToSvgX(34)}" y="${mapToSvgY(0) + 28}">엘레베이터 기준 왼쪽: 4218 → 4228</text>`;
  html += `<text class="corridor-label" x="${mapToSvgX(88)}" y="${mapToSvgY(0) + 28}">엘레베이터 기준 오른쪽: 4213 → 4204</text>`;

  for (const room of map.rooms) {
    const w = room.id === "4120" ? 78 : 38;
    const h = 34;
    const x = mapToSvgX(room.x) - w / 2;
    const y = mapToSvgY(room.y) - h / 2;
    const isTarget = target && room.id === target.id;
    html += `<rect class="room ${isTarget ? "target-room" : ""}" x="${x}" y="${y}" width="${w}" height="${h}" rx="4" />`;
    if (state.showLabels || isTarget) {
      const label = room.id === "4120" ? "4120" : room.id;
      html += `<text class="room-label" x="${mapToSvgX(room.x)}" y="${mapToSvgY(room.y) + 4}">${label}</text>`;
    }
    html += `<line class="door-line" x1="${mapToSvgX(room.front_x)}" y1="${mapToSvgY(room.front_y)}" x2="${mapToSvgX(room.x)}" y2="${mapToSvgY(room.y) - (room.side === "upper" ? 17 : -17)}" />`;
  }

  for (const facility of map.facilities) {
    const x = mapToSvgX(facility.x);
    const y = mapToSvgY(facility.y);
    const symbol = facility.type === "elevator" ? "EV" : "계단";
    html += `<g class="facility">`;
    html += `<rect x="${x - 22}" y="${y - 16}" width="44" height="32" rx="4" />`;
    html += `<text x="${x}" y="${y + 5}">${symbol}</text>`;
    html += `</g>`;
  }

  if (route.length) {
    const points = route.map((p) => `${mapToSvgX(p.x)},${mapToSvgY(p.y)}`).join(" ");
    html += `<polyline class="route" points="${points}" />`;
  }

  html += `<circle class="pdr-point" cx="${mapToSvgX(state.pdrX)}" cy="${mapToSvgY(state.pdrY)}" r="8" />`;
  html += `<text class="point-label" x="${mapToSvgX(state.pdrX) + 11}" y="${mapToSvgY(state.pdrY) - 9}">PDR</text>`;

  html += `<circle class="corrected-point" cx="${mapToSvgX(state.correctedX)}" cy="${mapToSvgY(state.correctedY)}" r="8" />`;
  html += `<text class="point-label" x="${mapToSvgX(state.correctedX) + 11}" y="${mapToSvgY(state.correctedY) + 19}">보정</text>`;

  if (target) {
    html += `<circle class="target-dot" cx="${mapToSvgX(target.x)}" cy="${mapToSvgY(target.y)}" r="9" />`;
  }

  $("mapSvg").innerHTML = html;
}

function updateReadout(extra = "") {
  const target = findRoom(state.currentTarget);
  const targetDistance = target
    ? distance({ x: state.correctedX, y: state.correctedY }, { x: target.front_x, y: target.front_y }).toFixed(1)
    : "-";

  $("readout").innerHTML = `
    <div><strong>목적지</strong><span>${state.currentTarget}</span></div>
    <div><strong>PDR 위치</strong><span>x=${state.pdrX.toFixed(1)}, y=${state.pdrY.toFixed(1)}</span></div>
    <div><strong>보정 위치</strong><span>x=${state.correctedX.toFixed(1)}, y=${state.correctedY.toFixed(1)}</span></div>
    <div><strong>남은 복도 거리</strong><span>${targetDistance} m 좌표 기준</span></div>
    ${extra ? `<div><strong>최근 보정</strong><span>${extra}</span></div>` : ""}
  `;
}

function resetPosition() {
  state.pdrX = state.startX;
  state.pdrY = 0;
  state.correctedX = state.startX;
  state.correctedY = 0;
  pushLog("4층 엘레베이터 앞 위치로 초기화");
  renderSvg();
  updateReadout();
}

function applyPdr() {
  const steps = Number($("stepsInput").value || 0);
  const direction = $("directionSelect").value;
  const stepLength = state.map.routing.step_length_m;
  const dx = steps * stepLength * (direction === "left" ? -1 : 1);
  state.pdrX = clamp(state.pdrX + dx, 0, 107);
  state.pdrY = 0;
  state.correctedX = state.pdrX;
  state.correctedY = 0;
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
  const pdr = snapToMainCorridor({ x: state.pdrX, y: state.pdrY });
  const magnetic = snapToMainCorridor({ x: candidate.x, y: candidate.y });
  const magneticConfidence = clamp(1 - candidate.score / 12, 0.1, 0.75);
  const pdrWeight = 1 - magneticConfidence;

  state.correctedX = pdr.x * pdrWeight + magnetic.x * magneticConfidence;
  state.correctedY = 0;

  const message = `${candidate.label} 후보, 차이 ${candidate.score.toFixed(1)} μT, 자기장 가중치 ${(magneticConfidence * 100).toFixed(0)}%`;
  pushLog(`자기장 보정: ${message}`);
  renderSvg();
  updateReadout(message);
}

function populateRooms() {
  const select = $("targetSelect");
  select.innerHTML = state.map.rooms
    .map((room) => `<option value="${room.id}">${room.id}</option>`)
    .join("");
  select.value = state.currentTarget;
}

async function init() {
  const response = await fetch("./data/it_4f_map.json");
  state.map = await response.json();
  populateRooms();

  $("targetSelect").addEventListener("change", (event) => {
    state.currentTarget = event.target.value;
    pushLog(`목적지 변경: ${state.currentTarget}`);
    renderSvg();
    updateReadout();
  });

  $("moveButton").addEventListener("click", applyPdr);
  $("magButton").addEventListener("click", applyMagneticCorrection);
  $("resetButton").addEventListener("click", resetPosition);
  $("labelToggle").addEventListener("change", (event) => {
    state.showLabels = event.target.checked;
    renderSvg();
  });

  resetPosition();
}

init().catch((error) => {
  document.body.innerHTML = `<pre>${error.stack || error}</pre>`;
});
