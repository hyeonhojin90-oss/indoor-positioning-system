import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";

const state = {
  data: null,
  scene: null,
  camera: null,
  renderer: null,
  controls: null,
  roomGroup: null,
  labelGroup: null,
  hintGroup: null,
  routeGroup: null,
  markerGroup: null,
  targetId: "4213"
};

const palette = {
  floor: 0xf0f3f6,
  corridor: 0xe3e9f1,
  wall: 0xcbd5e1,
  room: 0xf8fafc,
  facility: 0xdbeafe,
  stair: 0xe0e7ff,
  route: 0xc98212,
  target: 0xef4444,
  current: 0x16a34a,
  scanLeft: 0x8ec5ff,
  scanRight: 0xf7c878
};

const $ = (id) => document.getElementById(id);
const HUB_MAP_X = 62;
const HUB_X = mapX(HUB_MAP_X);
const HUB_START_Z = 0;
const HUB_END_Z = 15;
const EV_FRONT_Z = 9.2;

function mapX(x) {
  return x - 53.5;
}

function mapZ(y) {
  return -y;
}

function makeMat(color, roughness = 0.88, opacity = 1) {
  return new THREE.MeshStandardMaterial({
    color,
    roughness,
    metalness: 0,
    transparent: opacity < 1,
    opacity
  });
}

function addBox(group, { x, z, w, d, h, y = h / 2, color, opacity = 1, name = "" }) {
  const mesh = new THREE.Mesh(
    new THREE.BoxGeometry(w, h, d),
    makeMat(color, 0.9, opacity)
  );
  mesh.position.set(x, y, z);
  mesh.name = name;
  mesh.castShadow = true;
  mesh.receiveShadow = true;
  group.add(mesh);
  return mesh;
}

function addWall(group, x, z, w, d) {
  addBox(group, { x, z, w, d, h: 0.8, color: palette.wall, opacity: 0.95 });
}

function addElevatorHub() {
  addBox(state.scene, {
    x: HUB_X,
    z: 7.6,
    w: 11.2,
    d: 15.2,
    h: 0.13,
    y: 0.025,
    color: palette.corridor,
    name: "elevator-stair-hub-corridor"
  });

  addWall(state.scene, HUB_X - 5.7, 8.2, 0.22, 13.2);
  addWall(state.scene, HUB_X + 5.7, 8.2, 0.22, 13.2);
  addWall(state.scene, HUB_X, HUB_END_Z, 11.3, 0.22);

  addBox(state.scene, {
    x: HUB_X - 3.7,
    z: EV_FRONT_Z,
    w: 3.3,
    d: 4.8,
    h: 1.35,
    color: palette.facility,
    name: "4f-elevator-bank"
  });
  addLabel("엘레베이터", HUB_X - 3.7, EV_FRONT_Z, 2.2, 0.62, "#1e3a8a");

  addBox(state.scene, {
    x: HUB_X + 3.7,
    z: EV_FRONT_Z,
    w: 3.5,
    d: 4.8,
    h: 1.25,
    color: palette.stair,
    name: "4f-hub-stairs"
  });
  addLabel("계단", HUB_X + 3.7, EV_FRONT_Z, 2.05, 0.72, "#312e81");

  addBox(state.scene, {
    x: HUB_X,
    z: HUB_END_Z - 0.65,
    w: 6.2,
    d: 0.32,
    h: 1.15,
    color: 0xd8e7f0,
    opacity: 0.72,
    name: "hub-window-end"
  });
  addLabel("창가/게시판 방향", HUB_X, HUB_END_Z - 1.45, 1.55, 0.58, "#475569");
  addLabel("엘레베이터 허브", HUB_X, 5.0, 1.35, 0.7, "#1f2937");
}

function makeTextSprite(text, scale = 1, color = "#1f2937") {
  const canvas = document.createElement("canvas");
  const ctx = canvas.getContext("2d");
  canvas.width = 256;
  canvas.height = 96;
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.font = "700 34px Arial";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillStyle = color;
  ctx.fillText(text, canvas.width / 2, canvas.height / 2);

  const texture = new THREE.CanvasTexture(canvas);
  const material = new THREE.SpriteMaterial({ map: texture, transparent: true });
  const sprite = new THREE.Sprite(material);
  sprite.scale.set(4.8 * scale, 1.8 * scale, 1);
  return sprite;
}

function addLabel(text, x, z, y = 1.4, scale = 0.8, color = "#1f2937") {
  const sprite = makeTextSprite(text, scale, color);
  sprite.position.set(x, y, z);
  state.labelGroup.add(sprite);
  return sprite;
}

function addRoom(room) {
  const width = room.id === "4120" ? 9.5 : 4.8;
  const depth = room.side === "upper" ? 4.4 : 4.4;
  const x = mapX(room.x);
  const z = mapZ(room.y);
  const target = room.id === state.targetId;
  addBox(state.roomGroup, {
    x,
    z,
    w: width,
    d: depth,
    h: target ? 0.78 : 0.55,
    color: target ? 0xffd4d4 : palette.room,
    name: room.id
  });
  addWall(state.roomGroup, x, z + (room.side === "upper" ? -2.35 : 2.35), width, 0.18);
  addWall(state.roomGroup, x - width / 2, z, 0.18, depth);
  addWall(state.roomGroup, x + width / 2, z, 0.18, depth);
  addLabel(room.id === "4120" ? "4120" : room.id, x, z, 1.15, target ? 0.9 : 0.7, target ? "#b91c1c" : "#1f2937");
}

function addFacility(facility) {
  if (facility.id === "4F_EV_FRONT" || facility.id === "4F_CENTER_STAIRS") {
    return;
  }
  const x = mapX(facility.x);
  const z = mapZ(facility.y);
  const isElevator = facility.type === "elevator";
  addBox(state.scene, {
    x,
    z,
    w: isElevator ? 4.5 : 5.5,
    d: isElevator ? 3.8 : 3.4,
    h: 1.2,
    color: isElevator ? palette.facility : palette.stair,
    name: facility.id
  });
  addLabel(isElevator ? "EV" : "계단", x, z, 2.0, 0.75, "#1e3a8a");
}

function addRoute() {
  state.routeGroup.clear();
  state.markerGroup.clear();
  const room = state.data.rooms.find((item) => item.id === state.targetId);
  if (!room) return;

  const start = new THREE.Vector3(HUB_X, 0.16, EV_FRONT_Z);
  const junction = new THREE.Vector3(mapX(62), 0.16, mapZ(0));
  const front = new THREE.Vector3(mapX(room.front_x), 0.16, mapZ(room.front_y));
  const dest = new THREE.Vector3(mapX(room.x), 0.16, mapZ(room.y));
  const points = [start, junction, front, dest];
  const curve = new THREE.CatmullRomCurve3(points);
  const tube = new THREE.Mesh(
    new THREE.TubeGeometry(curve, 32, 0.18, 10, false),
    makeMat(palette.route, 0.7)
  );
  tube.name = "route";
  state.routeGroup.add(tube);

  addBox(state.markerGroup, {
    x: start.x,
    z: start.z,
    w: 1.1,
    d: 1.1,
    h: 0.8,
    color: palette.current,
    name: "current-position"
  });
  addLabel("현재", start.x, start.z - 1.9, 1.45, 0.7, "#166534");

  addBox(state.markerGroup, {
    x: dest.x,
    z: dest.z,
    w: 1.35,
    d: 1.35,
    h: 1.0,
    color: palette.target,
    name: "target-position"
  });
  addLabel("목적지", dest.x, dest.z - 1.9, 1.55, 0.7, "#b91c1c");
}

function addScanHints() {
  state.hintGroup.clear();
  addBox(state.hintGroup, {
    x: mapX(34),
    z: 0,
    w: 48,
    d: 2.8,
    h: 0.08,
    y: 0.08,
    color: palette.scanLeft,
    opacity: 0.35,
    name: "left-scan-reference"
  });
  addLabel("스캔 참고: 엘레베이터 기준 왼쪽 / 4218 방향", mapX(34), 3.5, 0.85, 0.58, "#1e3a8a");

  addBox(state.hintGroup, {
    x: mapX(88),
    z: 0,
    w: 39,
    d: 2.8,
    h: 0.08,
    y: 0.08,
    color: palette.scanRight,
    opacity: 0.36,
    name: "right-scan-reference"
  });
  addLabel("스캔 참고: 엘레베이터 기준 오른쪽 / 4213 방향", mapX(88), 3.5, 0.85, 0.58, "#92400e");
}

function buildScene() {
  state.scene.clear();
  state.scene.background = new THREE.Color(0xf5f7fa);

  const ambient = new THREE.HemisphereLight(0xffffff, 0xcbd5e1, 2.2);
  state.scene.add(ambient);

  const sun = new THREE.DirectionalLight(0xffffff, 2.4);
  sun.position.set(10, 24, 18);
  sun.castShadow = true;
  state.scene.add(sun);

  state.roomGroup = new THREE.Group();
  state.labelGroup = new THREE.Group();
  state.hintGroup = new THREE.Group();
  state.routeGroup = new THREE.Group();
  state.markerGroup = new THREE.Group();
  state.scene.add(state.roomGroup, state.hintGroup, state.routeGroup, state.markerGroup, state.labelGroup);

  addBox(state.scene, { x: 0, z: 3, w: 116, d: 38, h: 0.18, y: -0.09, color: palette.floor, name: "floor-base" });
  addBox(state.scene, { x: 0, z: 0, w: 107, d: 3.6, h: 0.12, y: 0.02, color: palette.corridor, name: "main-corridor" });
  addElevatorHub();

  addWall(state.scene, 0, -2.1, 107, 0.22);
  addWall(state.scene, mapX(29), 2.1, 58, 0.22);
  addWall(state.scene, mapX(88), 2.1, 36, 0.22);
  addWall(state.scene, mapX(0), 0, 0.22, 4.5);
  addWall(state.scene, mapX(107), 0, 0.22, 4.5);

  for (const room of state.data.rooms) addRoom(room);
  for (const facility of state.data.facilities) addFacility(facility);

  addScanHints();
  addRoute();

  state.hintGroup.visible = $("scanHintToggle").checked;
  state.labelGroup.visible = $("labelToggle").checked;
}

function resizeRenderer() {
  const canvas = $("clayCanvas");
  const rect = canvas.getBoundingClientRect();
  state.camera.aspect = rect.width / rect.height;
  state.camera.updateProjectionMatrix();
  state.renderer.setSize(rect.width, rect.height, false);
}

function setIsoView() {
  state.camera.position.set(4, 54, 54);
  state.controls.target.set(0, 0, 0);
  state.controls.update();
}

function setTopView() {
  state.camera.position.set(0, 88, 0.01);
  state.controls.target.set(0, 0, 0);
  state.controls.update();
}

function populateTargets() {
  const select = $("targetSelect");
  select.innerHTML = state.data.rooms.map((room) => `<option value="${room.id}">${room.id}</option>`).join("");
  select.value = state.targetId;
}

function updateDetail() {
  const room = state.data.rooms.find((item) => item.id === state.targetId);
  const dir = room.x < 62 ? "엘레베이터에서 내려 왼쪽, 4218 방향" : "엘레베이터에서 내려 오른쪽, 4213/4210 방향";
  $("detail").innerHTML = `
    <strong>${state.targetId} 안내 기준</strong>
    ${dir}<br>
    출발점은 4층 엘레베이터 허브 안쪽이고, 짧은 허브 복도를 지나 메인 복도로 나온 뒤 좌우 복도 방향으로 이동하는 방식으로 표시했다.
  `;
}

async function init() {
  const response = await fetch("./data/it_4f_map.json");
  state.data = await response.json();

  state.scene = new THREE.Scene();
  state.camera = new THREE.PerspectiveCamera(48, 1, 0.1, 500);
  state.renderer = new THREE.WebGLRenderer({ canvas: $("clayCanvas"), antialias: true });
  state.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  state.renderer.shadowMap.enabled = true;

  state.controls = new OrbitControls(state.camera, state.renderer.domElement);
  state.controls.enableDamping = true;
  state.controls.minDistance = 18;
  state.controls.maxDistance = 130;
  state.controls.maxPolarAngle = Math.PI / 2.05;

  populateTargets();
  buildScene();
  updateDetail();
  resizeRenderer();
  setIsoView();

  $("targetSelect").addEventListener("change", (event) => {
    state.targetId = event.target.value;
    buildScene();
    updateDetail();
  });

  $("labelToggle").addEventListener("change", (event) => {
    state.labelGroup.visible = event.target.checked;
  });

  $("scanHintToggle").addEventListener("change", (event) => {
    state.hintGroup.visible = event.target.checked;
  });

  $("viewIso").addEventListener("click", setIsoView);
  $("viewTop").addEventListener("click", setTopView);
  window.addEventListener("resize", resizeRenderer);

  function animate() {
    requestAnimationFrame(animate);
    state.controls.update();
    state.renderer.render(state.scene, state.camera);
  }
  animate();
}

init().catch((error) => {
  const message = error && (error.stack || error.message) ? (error.stack || error.message) : String(error);
  document.body.innerHTML = `
    <main class="app-shell">
      <div class="panel" style="padding:16px; color:#991b1b; line-height:1.6;">
        <strong>3D 지도를 불러오지 못했어.</strong><br>
        <pre style="white-space:pre-wrap;">${message}</pre>
      </div>
    </main>
  `;
});
