import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";

const pageParams = new URLSearchParams(window.location.search);
const FLOORS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10];
const COMBINED_FLOORS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10];
const COMBINED_FLOOR_GAP = 4.25;
const COMBINED_LABEL = "1F-10F";
const COMBINED_LONG_LABEL = "1F+2F+3F+4F+5F+6F+7F+8F+9F+10F";
const DEFAULT_TARGET_BY_FLOOR = {
  1: "1119",
  2: "2107",
  3: "3108",
  4: "4213",
  5: "5117",
  6: "6114",
  7: "7114",
  8: "8114",
  9: "9114",
  10: "10114"
};

const state = {
  data: null,
  maps: {},
  floor: 4,
  scene: null,
  camera: null,
  renderer: null,
  controls: null,
  roomGroup: null,
  labelGroup: null,
  hintGroup: null,
  routeGroup: null,
  markerGroup: null,
  viewMode: "iso",
  floorYOffset: 0,
  combinedLayerRendering: false,
  targetId: "4213",
  stairPreview: null
};

function defaultTargetForFloor(floor) {
  return DEFAULT_TARGET_BY_FLOOR[floor] || DEFAULT_TARGET_BY_FLOOR[3];
}

function combinedCenterY() {
  return ((COMBINED_FLOORS.length - 1) * COMBINED_FLOOR_GAP) / 2;
}

const palette = {
  floor: 0xe6ebf1,
  corridor: 0xc5d6e5,
  wall: 0xaebac8,
  room: 0xf8fafc,
  roomFloor: 0xdfe5eb,
  facility: 0xdbeafe,
  stair: 0xe0e7ff,
  door: 0x64748b,
  glass: 0x9bd7e8,
  trim: 0x94a3b8,
  route: 0xc98212,
  target: 0xef4444,
  current: 0x16a34a,
  verticalLink: 0x7c3aed,
  verticalLinkElevator: 0x0ea5e9,
  scanLeft: 0x8ec5ff,
  scanRight: 0xf7c878,
  restroom: 0xd9eee8
};

const $ = (id) => document.getElementById(id);
const HUB_MAP_X = 70.804;
const HUB_START_Z = 0;
const HUB_END_Z = 9.2;
const EV_FRONT_Z = 4.12;
const DEFAULT_LAYOUT = {
  main_length: 135.407,
  main_depth: 18.7,
  corridor_width: 2.34,
  room_depth: 7.9,
  hub_width: 2.76,
  hub_length: 9.2,
  hub_outer_width: 12.734,
  left_corridor_length: 64.437,
  right_corridor_length: 58.236
};

function mapX(x) {
  // Evacuation-plan photos were captured upside down. After normalizing them
  // by 180 degrees, increasing map X runs from the screen's right to left.
  return DEFAULT_LAYOUT.main_length / 2 - x;
}

const HUB_X = mapX(HUB_MAP_X);

function mapZ(y) {
  return -y;
}

function makeMat(color, roughness = 0.88, opacity = 1, metalness = 0) {
  return new THREE.MeshStandardMaterial({
    color,
    roughness,
    metalness,
    transparent: opacity < 1,
    opacity
  });
}

function addBox(group, { x, z, w, d, h, y = h / 2, color, opacity = 1, metalness = 0, name = "" }) {
  const dimensions = { x, z, w, d, h, y };
  if (!Object.values(dimensions).every(Number.isFinite)) {
    console.error(`Skipped invalid 3D geometry: ${JSON.stringify({ name, dimensions, floor: state.floor })}`);
    return null;
  }
  const mesh = new THREE.Mesh(
    new THREE.BoxGeometry(w, h, d),
    makeMat(color, metalness ? 0.32 : 0.9, opacity, metalness)
  );
  const layerOffset = [state.scene, state.roomGroup, state.hintGroup, state.routeGroup, state.markerGroup].includes(group)
    ? state.floorYOffset || 0
    : 0;
  mesh.position.set(x, y + layerOffset, z);
  mesh.name = name;
  mesh.castShadow = !state.combinedLayerRendering;
  mesh.receiveShadow = !state.combinedLayerRendering;
  group.add(mesh);
  return mesh;
}

function addWall(group, x, z, w, d, options = {}) {
  const height = options.height ?? 2.75;
  addBox(group, {
    x,
    z,
    w,
    d,
    h: height,
    y: options.y ?? height / 2,
    color: options.color ?? palette.wall,
    opacity: options.opacity ?? 0.98,
    name: options.name ?? "wall"
  });
}

function addPreviewBox(group, { x, y, z, w, h, d, color, opacity = 1, name = "" }) {
  const mesh = new THREE.Mesh(
    new THREE.BoxGeometry(w, h, d),
    makeMat(color, 0.78, opacity)
  );
  mesh.position.set(x, y, z);
  mesh.name = name;
  mesh.castShadow = true;
  mesh.receiveShadow = true;
  group.add(mesh);
  return mesh;
}

function buildInterfloorStairModule({
  group,
  addPart,
  name,
  width,
  depth,
  floorGap,
  upperColor = 0x60a5fa,
  lowerColor = 0x86efac,
  landingColor = 0x4338ca,
  padColor = 0xe0e7ff,
  addArrows = true,
  swapFlights = false,
  accessLandingDepth = null,
  addAccessLandings = true,
  runStartZ = null
}) {
  const stepCount = 12;
  const landingY = floorGap / 2;
  const landingThickness = 0.18;
  const innerWidth = Math.max(width - 0.3, 1.5);
  const laneGap = Math.min(Math.max(innerWidth * 0.06, 0.1), 0.2);
  const laneWidth = Math.max((innerWidth - laneGap) / 2, 0.62);
  const laneOffset = laneWidth / 2 + laneGap / 2;
  const nearInset = Math.min(Math.max(depth * 0.09, 0.28), 0.56);
  const landingDepth = Math.min(Math.max(depth * 0.18, 0.52), 1.05);
  const baseNearZ = -depth / 2 + nearInset;
  const runOffsetZ = Number.isFinite(runStartZ) ? runStartZ - baseNearZ : 0;
  const nearZ = baseNearZ + runOffsetZ;
  const farZ = depth / 2 - landingDepth - 0.12 + runOffsetZ;
  const landingZ = depth / 2 - landingDepth / 2 - 0.05 + runOffsetZ;
  const runLength = Math.max(farZ - nearZ, 1.15);
  const treadDepth = runLength / stepCount + 0.03;
  const lowerFloorTop = 0.14;
  const accessDepth = accessLandingDepth ?? Math.max(nearInset * 0.95, 0.36);
  const blueX = swapFlights ? laneOffset : -laneOffset;
  const greenX = -blueX;

  addPart({
    x: 0,
    z: landingZ,
    w: innerWidth,
    d: landingDepth,
    h: landingThickness,
    y: landingY - landingThickness / 2,
    color: landingColor,
    name: `${name}-half-landing`
  });

  const stepThickness = 0.1;
  const upperRise = (floorGap - landingY) / stepCount;
  const lowerRise = (landingY - lowerFloorTop) / stepCount;
  for (let index = 0; index < stepCount; index += 1) {
    const centerProgress = (index + 0.5) / stepCount;
    const edgeProgress = (index + 1) / stepCount;
    const blueTop = floorGap - upperRise * index;
    const greenTop = landingY - lowerRise * index;
    const blueZ = nearZ + runLength * centerProgress;
    const greenZ = farZ - runLength * centerProgress;

    addPart({
      x: blueX,
      z: blueZ,
      w: laneWidth - 0.06,
      d: treadDepth,
      h: stepThickness,
      y: blueTop - stepThickness / 2,
      color: upperColor,
      name: `${name}-4f-to-half-step-${index + 1}`
    });
    addPart({
      x: blueX,
      z: nearZ + runLength * edgeProgress,
      w: laneWidth - 0.06,
      d: 0.055,
      h: upperRise + 0.02,
      y: blueTop - upperRise / 2,
      color: upperColor,
      name: `${name}-4f-to-half-riser-${index + 1}`
    });
    addPart({
      x: greenX,
      z: greenZ,
      w: laneWidth - 0.06,
      d: treadDepth,
      h: stepThickness,
      y: greenTop - stepThickness / 2,
      color: lowerColor,
      name: `${name}-half-to-3f-step-${index + 1}`
    });
    addPart({
      x: greenX,
      z: farZ - runLength * edgeProgress,
      w: laneWidth - 0.06,
      d: 0.055,
      h: lowerRise + 0.02,
      y: greenTop - lowerRise / 2,
      color: lowerColor,
      name: `${name}-half-to-3f-riser-${index + 1}`
    });
  }

  if (addAccessLandings) {
    [-1, 1].forEach((floorDirection) => {
      addPart({
        x: 0,
        z: nearZ - nearInset * 0.32,
        w: innerWidth,
        d: accessDepth,
        h: 0.12,
        y: floorDirection > 0 ? floorGap - 0.06 : 0.06,
        color: padColor,
        name: `${name}-${floorDirection > 0 ? "4f" : "3f"}-access-landing`
      });
    });
  }

  if (addArrows) {
    const upperStart = new THREE.Vector3(blueX, floorGap + 0.16, nearZ);
    const upperEnd = new THREE.Vector3(blueX, landingY + 0.2, farZ);
    const upperDirection = upperEnd.clone().sub(upperStart);
    const upperArrow = new THREE.ArrowHelper(
      upperDirection.clone().normalize(),
      upperStart,
      upperDirection.length(),
      0x2563eb,
      0.28,
      0.15
    );
    upperArrow.name = `${name}-4f-to-half-arrow`;
    group.add(upperArrow);

    const lowerStart = new THREE.Vector3(greenX, landingY + 0.18, farZ);
    const lowerEnd = new THREE.Vector3(greenX, lowerFloorTop + 0.18, nearZ);
    const lowerDirection = lowerEnd.clone().sub(lowerStart);
    const lowerArrow = new THREE.ArrowHelper(
      lowerDirection.clone().normalize(),
      lowerStart,
      lowerDirection.length(),
      0x16a34a,
      0.28,
      0.15
    );
    lowerArrow.name = `${name}-half-to-3f-arrow`;
    group.add(lowerArrow);
  }

  return {
    landing: new THREE.Vector3(0, landingY, landingZ),
    upperEntry: new THREE.Vector3(blueX, floorGap, nearZ),
    lowerExit: new THREE.Vector3(greenX, lowerFloorTop, nearZ)
  };
}

function initStairPreview() {
  const canvas = $("stairPreviewCanvas");
  if (!canvas || state.stairPreview) return;

  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x111827);
  const camera = new THREE.PerspectiveCamera(42, 1, 0.1, 80);
  camera.position.set(0, 5.75, 7.15);
  camera.lookAt(0, 1.58, 0);

  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: false });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  renderer.outputColorSpace = THREE.SRGBColorSpace;

  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.enablePan = false;
  controls.minDistance = 5.2;
  controls.maxDistance = 10.5;
  controls.target.set(0, 1.58, 0);
  controls.update();

  scene.add(new THREE.HemisphereLight(0xffffff, 0x334155, 2.4));
  const light = new THREE.DirectionalLight(0xffffff, 2.2);
  light.position.set(4, 8, 6);
  light.castShadow = true;
  scene.add(light);

  const root = new THREE.Group();
  root.rotation.y = THREE.MathUtils.degToRad(-10);
  scene.add(root);
  const anchors = buildInterfloorStairModule({
    group: root,
    addPart: (part) => addPreviewBox(root, part),
    name: "preview",
    width: 4.05,
    depth: 5.35,
    floorGap: 3.24,
    landingColor: 0x312e81,
    padColor: 0x020617
  });

  const marker = new THREE.Mesh(
    new THREE.SphereGeometry(0.18, 24, 16),
    makeMat(0xef4444, 0.45)
  );
  marker.name = "preview-current-position";
  marker.castShadow = true;
  root.add(marker);

  state.stairPreview = { scene, camera, renderer, root, marker, controls, anchors };
  resizeStairPreview();
  updateStairPreview();
}

function resizeStairPreview() {
  const preview = state.stairPreview;
  const canvas = $("stairPreviewCanvas");
  if (!preview || !canvas) return;
  const rect = canvas.getBoundingClientRect();
  if (!rect.width || !rect.height) return;
  preview.camera.aspect = rect.width / rect.height;
  preview.camera.updateProjectionMatrix();
  preview.renderer.setSize(rect.width, rect.height, false);
}

function renderStairPreview() {
  const preview = state.stairPreview;
  if (!preview) return;
  preview.controls.update();
  preview.renderer.render(preview.scene, preview.camera);
}

function addDoglegStair(options) {
  const {
    group = state.scene,
    name,
    x: worldX,
    z: worldZ,
    width,
    depth,
    floorHeight = 4,
    flightWidth = 1.5,
    firstRun = 3.4,
    secondRun = 3.5,
    entranceSide = "front",
    landingSide = "back",
    openSide = null,
    closeBack = false,
    backFillDepth = 0,
    stretchFlights = false,
    rotation = 0,
    color = palette.stair
  } = options;
  const stairRoot = new THREE.Group();
  stairRoot.name = name;
  stairRoot.position.set(worldX, state.floorYOffset || 0, worldZ);
  stairRoot.rotation.y = THREE.MathUtils.degToRad(rotation);
  group.add(stairRoot);

  if (state.combinedLayerRendering) {
    const frameHeight = 0.58;
    if (openSide !== "left") {
      addWall(stairRoot, -width / 2, 0, 0.12, depth, { height: frameHeight, opacity: 0.5, name: `${name}-combined-left-frame` });
    }
    if (openSide !== "right") {
      addWall(stairRoot, width / 2, 0, 0.12, depth, { height: frameHeight, opacity: 0.5, name: `${name}-combined-right-frame` });
    }
    if (closeBack) {
      addWall(stairRoot, 0, depth / 2, width, 0.12, { height: frameHeight, opacity: 0.5, name: `${name}-combined-back-frame` });
    }
    return;
  }

  const x = 0;
  const z = 0;
  const wallHeight = Math.min(floorHeight, 3.1);
  const wallThickness = 0.14;
  const landingDepth = Math.max(0.95, depth - Math.max(firstRun, secondRun));
  const usableFlightWidth = stretchFlights
    ? width / 2 - 0.04
    : Math.min(flightWidth, width / 2 - 0.08);
  const leftX = x - usableFlightWidth / 2;
  const rightX = x + usableFlightWidth / 2;
  const frontZ = z - depth / 2;
  const backZ = z + depth / 2;
  const landingAtBack = landingSide === "back";
  const firstStartZ = landingAtBack ? frontZ + 0.28 : backZ - 0.28;
  const firstEndZ = landingAtBack
    ? Math.min(firstStartZ + firstRun, backZ - landingDepth)
    : Math.max(firstStartZ - firstRun, frontZ + landingDepth);
  const secondStartZ = landingAtBack ? backZ - landingDepth : frontZ + landingDepth;
  const secondEndZ = landingAtBack
    ? Math.max(secondStartZ - secondRun, frontZ + 0.28)
    : Math.min(secondStartZ + secondRun, backZ - 0.28);
  const halfLandingZ = landingAtBack ? backZ - landingDepth / 2 : frontZ + landingDepth / 2;
  const upperLandingZ = landingAtBack ? frontZ + 0.24 : backZ - 0.24;
  const halfHeight = floorHeight / 2;
  const stepCount = 12;

  addBox(stairRoot, { x, z, w: width, d: depth, h: 0.1, y: 0.05, color: 0xe8ecf5, name: `${name}-floor` });

  for (let index = 0; index < stepCount; index += 1) {
    const progress = (index + 0.5) / stepCount;
    addBox(stairRoot, {
      x: leftX,
      z: firstStartZ + (firstEndZ - firstStartZ) * progress,
      w: usableFlightWidth - 0.08,
      d: Math.abs(firstEndZ - firstStartZ) / stepCount + 0.025,
      h: 0.12 + halfHeight * progress,
      color,
      name: `${name}-lower-flight-${index + 1}`
    });
  }

  addBox(stairRoot, {
    x,
    z: halfLandingZ,
    w: width - 0.28,
    d: landingDepth,
    h: 0.14,
    y: halfHeight,
    color,
    name: `${name}-half-landing`
  });

  for (let index = 0; index < stepCount; index += 1) {
    const progress = (index + 0.5) / stepCount;
    addBox(stairRoot, {
      x: rightX,
      z: secondStartZ + (secondEndZ - secondStartZ) * progress,
      w: usableFlightWidth - 0.08,
      d: Math.abs(secondEndZ - secondStartZ) / stepCount + 0.025,
      h: 0.12 + halfHeight + halfHeight * progress,
      color,
      name: `${name}-upper-flight-${index + 1}`
    });
  }

  addBox(stairRoot, {
    x,
    z: upperLandingZ,
    w: width - 0.28,
    d: 0.48,
    h: 0.14,
    y: floorHeight,
    color,
    name: `${name}-upper-landing`
  });

  if (backFillDepth > 0.05) {
    addBox(stairRoot, {
      x,
      z: backZ - backFillDepth / 2,
      w: width,
      d: backFillDepth,
      h: wallHeight,
      color: 0xd5dde6,
      name: `${name}-rear-space-fill`
    });
  }

  if (openSide !== "left") {
    addWall(stairRoot, x - width / 2, z, wallThickness, depth, { height: wallHeight, color: palette.trim, name: `${name}-left-wall` });
  }
  if (openSide !== "right") {
    addWall(stairRoot, x + width / 2, z, wallThickness, depth, { height: wallHeight, color: palette.trim, name: `${name}-right-wall` });
  }
  if (closeBack) {
    addWall(stairRoot, x, backZ, width, wallThickness, { height: wallHeight, color: palette.trim, name: `${name}-back-wall` });
  }
}

function addSplitFloorStair(options) {
  const {
    group = state.scene,
    name,
    x,
    z,
    width,
    depth,
    floorHeight = 4,
    flightWidth = 1.5,
    runLength = 3.5,
    rotation = 0
  } = options;
  const root = new THREE.Group();
  root.name = name;
  root.position.set(x, state.floorYOffset || 0, z);
  root.rotation.y = THREE.MathUtils.degToRad(rotation);
  group.add(root);

  const halfHeight = floorHeight / 2;
  const laneWidth = Math.min(flightWidth, width / 2 - 0.08);
  const backLaneX = -laneWidth / 2;
  const frontLaneX = laneWidth / 2;
  const startZ = -depth / 2 + 0.72;
  const endZ = Math.min(startZ + runLength, depth / 2 - 0.45);
  const stepCount = 12;
  const treadDepth = Math.abs(endZ - startZ) / stepCount + 0.025;
  const cutawayWallHeight = 1.18;

  addBox(root, {
    x: 0,
    z: -depth / 2 + 0.32,
    w: width - 0.24,
    d: 0.64,
    h: 0.12,
    y: 0.06,
    color: 0xe8ecf5,
    name: `${name}-floor-landing`
  });

  for (let index = 0; index < stepCount; index += 1) {
    const progress = (index + 0.5) / stepCount;
    const treadZ = startZ + (endZ - startZ) * progress;
    const upTop = halfHeight * progress;
    const downTop = -halfHeight * progress;
    addBox(root, {
      x: backLaneX,
      z: treadZ,
      w: laneWidth - 0.08,
      d: treadDepth,
      h: 0.12,
      y: upTop - 0.06,
      color: 0xcfe8d5,
      name: `${name}-up-flight-${index + 1}`
    });
    addBox(root, {
      x: frontLaneX,
      z: treadZ,
      w: laneWidth - 0.08,
      d: treadDepth,
      h: 0.12,
      y: downTop - 0.06,
      color: 0xc7d2fe,
      name: `${name}-down-flight-${index + 1}`
    });
  }

  const arrowDirection = new THREE.Vector3(0, 0, 1);
  const arrowLength = Math.max(endZ - startZ - 0.35, 1.2);
  const downArrow = new THREE.ArrowHelper(arrowDirection, new THREE.Vector3(frontLaneX, 0.24, startZ + 0.12), arrowLength, 0x2563eb, 0.38, 0.22);
  downArrow.name = `${name}-down-direction`;
  root.add(downArrow);
  const upArrow = new THREE.ArrowHelper(arrowDirection, new THREE.Vector3(backLaneX, 0.32, startZ + 0.12), arrowLength, 0x16a34a, 0.38, 0.22);
  upArrow.name = `${name}-up-direction`;
  root.add(upArrow);

  const downLabel = makeTextSprite("앞쪽 내려감", 0.38, "#1d4ed8");
  downLabel.position.set(frontLaneX, 2.05, startZ + arrowLength * 0.3);
  root.add(downLabel);
  const upLabel = makeTextSprite("뒤쪽 올라감", 0.38, "#15803d");
  upLabel.position.set(backLaneX, 2.25, startZ + arrowLength * 0.72);
  root.add(upLabel);

  addWall(root, -width / 2, 0, 0.14, depth, { height: cutawayWallHeight, color: palette.trim, name: `${name}-left-wall` });
  addWall(root, width / 2, 0, 0.14, depth, { height: cutawayWallHeight, color: palette.trim, name: `${name}-right-wall` });
}

function addSideEndStair(options) {
  const {
    name,
    x,
    z,
    width,
    depth,
    direction = 1,
    floorHeight = 4,
    entranceWall = true,
    entranceMode = "side",
    runAxis = "depth",
    entryLandingWidth = null,
    doorWidth = 1.15,
    frontDoorInset = 0,
    skipClosedSideWall = false,
    closedSideWallFrontOpeningDepth = 0,
    showTreadGuides = true
  } = options;
  const root = new THREE.Group();
  root.name = name;
  root.position.set(x, state.floorYOffset || 0, z);
  state.scene.add(root);
  const corridorEntryLandingWidth = runAxis === "corridor"
    ? Math.min(Math.max(entryLandingWidth ?? width * 0.38, 1.1), Math.max(width - 1.45, 1.1))
    : null;

  if (state.combinedLayerRendering) {
    if (entranceWall && entranceMode === "front") {
      const entranceHeight = 2.75;
      const frontZ = -depth / 2;
      const nominalDoorWidth = Math.min(doorWidth, width - 0.48);
      const doorOpeningWidth = corridorEntryLandingWidth
        ? Math.min(corridorEntryLandingWidth, width - 0.48)
        : nominalDoorWidth;
      const doorLeafWidth = Math.min(nominalDoorWidth, doorOpeningWidth);
      const doorInset = Math.max(0, Math.min(frontDoorInset, Math.max((width - doorOpeningWidth) / 2, 0)));
      const doorStartX = direction > 0
        ? -width / 2 + doorInset
        : width / 2 - doorInset - doorOpeningWidth;
      const doorEndX = doorStartX + doorOpeningWidth;
      const leftWallWidth = Math.max(doorStartX + width / 2, 0);
      const rightWallWidth = Math.max(width / 2 - doorEndX, 0);

      if (leftWallWidth > 0.05) {
        addWall(root, -width / 2 + leftWallWidth / 2, frontZ, leftWallWidth, 0.12, {
          height: entranceHeight,
          color: palette.trim,
          name: `${name}-combined-front-wall-left-of-door`
        });
      }
      if (rightWallWidth > 0.05) {
        addWall(root, doorEndX + rightWallWidth / 2, frontZ, rightWallWidth, 0.12, {
          height: entranceHeight,
          color: palette.trim,
          name: `${name}-combined-front-wall-right-of-door`
        });
      }

      const doorCenterX = direction > 0
        ? doorStartX + doorLeafWidth / 2
        : doorEndX - doorLeafWidth / 2;
      const doorLeaf = new THREE.Mesh(
        new THREE.BoxGeometry(doorLeafWidth * 0.88, 2.05, 0.08),
        makeMat(palette.door, 0.32, 0.98, 0.35)
      );
      doorLeaf.name = `${name}-combined-front-door-open`;
      doorLeaf.position.set(doorCenterX - direction * 0.18, 1.025, frontZ - 0.32);
      doorLeaf.rotation.y = THREE.MathUtils.degToRad(direction > 0 ? 58 : -58);
      doorLeaf.castShadow = true;
      doorLeaf.receiveShadow = true;
      root.add(doorLeaf);
    }
    return;
  }

  const wallHeight = Math.min(floorHeight, 2.75);
  const halfHeight = floorHeight / 2;
  const frontZ = -depth / 2;
  const backZ = depth / 2;
  const landingDepth = Math.max(0.9, Math.min(1.18, depth * 0.18));
  const runStartZ = frontZ + 0.7;
  const runEndZ = backZ - landingDepth - 0.18;
  const runLength = Math.max(runEndZ - runStartZ, 2.4);
  const stepCount = 12;
  const laneGap = 0.16;
  const laneWidth = Math.min(width / 2 - laneGap, 1.36);
  const laneOffset = laneWidth / 2 + laneGap / 2;
  const downLaneX = direction > 0 ? -laneOffset : laneOffset;
  const upLaneX = -downLaneX;
  const treadDepth = runLength / stepCount + 0.025;

  if (runAxis === "corridor") {
    const landingWidth = corridorEntryLandingWidth;
    const corridorRun = Math.max(width - landingWidth - 0.24, 1.2);
    const corridorStepDir = direction > 0 ? 1 : -1;
    const corridorStartX = direction > 0 ? -width / 2 + landingWidth : width / 2 - landingWidth;
    const corridorEndX = corridorStartX + corridorStepDir * corridorRun;
    const corridorStepWidth = corridorRun / stepCount;
    const corridorLaneGap = 0.18;
    const corridorLaneDepth = (depth - corridorLaneGap) / 2;
    const corridorDownZ = -depth / 2 + corridorLaneDepth / 2;
    const corridorUpZ = depth / 2 - corridorLaneDepth / 2;
    const corridorCenterX = corridorStartX + corridorStepDir * corridorRun / 2;
    const corridorArrow = new THREE.Vector3(corridorStepDir, 0, 0);

    addBox(root, { x: 0, z: 0, w: width, d: depth, h: 0.08, y: 0.04, color: 0xe8ecf5, name: `${name}-floor` });
    addBox(root, {
      x: direction > 0 ? -width / 2 + landingWidth / 2 : width / 2 - landingWidth / 2,
      z: 0,
      w: landingWidth,
      d: depth - 0.18,
      h: 0.11,
      y: 0.07,
      color: 0xf1f5f9,
      name: `${name}-front-landing`
    });
    if (showTreadGuides) {
      addBox(root, {
        x: corridorCenterX,
        z: corridorDownZ,
        w: corridorRun,
        d: corridorLaneDepth - 0.08,
        h: 0.035,
        y: 0.115,
        color: 0x5f7397,
        opacity: 0.48,
        name: `${name}-down-stairwell-opening`
      });
      addBox(root, {
        x: corridorCenterX,
        z: corridorUpZ,
        w: corridorRun,
        d: corridorLaneDepth - 0.08,
        h: 0.035,
        y: 0.115,
        color: 0xbfe6c9,
        opacity: 0.34,
        name: `${name}-up-stairwell-base`
      });
    }
    addBox(root, {
      x: corridorEndX + corridorStepDir * 0.12,
      z: 0,
      w: landingWidth,
      d: depth - 0.26,
      h: 0.14,
      y: halfHeight * 0.34,
      color: palette.stair,
      opacity: 0.92,
      name: `${name}-half-landing`
    });
    for (let index = 0; index < stepCount; index += 1) {
      const progress = (index + 0.5) / stepCount;
      const stepCenterX = corridorStartX + corridorStepDir * corridorRun * progress;
      const downTop = 0.92 - 0.76 * progress;
      const upTop = 0.18 + 0.96 * progress;
      addBox(root, {
        x: stepCenterX,
        z: corridorDownZ,
        w: corridorStepWidth,
        d: corridorLaneDepth - 0.12,
        h: 0.105,
        y: downTop - 0.0525,
        color: 0xc7d2fe,
        name: `${name}-down-flight-${index + 1}`
      });
      if (showTreadGuides) {
        addBox(root, {
          x: stepCenterX,
          z: corridorDownZ,
          w: 0.055,
          d: corridorLaneDepth - 0.1,
          h: 0.045,
          y: 1.22,
          color: 0x1d4ed8,
          opacity: 0.86,
          name: `${name}-down-visible-tread-${index + 1}`
        });
      }
      if (showTreadGuides) {
        addBox(root, {
          x: stepCenterX + corridorStepDir * corridorStepWidth / 2,
          z: corridorDownZ,
          w: 0.035,
          d: corridorLaneDepth - 0.16,
          h: Math.max(downTop - 0.1, 0.12),
          y: Math.max(downTop - 0.1, 0.12) / 2,
          color: 0x93a5d8,
          opacity: 0.72,
          name: `${name}-down-riser-${index + 1}`
        });
      }
      addBox(root, {
        x: stepCenterX,
        z: corridorUpZ,
        w: corridorStepWidth,
        d: corridorLaneDepth - 0.12,
        h: 0.105,
        y: upTop - 0.0525,
        color: 0xcfe8d5,
        name: `${name}-up-flight-${index + 1}`
      });
      if (showTreadGuides) {
        addBox(root, {
          x: stepCenterX,
          z: corridorUpZ,
          w: 0.055,
          d: corridorLaneDepth - 0.1,
          h: 0.045,
          y: 1.22,
          color: 0x15803d,
          opacity: 0.82,
          name: `${name}-up-visible-tread-${index + 1}`
        });
      }
      if (showTreadGuides) {
        addBox(root, {
          x: stepCenterX - corridorStepDir * corridorStepWidth / 2,
          z: corridorUpZ,
          w: 0.035,
          d: corridorLaneDepth - 0.16,
          h: Math.max(upTop - 0.1, 0.12),
          y: Math.max(upTop - 0.1, 0.12) / 2,
          color: 0x92c9a0,
          opacity: 0.68,
          name: `${name}-up-riser-${index + 1}`
        });
      }
    }

    const downArrow = new THREE.ArrowHelper(corridorArrow, new THREE.Vector3(corridorStartX, 0.92, corridorDownZ), corridorRun - 0.16, 0x2563eb, 0.32, 0.18);
    downArrow.rotation.z = THREE.MathUtils.degToRad(corridorStepDir > 0 ? -10 : 10);
    downArrow.name = `${name}-down-direction`;
    root.add(downArrow);
    const upArrow = new THREE.ArrowHelper(corridorArrow, new THREE.Vector3(corridorStartX, 0.5, corridorUpZ), corridorRun - 0.16, 0x16a34a, 0.32, 0.18);
    upArrow.rotation.z = THREE.MathUtils.degToRad(corridorStepDir > 0 ? 10 : -10);
    upArrow.name = `${name}-up-direction`;
    root.add(upArrow);

    const downLabel = makeTextSprite("앞쪽 내려감", 0.36, "#1d4ed8");
    downLabel.position.set(corridorStartX + corridorStepDir * corridorRun * 0.42, 1.44, corridorDownZ);
    root.add(downLabel);
    const upLabel = makeTextSprite("뒤쪽 올라감", 0.36, "#15803d");
    upLabel.position.set(corridorStartX + corridorStepDir * corridorRun * 0.58, 1.5, corridorUpZ);
    root.add(upLabel);
  } else {
  addBox(root, { x: 0, z: 0, w: width, d: depth, h: 0.08, y: 0.04, color: 0xe8ecf5, name: `${name}-floor` });
  addBox(root, {
    x: 0,
    z: frontZ + 0.34,
    w: width - 0.28,
    d: 0.68,
    h: 0.11,
    y: 0.07,
    color: 0xf1f5f9,
    name: `${name}-front-landing`
  });
  if (showTreadGuides) {
    addBox(root, {
      x: downLaneX,
      z: runStartZ + runLength / 2,
      w: laneWidth,
      d: runLength + 0.16,
      h: 0.035,
      y: 0.115,
      color: 0x5f7397,
      opacity: 0.48,
      name: `${name}-down-stairwell-opening`
    });
    addBox(root, {
      x: downLaneX,
      z: runEndZ + 0.18,
      w: laneWidth - 0.12,
      d: 0.34,
      h: 1.1,
      y: 0.55,
      color: 0x475569,
      opacity: 0.38,
      name: `${name}-down-lower-void`
    });
    addBox(root, {
      x: upLaneX,
      z: runStartZ + runLength / 2,
      w: laneWidth,
      d: runLength + 0.16,
      h: 0.035,
      y: 0.115,
      color: 0xbfe6c9,
      opacity: 0.34,
      name: `${name}-up-stairwell-base`
    });
  }
  addBox(root, {
    x: 0,
    z: backZ - landingDepth / 2,
    w: width - 0.28,
    d: landingDepth,
    h: 0.14,
    y: halfHeight * 0.34,
    color: palette.stair,
    opacity: 0.92,
    name: `${name}-half-landing`
  });
  for (let index = 0; index < stepCount; index += 1) {
    const progress = (index + 0.5) / stepCount;
    const downZ = runStartZ + runLength * progress;
    const upZ = runEndZ - runLength * progress;
    const downTop = 0.92 - 0.76 * progress;
    const upTop = 0.18 + 0.96 * progress;
    addBox(root, {
      x: downLaneX,
      z: downZ,
      w: laneWidth - 0.12,
      d: treadDepth,
      h: 0.105,
      y: downTop - 0.0525,
      color: 0xc7d2fe,
      name: `${name}-down-flight-${index + 1}`
    });
    if (showTreadGuides) {
      addBox(root, {
        x: downLaneX,
        z: downZ,
        w: laneWidth - 0.1,
        d: 0.055,
        h: 0.045,
        y: 1.22,
        color: 0x1d4ed8,
        opacity: 0.86,
        name: `${name}-down-visible-tread-${index + 1}`
      });
    }
    if (showTreadGuides) {
      addBox(root, {
        x: downLaneX,
        z: downZ + treadDepth / 2,
        w: laneWidth - 0.16,
        d: 0.035,
        h: Math.max(downTop - 0.1, 0.12),
        y: Math.max(downTop - 0.1, 0.12) / 2,
        color: 0x93a5d8,
        opacity: 0.72,
        name: `${name}-down-riser-${index + 1}`
      });
    }
    addBox(root, {
      x: upLaneX,
      z: upZ,
      w: laneWidth - 0.12,
      d: treadDepth,
      h: 0.105,
      y: upTop - 0.0525,
      color: 0xcfe8d5,
      name: `${name}-up-flight-${index + 1}`
    });
    if (showTreadGuides) {
      addBox(root, {
        x: upLaneX,
        z: upZ,
        w: laneWidth - 0.1,
        d: 0.055,
        h: 0.045,
        y: 1.22,
        color: 0x15803d,
        opacity: 0.82,
        name: `${name}-up-visible-tread-${index + 1}`
      });
    }
    if (showTreadGuides) {
      addBox(root, {
        x: upLaneX,
        z: upZ - treadDepth / 2,
        w: laneWidth - 0.16,
        d: 0.035,
        h: Math.max(upTop - 0.1, 0.12),
        y: Math.max(upTop - 0.1, 0.12) / 2,
        color: 0x92c9a0,
        opacity: 0.68,
        name: `${name}-up-riser-${index + 1}`
      });
    }
  }

  const downArrow = new THREE.ArrowHelper(new THREE.Vector3(0, 0, 1), new THREE.Vector3(downLaneX, 0.92, runStartZ), runLength - 0.2, 0x2563eb, 0.32, 0.18);
  downArrow.rotation.x = THREE.MathUtils.degToRad(-10);
  downArrow.name = `${name}-down-direction`;
  root.add(downArrow);
  const upArrow = new THREE.ArrowHelper(new THREE.Vector3(0, 0, -1), new THREE.Vector3(upLaneX, 0.5, runEndZ), runLength - 0.2, 0x16a34a, 0.32, 0.18);
  upArrow.rotation.x = THREE.MathUtils.degToRad(10);
  upArrow.name = `${name}-up-direction`;
  root.add(upArrow);

  const downLabel = makeTextSprite("앞쪽 내려감", 0.36, "#1d4ed8");
  downLabel.position.set(downLaneX, 1.44, runStartZ + runLength * 0.36);
  root.add(downLabel);
  const upLabel = makeTextSprite("뒤쪽 올라감", 0.36, "#15803d");
  upLabel.position.set(upLaneX, 1.5, runEndZ - runLength * 0.28);
  root.add(upLabel);
  }

  addWall(root, 0, depth / 2, width, 0.12, { height: wallHeight, color: palette.trim, name: `${name}-outer-wall` });
  addWall(root, direction > 0 ? width / 2 : -width / 2, 0, 0.12, depth, { height: wallHeight, color: palette.trim, name: `${name}-end-wall` });
  if (entranceWall && entranceMode === "front") {
    const entranceSideX = direction > 0 ? -width / 2 : width / 2;
    const frontZ = -depth / 2;
    if (!skipClosedSideWall) {
      const sideOpeningDepth = Math.max(0, Math.min(closedSideWallFrontOpeningDepth, depth - 0.12));
      const closedWallDepth = depth - sideOpeningDepth;
      if (closedWallDepth > 0.08) {
        addWall(root, entranceSideX, frontZ + sideOpeningDepth + closedWallDepth / 2, 0.12, closedWallDepth, {
          height: wallHeight,
          color: palette.trim,
          name: `${name}-closed-side-wall`
        });
      }
    }

    const nominalDoorWidth = Math.min(doorWidth, width - 0.48);
    const doorOpeningWidth = corridorEntryLandingWidth
      ? Math.min(corridorEntryLandingWidth, width - 0.48)
      : nominalDoorWidth;
    const doorLeafWidth = Math.min(nominalDoorWidth, doorOpeningWidth);
    const doorInset = Math.max(0, Math.min(frontDoorInset, Math.max((width - doorOpeningWidth) / 2, 0)));
    const doorStartX = direction > 0
      ? -width / 2 + doorInset
      : width / 2 - doorInset - doorOpeningWidth;
    const doorEndX = doorStartX + doorOpeningWidth;
    const leftWallWidth = Math.max(doorStartX + width / 2, 0);
    const rightWallWidth = Math.max(width / 2 - doorEndX, 0);

    if (leftWallWidth > 0.05) {
      addWall(root, -width / 2 + leftWallWidth / 2, frontZ, leftWallWidth, 0.12, {
        height: wallHeight,
        color: palette.trim,
        name: `${name}-front-wall-left-of-door`
      });
    }
    if (rightWallWidth > 0.05) {
      addWall(root, doorEndX + rightWallWidth / 2, frontZ, rightWallWidth, 0.12, {
        height: wallHeight,
        color: palette.trim,
        name: `${name}-front-wall-right-of-door`
      });
    }

    const openingCenterX = (doorStartX + doorEndX) / 2;
    const doorCenterX = direction > 0
      ? doorStartX + doorLeafWidth / 2
      : doorEndX - doorLeafWidth / 2;
    const doorLeaf = new THREE.Mesh(
      new THREE.BoxGeometry(doorLeafWidth * 0.88, 2.05, 0.08),
      makeMat(palette.door, 0.32, 0.98, 0.35)
    );
    doorLeaf.name = `${name}-front-door-open`;
    doorLeaf.position.set(doorCenterX - direction * 0.18, 1.025, frontZ - 0.32);
    doorLeaf.rotation.y = THREE.MathUtils.degToRad(direction > 0 ? 58 : -58);
    doorLeaf.castShadow = true;
    doorLeaf.receiveShadow = true;
    root.add(doorLeaf);
    addBox(root, {
      x: openingCenterX,
      z: frontZ,
      w: doorOpeningWidth,
      d: 0.16,
      h: 0.035,
      y: 0.14,
      color: palette.door,
      metalness: 0.25,
      name: `${name}-front-door-threshold`
    });
  } else if (entranceWall) {
    const entranceX = direction > 0 ? -width / 2 : width / 2;
    const doorStartZ = -depth / 2 + 0.22;
    const doorEndZ = doorStartZ + doorWidth;
    const beforeDoor = Math.max(doorStartZ + depth / 2, 0);
    const afterDoor = Math.max(depth / 2 - doorEndZ, 0);
    if (beforeDoor > 0.05) {
      addWall(root, entranceX, -depth / 2 + beforeDoor / 2, 0.12, beforeDoor, {
        height: wallHeight,
        color: palette.trim,
        name: `${name}-entrance-wall-before-door`
      });
    }
    if (afterDoor > 0.05) {
      addWall(root, entranceX, doorEndZ + afterDoor / 2, 0.12, afterDoor, {
        height: wallHeight,
        color: palette.trim,
        name: `${name}-entrance-wall-after-door`
      });
    }
    const doorLeaf = new THREE.Mesh(
      new THREE.BoxGeometry(0.08, 2.05, doorWidth * 0.88),
      makeMat(palette.door, 0.32, 0.98, 0.35)
    );
    doorLeaf.name = `${name}-entrance-door-open`;
    doorLeaf.position.set(entranceX - direction * 0.34, 1.025, doorStartZ + doorWidth * 0.44);
    doorLeaf.rotation.y = THREE.MathUtils.degToRad(direction > 0 ? -68 : 68);
    doorLeaf.castShadow = true;
    doorLeaf.receiveShadow = true;
    root.add(doorLeaf);
    addBox(root, {
      x: entranceX,
      z: (doorStartZ + doorEndZ) / 2,
      w: 0.16,
      d: doorWidth,
      h: 0.035,
      y: 0.14,
      color: palette.door,
      metalness: 0.25,
      name: `${name}-entrance-threshold`
    });
  }
}

function addElevatorHub() {
  const layout = { ...DEFAULT_LAYOUT, ...state.data.layout_dimensions };
  const elevator = state.data.facilities.find((item) => item.id === "4F_ELEVATOR_BANK");
  const stairs = state.data.facilities.find((item) => item.id === "4F_CENTER_STAIRS");
  const hubHalfWidth = layout.hub_width / 2;
  const coreStartZ = layout.corridor_width / 2;
  const coreEndZ = coreStartZ + layout.hub_length;
  const toCoreZ = (depth) => coreStartZ + depth;
  const hubCenterZ = coreStartZ + layout.hub_length / 2;
  const wallHeight = 2.85;
  const sideBayWidth = (layout.hub_outer_width - layout.hub_width) / 2;
  addBox(state.scene, {
    x: HUB_X,
    z: hubCenterZ,
    w: layout.hub_width,
    d: layout.hub_length,
    h: 0.1,
    y: 0.05,
    color: palette.corridor,
    name: "elevator-stair-hub-corridor"
  });

  const stairX = mapX(stairs?.x ?? HUB_MAP_X + 3.7);
  const elevatorX = mapX(elevator?.x ?? HUB_MAP_X - 3.7);
  const stairSideSign = Math.sign(stairX - HUB_X) || -1;
  const elevatorSideSign = Math.sign(elevatorX - HUB_X) || 1;
  const stairBoundaryX = HUB_X + stairSideSign * hubHalfWidth;
  const elevatorBoundaryX = HUB_X + elevatorSideSign * hubHalfWidth;
  const elevatorOuterX = HUB_X + elevatorSideSign * (hubHalfWidth + sideBayWidth);
  const elevatorCapX = HUB_X + elevatorSideSign * (hubHalfWidth + sideBayWidth / 2);
  addWall(state.scene, elevatorOuterX, hubCenterZ, 0.16, layout.hub_length, { height: wallHeight, name: "elevator-rear-wall" });
  addWall(state.scene, elevatorCapX, coreStartZ, sideBayWidth, 0.16, { height: wallHeight, name: "elevator-start-cap" });
  addWall(state.scene, elevatorCapX, coreEndZ, sideBayWidth, 0.16, { height: wallHeight, name: "elevator-end-cap" });

  const stairStartDepth = 2.44;
  const stairStartZ = toCoreZ(stairStartDepth);
  const stairDepth = coreEndZ - stairStartZ;
  addBox(state.scene, {
    x: stairX,
    z: coreStartZ + stairStartDepth / 2,
    w: sideBayWidth - 0.28,
    d: stairStartDepth,
    h: wallHeight,
    color: 0xd5dde6,
    name: "main-stair-2p44m-solid-fill"
  });
  addDoglegStair({
    name: "hub-main-stair",
    x: stairX,
    z: stairStartZ + stairDepth / 2,
    width: sideBayWidth - 0.28,
    depth: stairDepth,
    floorHeight: state.data.floor_core?.provisional_floor_height || 4,
    flightWidth: state.data.floor_core?.main_stair_flight_width || 1.5,
    firstRun: state.data.floor_core?.main_stair_first_run || 3.4,
    secondRun: state.data.floor_core?.main_stair_second_run || 3.5,
    landingSide: "front",
    openSide: stairSideSign < 0 ? "right" : "left",
    closeBack: true,
    stretchFlights: true
  });
  const stairDoorWidth = 1.0;
  const stairDoorStartDepth = stairStartDepth;
  const stairDoorEndDepth = stairDoorStartDepth + stairDoorWidth;
  addWall(
    state.scene,
    stairBoundaryX,
    coreStartZ + stairStartDepth / 2,
    0.16,
    stairStartDepth,
    { height: wallHeight, name: "main-stair-wall-before-door" }
  );
  const wallAfterDoorDepth = Math.max(layout.hub_length - stairDoorEndDepth, 0);
  if (wallAfterDoorDepth > 0.05) {
    addWall(
      state.scene,
      stairBoundaryX,
      toCoreZ(stairDoorEndDepth + wallAfterDoorDepth / 2),
      0.16,
      wallAfterDoorDepth,
      { height: wallHeight, name: "main-stair-wall-after-door" }
    );
  }
  addBox(state.scene, {
    x: stairBoundaryX,
    z: toCoreZ(stairDoorStartDepth + stairDoorWidth / 2),
    w: 0.2,
    d: stairDoorWidth,
    h: 0.025,
    y: 0.12,
    color: palette.door,
    name: "main-stair-door-threshold"
  });
  if (!state.combinedLayerRendering) {
    addLabel("계단", stairX, stairStartZ + 1.15, 3.15, 0.72, "#312e81");
  }

  const elevatorDoorWidth = 1.1;
  const elevatorDoorStarts = [3.59, 6.96];
  const elevatorWallSegments = [
    [0, elevatorDoorStarts[0]],
    [elevatorDoorStarts[0] + elevatorDoorWidth, elevatorDoorStarts[1]],
    [elevatorDoorStarts[1] + elevatorDoorWidth, layout.hub_length]
  ];
  for (const [startZ, endZ] of elevatorWallSegments) {
    if (endZ <= startZ) continue;
    addWall(state.scene, elevatorBoundaryX, toCoreZ((startZ + endZ) / 2), 0.16, endZ - startZ, { height: wallHeight });
  }
  elevatorDoorStarts.forEach((startZ, index) => {
    const doorCenterZ = toCoreZ(startZ + elevatorDoorWidth / 2);
    addBox(state.scene, {
      x: elevatorX,
      z: doorCenterZ,
      w: sideBayWidth - 0.3,
      d: elevatorDoorWidth + 0.3,
      h: wallHeight,
      color: 0xcbd5e1,
      name: `4f-elevator-shaft-${index + 1}`
    });
    addBox(state.scene, {
      x: elevatorBoundaryX + elevatorSideSign * 0.06,
      z: doorCenterZ,
      w: 0.08,
      d: elevatorDoorWidth,
      h: 2.35,
      color: palette.door,
      metalness: 0.55,
      name: `elevator-door-${index + 1}`
    });
    addLabel(`EV ${index + 1}`, elevatorBoundaryX + elevatorSideSign * 0.25, doorCenterZ, 2.6, 0.46, "#1e3a8a");
  });
  addLabel("엘레베이터 2대", elevatorX, toCoreZ(4.9), 3.25, 0.58, "#1e3a8a");

  addBox(state.scene, {
    x: HUB_X,
    z: coreEndZ - 0.22,
    w: layout.hub_width,
    d: 0.32,
    h: 2.25,
    y: 1.35,
    color: 0xd8e7f0,
    opacity: 0.72,
    name: "hub-window-end"
  });
  addLabel("창가", HUB_X, coreEndZ - 0.55, 3.1, 0.58, "#475569");
  addLabel("코어 복도", HUB_X, toCoreZ(1.55), 3.15, 0.65, "#1f2937");
}

function addRightEndFacilities() {
  if (Number(state.floor) >= 6) {
    addFloor6RightEndFacilities();
    return;
  }
  const layout = { ...DEFAULT_LAYOUT, ...state.data.layout_dimensions };
  const restroom = state.data.facilities.find((item) => item.id === "4F_RESTROOM");
  const endStairs = state.data.facilities.find((item) => item.id === "4F_4204_END_STAIRS");
  if (!restroom || !endStairs) return;

  const currentFloor = Number(state.floor);
  const stairPlacement = getRightEndStairPlacement(layout, endStairs);
  const stairAlongCorridor = stairPlacement.width;
  const stairDepthFromCorridor = stairPlacement.depth;
  const passageWidth = restroom.passage_width || 1.262;
  const passageDepth = restroom.passage_depth || layout.room_depth;
  const doorwayWidth = restroom.door_width || 0.902;
  const endDirection = 1;
  const stairX = stairPlacement.x;
  const stairStartX = stairPlacement.startX;
  const fixedRoom4204 = state.maps[4]?.rooms.find((item) => item.id === "4204");
  const fixedRoomEdgeX = fixedRoom4204
    ? mapX(fixedRoom4204.x) + (fixedRoom4204.width || 4.5) / 2
    : stairStartX - passageWidth - 0.35;
  const passageClearance = restroom.passage_clearance_after_4204 || 0.35;
  const fixedPassageX = restroom.passage_center_map_x == null
    ? fixedRoomEdgeX + passageClearance + passageWidth / 2
    : mapX(restroom.passage_center_map_x);
  // Floors 1 through 5 share the fixed passage/core shell. Only the end
  // stair moves so its first flight starts at the corridor end line.
  const preserveFixedPassage = new Set([1, 2, 3, 4, 5]).has(currentFloor);
  const passageX = preserveFixedPassage
    ? fixedPassageX
    : Math.min(
      fixedPassageX,
      stairStartX - 0.22 - passageWidth / 2
    );
  const facilitySide = restroom.side || endStairs.side || "lower";
  const sideSign = facilitySide === "upper" ? -1 : 1;
  const corridorEdgeZ = sideSign * layout.corridor_width / 2;
  const passageZ = corridorEdgeZ + sideSign * passageDepth / 2;
  const passageEndZ = corridorEdgeZ + sideSign * passageDepth;
  const passageLeftX = passageX - passageWidth / 2;
  const passageRightX = passageX + passageWidth / 2;
  const wallHeight = 2.75;

  const currentRoomEdgeX = state.data.rooms
    .filter((room) => !room.placement && (room.side || facilitySide) === facilitySide && room.x != null)
    .map((room) => {
      if (room.extend_to_restroom_passage) return passageLeftX;
      return mapX(room.display_x ?? room.x) + (room.display_width || room.width || 4.5) / 2;
    })
    .filter((edgeX) => edgeX < passageLeftX - 0.04)
    .sort((a, b) => b - a)[0];
  const rawGapFillWidth = currentFloor !== 4 && currentRoomEdgeX != null
    ? Math.max(passageLeftX - currentRoomEdgeX, 0)
    : 0;
  const seamCoverFloors = new Set([1, 2, 3]);
  const shouldCoverRestroomSeam = rawGapFillWidth > 0.01
    || (seamCoverFloors.has(currentFloor) && currentFloor !== 2 && currentRoomEdgeX != null);
  if (shouldCoverRestroomSeam) {
    const gapFillOverlap = currentFloor === 5
      ? 1.35
      : rawGapFillWidth > 0.01
        ? 3.4
        : 0.36;
    const gapFillDepth = Math.max(passageDepth, stairDepthFromCorridor);
    const gapFillLeft = currentRoomEdgeX - gapFillOverlap;
    const gapFillRight = passageLeftX + gapFillOverlap;
    addBox(state.scene, {
      x: (gapFillLeft + gapFillRight) / 2,
      z: corridorEdgeZ + sideSign * gapFillDepth / 2,
      w: Math.max(gapFillRight - gapFillLeft, 0.08),
      d: gapFillDepth + (currentFloor === 5 ? 0.32 : 0.95),
      h: 0.16,
      y: 0.08,
      color: palette.roomFloor,
      opacity: 1,
      name: "right-end-restroom-left-gap-fill"
    });
  }

  // The scan confirms a side passage before the end stair, but not the full
  // restroom footprint. Model only the measured passage and doorway.
  addBox(state.scene, {
    x: passageX,
    z: passageZ,
    w: passageWidth,
    d: passageDepth,
    h: 0.1,
    y: 0.05,
    color: palette.restroom,
    name: "right-end-restroom-passage"
  });
  addWall(state.scene, passageLeftX, passageZ, 0.14, passageDepth, {
    height: wallHeight,
    name: "right-end-restroom-left-wall"
  });
  const sideWallDepth = passageDepth;
  if (sideWallDepth > 0.08) {
    addWall(
      state.scene,
      passageRightX,
      corridorEdgeZ + sideSign * (sideWallDepth / 2),
      0.14,
      sideWallDepth,
      { height: wallHeight, name: "right-end-restroom-right-wall" }
    );
  }
  const endWallSegment = Math.max((passageWidth - doorwayWidth) / 2, 0.12);
  addWall(state.scene, passageX - (doorwayWidth + endWallSegment) / 2, passageEndZ, endWallSegment, 0.14, { height: wallHeight });
  addWall(state.scene, passageX + (doorwayWidth + endWallSegment) / 2, passageEndZ, endWallSegment, 0.14, { height: wallHeight });
  addBox(state.scene, {
    x: passageX,
    z: passageEndZ,
    w: doorwayWidth,
    d: 0.06,
    h: 2.15,
    color: palette.door,
    metalness: 0.25,
    name: "restroom-door"
  });
  addLabel("화장실 통로", passageX, passageZ, 3.05, 0.58, "#065f46");

  const stairZ = corridorEdgeZ + sideSign * stairDepthFromCorridor / 2;
  const wallBeforeStair = Math.max(stairStartX - passageRightX, 0);
  const skipStairClosedSideWall = currentFloor === 5;
  const stairEntrySideOpeningDepth = 0;
  if (wallBeforeStair > 0.08) {
    const frontWallOverlap = 0;
    addBox(state.scene, {
      x: passageRightX + (wallBeforeStair + frontWallOverlap) / 2,
      z: stairZ,
      w: wallBeforeStair + frontWallOverlap,
      d: stairDepthFromCorridor,
      h: 0.1,
      y: 0.05,
      color: palette.roomFloor,
      opacity: 1,
      name: "right-end-restroom-to-stair-solid-floor"
    });
    addWall(
      state.scene,
      passageRightX + (wallBeforeStair + frontWallOverlap) / 2,
      corridorEdgeZ,
      wallBeforeStair + frontWallOverlap,
      0.14,
      { height: wallHeight, name: "wall-before-end-stair-entrance" }
    );
  }

  addSideEndStair({
    name: "4204-end-stair",
    x: stairX,
    z: stairZ,
    width: stairAlongCorridor,
    depth: stairDepthFromCorridor,
    direction: endDirection,
    floorHeight: endStairs.floor_height || 4,
    entranceMode: "front",
    runAxis: "corridor",
    entryLandingWidth: endStairs.entry_landing_width,
    frontDoorInset: 0,
    skipClosedSideWall: skipStairClosedSideWall,
    closedSideWallFrontOpeningDepth: stairEntrySideOpeningDepth,
    showTreadGuides: currentFloor === 4 || currentFloor === 5
  });

  if (!state.combinedLayerRendering) {
    addLabel("끝 계단", stairX, stairZ, 3.05, 0.58, "#312e81");
  }
}

function addFloor6RightEndFacilities() {
  const layout = { ...DEFAULT_LAYOUT, ...state.data.layout_dimensions };
  const spec = state.data.floor6_right_end;
  const fixedStair = state.maps[4]?.facilities.find((item) => item.id === "4F_4204_END_STAIRS");
  const room = state.data.rooms.find((item) => item.id === spec?.room_id);
  if (!spec || !fixedStair || !room) return;

  // The 6F plan changes the rooms and passage before the right stair, not the
  // stair anchor itself. Keep the 4F stair coordinate as the fixed building shell.
  const stair = getRightEndStairPlacement(layout, fixedStair);
  const floorPrefix = String(state.floor);
  const adjacentRoom = state.data.rooms.find((item) => item.id === `${floorPrefix}203`);
  const upperEndRoom = state.data.rooms.find((item) => item.id === `${floorPrefix}103`);
  const endLineMapX = adjacentRoom
    ? adjacentRoom.x - adjacentRoom.width / 2
    : upperEndRoom
      ? upperEndRoom.x - upperEndRoom.width / 2
      : room.x + room.width / 2;
  const endLineX = mapX(endLineMapX);
  const corridorEndX = mapX(0);
  const endZoneWidth = Math.abs(corridorEndX - endLineX);
  const endZoneCenterX = (corridorEndX + endLineX) / 2;
  const corridorHalf = layout.corridor_width / 2;

  // The upper 103 room and lower 203 room end on this same line. The 2D plan has no room or corridor
  // floor beyond this end line: it is closed by the L-shaped outer wall.
  addWall(state.scene, endZoneCenterX, -corridorHalf, endZoneWidth, 0.14, { height: 2.75, name: "6f-right-end-upper-l-wall" });

  addSideEndStair({
    name: "6f-right-end-stair",
    // The 4F stair size/orientation stays fixed, but its entry landing begins
    // outside the 6103/6203 end line so it cannot overlap either room.
    x: stair.x + (fixedStair.entry_landing_width || 0),
    z: stair.z,
    width: stair.width,
    depth: stair.depth,
    direction: 1,
    floorHeight: fixedStair.floor_height || 4,
    entranceMode: "front",
    runAxis: "corridor",
    entryLandingWidth: fixedStair.entry_landing_width,
    frontDoorInset: 0,
    showTreadGuides: true
  });

  const sideSign = room.side === "upper" ? -1 : 1;
  const corridorEdgeZ = sideSign * layout.corridor_width / 2;
  const roomDepth = spec.room_depth;
  const roomX = mapX(room.x);
  const roomZ = corridorEdgeZ + sideSign * (layout.room_depth - roomDepth / 2);
  const frontZ = roomZ - sideSign * roomDepth / 2;
  const outerZ = roomZ + sideSign * roomDepth / 2;
  const wallHeight = 2.75;
  const wallThickness = 0.14;
  const doorWidth = Math.min(1.1, room.width * 0.26);
  const wallSegment = Math.max((room.width - doorWidth) / 2, 0.3);

  addBox(state.roomGroup, {
    x: roomX,
    z: roomZ,
    w: room.width,
    d: roomDepth,
    h: 0.1,
    y: 0.05,
    color: palette.roomFloor,
    name: `${room.id}-floor`
  });
  addWall(state.roomGroup, roomX, outerZ, room.width, wallThickness, { height: wallHeight, name: `${room.id}-outer-wall` });
  addWall(state.roomGroup, roomX - room.width / 2, roomZ, wallThickness, roomDepth, { height: wallHeight, name: `${room.id}-left-wall` });
  addWall(state.roomGroup, roomX + room.width / 2, roomZ, wallThickness, roomDepth, { height: wallHeight, name: `${room.id}-right-wall` });
  addWall(state.roomGroup, roomX - (doorWidth + wallSegment) / 2, frontZ, wallSegment, wallThickness, { height: wallHeight, name: `${room.id}-front-wall-left` });
  addWall(state.roomGroup, roomX + (doorWidth + wallSegment) / 2, frontZ, wallSegment, wallThickness, { height: wallHeight, name: `${room.id}-front-wall-right` });
  addBox(state.roomGroup, { x: roomX, z: frontZ, w: doorWidth, d: 0.06, h: 2.15, color: palette.door, metalness: 0.25, name: `${room.id}-door` });
  addLabel(room.label || room.id, roomX, frontZ + sideSign * 0.32, 3.15, 0.7, "#1f2937");

  const passageX = mapX(spec.passage_center_x);
  const passageZ = corridorEdgeZ + sideSign * spec.passage_depth / 2;
  addBox(state.scene, {
    x: passageX,
    z: passageZ,
    w: spec.passage_width,
    d: spec.passage_depth,
    h: 0.1,
    y: 0.05,
    color: palette.restroom,
    name: "6f-right-end-passage"
  });
  // The former restroom passage is the 6202 access passage on 6F. Its side
  // walls define the passage without closing the corridor-side entrance.
  addWall(state.scene, passageX - spec.passage_width / 2, passageZ, 0.14, spec.passage_depth, { height: wallHeight, name: "6f-right-end-passage-left-wall" });
  addWall(state.scene, passageX + spec.passage_width / 2, passageZ, 0.14, spec.passage_depth, { height: wallHeight, name: "6f-right-end-passage-right-wall" });
  addLabel("통로", passageX, passageZ, 3.05, 0.48, "#065f46");
  addLabel("오른쪽 계단", stair.x, stair.z, 3.05, 0.58, "#312e81");
}

function addLeftEndFacilities() {
  const layout = { ...DEFAULT_LAYOUT, ...state.data.layout_dimensions };
  const endStairs = state.data.facilities.find((item) => item.id === "4F_4228_END_STAIRS");
  if (!endStairs) return;

  const stairAlongCorridor = endStairs.visual_width_along_corridor || 3.1;
  const stairDepthFromCorridor = endStairs.visual_depth_from_corridor || 6.87;
  const sideSign = (endStairs.side || "lower") === "upper" ? -1 : 1;
  const corridorEdgeZ = sideSign * layout.corridor_width / 2;
  const endX = mapX(layout.main_length);
  const stairX = endX - stairAlongCorridor / 2;
  const stairZ = corridorEdgeZ + sideSign * stairDepthFromCorridor / 2;

  addBox(state.scene, {
    x: stairX,
    z: 0,
    w: stairAlongCorridor,
    d: layout.corridor_width,
    h: 0.09,
    y: 0.045,
    color: palette.corridor,
    name: "4228-end-stair-access-landing"
  });

  addSideEndStair({
    name: "4228-end-stair",
    x: stairX,
    z: stairZ,
    width: stairAlongCorridor,
    depth: stairDepthFromCorridor,
    direction: -1,
    floorHeight: endStairs.floor_height || 4,
    entranceMode: "front",
    showTreadGuides: Number(state.floor) === 4
  });
  if (!state.combinedLayerRendering) {
    addLabel("끝 계단", stairX, stairZ, 3.05, 0.58, "#312e81");
  }
}

function addMainRestroom() {
  const layout = { ...DEFAULT_LAYOUT, ...state.data.layout_dimensions };
  const restroom = state.data.facilities.find((item) => item.id === "4F_MAIN_RESTROOM");
  if (!restroom) return;

  const width = restroom.width || 2.792;
  const sideExpansion = restroom.side_expansion_away_from_elevator ?? 1.1;
  const restroomWidth = width + sideExpansion;
  const x = mapX(restroom.x);
  const restroomX = x - sideExpansion / 2;
  // The Polycam/GLB geometry places this restroom on the same side of the
  // main corridor as the core stem. The evacuation plan is used only for the
  // room-number sequence and must not flip this footprint to the upper row.
  const corridorEdgeZ = layout.corridor_width / 2;
  const outerZ = corridorEdgeZ + layout.room_depth;
  const entrySetback = Math.min(restroom.entry_setback_from_corridor ?? 1.45, layout.room_depth - 1.1);
  const restroomDepth = layout.room_depth - entrySetback;
  const restroomEntryZ = corridorEdgeZ + entrySetback;
  const restroomZ = restroomEntryZ + restroomDepth / 2;
  const openZ = corridorEdgeZ + entrySetback / 2;
  const wallHeight = 2.75;
  const doorWidth = 0.9;
  const frontSegment = (restroomWidth - doorWidth) / 2;

  addBox(state.scene, {
    x: restroomX,
    z: openZ,
    w: restroomWidth,
    d: entrySetback,
    h: 0.025,
    y: 0.075,
    color: 0xf8fafc,
    opacity: 0.34,
    name: "main-restroom-front-open-area"
  });
  addBox(state.scene, {
    x: restroomX,
    z: restroomZ,
    w: restroomWidth,
    d: restroomDepth,
    h: 0.1,
    y: 0.05,
    color: palette.restroom,
    opacity: 0.94,
    name: restroom.id
  });
  addWall(state.scene, restroomX, outerZ, restroomWidth, 0.14, { height: wallHeight });
  addWall(state.scene, restroomX - restroomWidth / 2, restroomZ, 0.14, restroomDepth, { height: wallHeight });
  addWall(state.scene, restroomX + restroomWidth / 2, restroomZ, 0.14, restroomDepth, { height: wallHeight });
  addWall(state.scene, restroomX - (doorWidth + frontSegment) / 2, restroomEntryZ, frontSegment, 0.14, { height: wallHeight });
  addWall(state.scene, restroomX + (doorWidth + frontSegment) / 2, restroomEntryZ, frontSegment, 0.14, { height: wallHeight });
  addBox(state.scene, { x: restroomX, z: restroomEntryZ, w: doorWidth, d: 0.06, h: 2.15, color: palette.door, metalness: 0.25, name: "main-restroom-door" });
  addLabel("진입 공간", restroomX, openZ, 1.05, 0.48, "#64748b");
  addLabel("메인 화장실", restroomX, restroomZ, 3.1, 0.62, "#065f46");

  const elevator = state.data.facilities.find((item) => item.id === "4F_ELEVATOR_BANK");
  const hubHalfWidth = layout.hub_width / 2;
  const sideBayWidth = (layout.hub_outer_width - layout.hub_width) / 2;
  const elevatorX = mapX(elevator?.x ?? HUB_MAP_X - 3.7);
  const elevatorSideSign = Math.sign(elevatorX - HUB_X) || 1;
  const elevatorBoundaryX = HUB_X + elevatorSideSign * hubHalfWidth;
  const elevatorOuterX = HUB_X + elevatorSideSign * (hubHalfWidth + sideBayWidth);
  const noticeStartX = Math.min(elevatorOuterX, elevatorBoundaryX) + 0.16;
  const noticeEndX = Math.max(elevatorOuterX, elevatorBoundaryX) - 0.16;
  const noticeTurnX = noticeEndX;
  const noticeCoreLength = restroom.noticeboard_core_length ?? 3.59;
  const noticeCoreCenterZ = corridorEdgeZ + noticeCoreLength / 2;
  const serviceOuterZ = corridorEdgeZ + layout.room_depth;
  const serviceStartX = restroomX - restroomWidth / 2;
  const serviceEndX = restroomX + restroomWidth / 2;
  const serviceWidth = serviceEndX - serviceStartX;
  addWall(state.scene, (serviceStartX + serviceEndX) / 2, serviceOuterZ, serviceWidth, 0.08, { height: 0.18, color: 0x94a3b8, opacity: 0.55, name: "main-restroom-rear-reference-edge" });
  addWall(state.scene, (noticeStartX + noticeEndX) / 2, corridorEdgeZ, noticeEndX - noticeStartX, 0.12, { height: 1.25, color: 0xeab308, name: "main-corridor-noticeboard-3p93m" });
  addWall(state.scene, noticeTurnX, noticeCoreCenterZ, 0.12, noticeCoreLength, { height: 1.25, color: 0xd1008f, name: "elevator-to-corridor-noticeboard-3p59m" });
  addLabel("게시판 3.93m", (noticeStartX + noticeEndX) / 2, corridorEdgeZ + 0.2, 1.75, 0.48, "#92400e");
  addLabel("게시판 3.59m", noticeTurnX + 0.22, noticeCoreCenterZ, 1.75, 0.44, "#9d174d");
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
  // A ten-floor stack would otherwise create hundreds of canvas textures and
  // shadowed sprites. Combined view keeps floor/vertical-link labels, which are
  // added after each floor layer, while room/facility labels remain available
  // in the corresponding standalone floor view.
  if (state.combinedLayerRendering) return null;
  const sprite = makeTextSprite(text, scale, color);
  sprite.position.set(x, y + (state.floorYOffset || 0), z);
  state.labelGroup.add(sprite);
  return sprite;
}

function addRoom(room) {
  if (room.placement === "extension-marker" || room.placement === "floor6-end-room") return;
  if (room.placement === "free") {
    addFreeRoom(room);
    return;
  }
  const layout = { ...DEFAULT_LAYOUT, ...state.data.layout_dimensions };
  // 2층의 끝 세 방은 현장 수집 좌표와 GLB 정합 전의 방 폭을 분리한다.
  // display_*는 2D 평면의 기둥·진입구 선에 맞춘 렌더링 전용 값이다.
  const authoredWidth = room.display_width || room.width || 4.5;
  const depth = room.depth || layout.room_depth;
  const authoredX = mapX(room.display_x ?? room.x);
  const corridorHalf = layout.corridor_width / 2;
  const z = room.side === "upper"
    ? -(corridorHalf + depth / 2)
    : corridorHalf + depth / 2;
  const target = room.id === state.targetId;
  const wallHeight = 2.75;
  const wallThickness = 0.14;
  const side = room.side || "lower";
  const sharedWallTolerance = 0.04;
  const restroom = state.data.facilities.find((item) => item.id === "4F_RESTROOM");
  const restroomPassageLeftX = restroom?.passage_center_map_x == null
    ? null
    : mapX(restroom.passage_center_map_x) - (restroom.passage_width || 1.262) / 2;
  const restroomPassageRightX = restroom?.passage_center_map_x == null
    ? null
    : mapX(restroom.passage_center_map_x) + (restroom.passage_width || 1.262) / 2;
  const leftEdge = authoredX - authoredWidth / 2;
  const rightEdge = room.extend_to_restroom_passage && restroomPassageLeftX != null
    ? restroomPassageLeftX
    : authoredX + authoredWidth / 2;
  const width = rightEdge - leftEdge;
  const x = (leftEdge + rightEdge) / 2;
  const roomColor = target ? 0xffe2df : palette.roomFloor;
  const outerZ = z + (room.side === "upper" ? -depth / 2 : depth / 2);
  const frontZ = z + (room.side === "upper" ? depth / 2 : -depth / 2);
  const endsAtRestroomPassageLeft = restroomPassageLeftX != null
    && side === (restroom.side || "lower")
    && Math.abs(rightEdge - restroomPassageLeftX) <= sharedWallTolerance;
  const startsAtRestroomPassageRight = restroomPassageRightX != null
    && side === (restroom.side || "lower")
    && Math.abs(leftEdge - restroomPassageRightX) <= sharedWallTolerance;
  const hasNeighborEndingAtLeftEdge = state.data.rooms.some((candidate) => {
    if (candidate === room || candidate.placement || candidate.x == null) return false;
    if ((candidate.side || "lower") !== side) return false;
    const candidateWidth = candidate.display_width || candidate.width || 4.5;
    const candidateX = mapX(candidate.display_x ?? candidate.x);
    const candidateRightEdge = candidateX + candidateWidth / 2;
    return Math.abs(candidateRightEdge - leftEdge) <= sharedWallTolerance;
  });
  const hideDoor = room.hide_door === true;
  const doorWidth = hideDoor ? 0 : Math.min(1.25, Math.max(0.9, width * 0.24));
  const frontSegment = Math.max((width - doorWidth) / 2, 0.3);
  addBox(state.roomGroup, {
    x,
    z,
    w: width,
    d: depth,
    h: 0.1,
    y: 0.05,
    color: roomColor,
    name: room.id
  });
  addWall(state.roomGroup, x, outerZ, width, wallThickness, { height: wallHeight });
  if (!hasNeighborEndingAtLeftEdge && !startsAtRestroomPassageRight) {
    addWall(state.roomGroup, leftEdge, z, wallThickness, depth, { height: wallHeight });
  }
  if (!endsAtRestroomPassageLeft) {
    addWall(state.roomGroup, rightEdge, z, wallThickness, depth, { height: wallHeight });
  }
  if (hideDoor) {
    addWall(state.roomGroup, x, frontZ, width, wallThickness, { height: wallHeight });
  } else {
    addWall(state.roomGroup, x - (doorWidth + frontSegment) / 2, frontZ, frontSegment, wallThickness, { height: wallHeight });
    addWall(state.roomGroup, x + (doorWidth + frontSegment) / 2, frontZ, frontSegment, wallThickness, { height: wallHeight });
    addBox(state.roomGroup, {
      x,
      z: frontZ,
      w: doorWidth,
      d: 0.06,
      h: 2.15,
      color: target ? palette.target : palette.door,
      metalness: 0.25,
      name: `${room.id}-door`
    });
  }
  if (!room.hide_label) {
    addLabel(room.label || room.id, x, frontZ + (room.side === "upper" ? -0.32 : 0.32), 3.15, target ? 0.9 : 0.7, target ? "#b91c1c" : "#1f2937");
  }
}

function getFloor5OutdoorLayout() {
  const layout = { ...DEFAULT_LAYOUT, ...state.data.layout_dimensions };
  const commonLeft = 70;
  const commonRight = 1310;
  const corridorCenterY = 470 + 230 + 32;
  const xScale = layout.main_length / (commonRight - commonLeft);
  const zScale = layout.room_depth / 110;
  const toWorldX = (svgX) => (svgX - (commonLeft + commonRight) / 2) * xScale;
  const toWorldZ = (svgY) => (svgY - corridorCenterY) * zScale;
  const rect = (x1, y1, x2, y2) => {
    const left = Math.min(toWorldX(x1), toWorldX(x2));
    const right = Math.max(toWorldX(x1), toWorldX(x2));
    const nearZ = Math.max(toWorldZ(y1), toWorldZ(y2));
    const farZ = Math.min(toWorldZ(y1), toWorldZ(y2));
    return {
      left,
      right,
      farZ,
      nearZ,
      centerX: (left + right) / 2,
      centerZ: (farZ + nearZ) / 2,
      width: right - left,
      depth: nearZ - farZ
    };
  };

  const outdoor = rect(1018, 85, 1310, 700);
  const upperDoorLeft = toWorldX(1060);
  const upperDoorRight = toWorldX(1118);

  return {
    outdoor,
    toWorldX,
    toWorldZ,
    upperDoor: {
      center: (upperDoorLeft + upperDoorRight) / 2,
      width: Math.abs(upperDoorRight - upperDoorLeft)
    },
    upperDoorZ: toWorldZ(700),
    rightDoorX: mapX(0.9)
  };
}

function addFloor5OutdoorAccess() {
  const wing = getFloor5OutdoorLayout();
  if (!wing) return;

  const rightCorridorEndX = mapX(0.9);
  const edgeOpacity = state.combinedLayerRendering ? 0.28 : 0.62;

  addBox(state.scene, {
    x: wing.outdoor.centerX,
    z: wing.outdoor.centerZ,
    w: wing.outdoor.width,
    d: wing.outdoor.depth,
    h: 0.08,
    y: 0.04,
    color: 0xe8edf4,
    opacity: 1,
    name: "5f-outdoor-zone-floor"
  });
  [
    {
      x: wing.outdoor.centerX,
      z: wing.outdoor.farZ,
      w: wing.outdoor.width,
      d: 0.1,
      name: "5f-outdoor-far-edge"
    },
    {
      x: wing.outdoor.left,
      z: wing.outdoor.centerZ,
      w: 0.1,
      d: wing.outdoor.depth,
      name: "5f-outdoor-left-edge"
    },
    {
      x: wing.outdoor.right,
      z: wing.outdoor.centerZ,
      w: 0.1,
      d: wing.outdoor.depth,
      name: "5f-outdoor-right-edge"
    }
  ].forEach((edge) => {
    addBox(state.scene, {
      ...edge,
      h: 0.08,
      y: 0.13,
      color: 0xd8a307,
      opacity: edgeOpacity
    });
  });
  addBox(state.scene, {
    x: rightCorridorEndX,
    z: 0,
    w: 0.12,
    d: 1.45,
    h: 0.08,
    y: 0.16,
    color: 0x2563eb,
    name: "5f-right-corridor-outdoor-door"
  });
  addBox(state.scene, {
    x: wing.upperDoor.center,
    z: wing.upperDoorZ,
    w: wing.upperDoor.width,
    d: 0.12,
    h: 0.08,
    y: 0.16,
    color: 0x2563eb,
    name: "5f-5111-side-outdoor-door"
  });
  addLabel("5층 야외공간", wing.outdoor.centerX, wing.outdoor.centerZ, 1.45, 0.62, "#9d174d");
  addLabel("야외문", wing.upperDoor.center, wing.upperDoorZ - 0.42, 1.25, 0.42, "#1d4ed8");
  addLabel("복도 끝 야외문", rightCorridorEndX + 0.55, 0, 1.45, 0.42, "#1d4ed8");
}

function getFloor1ExtensionLayout() {
  if (!state.data.floor1_extension) return null;

  const layout = { ...DEFAULT_LAYOUT, ...state.data.layout_dimensions };
  const commonLeft = 70;
  const commonRight = 1310;
  const xScale = layout.main_length / (commonRight - commonLeft);
  const zScale = layout.room_depth / 110;
  const corridorHalf = layout.corridor_width / 2;
  const upperOuterZ = -(corridorHalf + layout.room_depth);
  const lowerOuterZ = corridorHalf + layout.room_depth;
  const toWorldX = (svgX) => (svgX - (commonLeft + commonRight) / 2) * xScale;
  const toUpperZ = (localY) => -corridorHalf - (230 - localY) * zScale;
  const toLowerZ = (localY) => corridorHalf + (localY - 294) * zScale;
  const toExtensionZ = (svgY) => upperOuterZ - (530 - svgY) * zScale;
  const rect = (x1, z1, x2, z2, zMapper) => {
    const left = Math.min(toWorldX(x1), toWorldX(x2));
    const right = Math.max(toWorldX(x1), toWorldX(x2));
    const farZ = Math.min(zMapper(z1), zMapper(z2));
    const nearZ = Math.max(zMapper(z1), zMapper(z2));
    return {
      left,
      right,
      farZ,
      nearZ,
      centerX: (left + right) / 2,
      centerZ: (farZ + nearZ) / 2,
      width: right - left,
      depth: nearZ - farZ
    };
  };

  const restArea = rect(696, 120, 1018, 230, toUpperZ);
  const passageBase = rect(860, 294, 894, 404, toLowerZ);
  const room1213 = state.data.rooms?.find((room) => room.id === "1213");
  const room1210 = state.data.rooms?.find((room) => room.id === "1210");
  let passage = passageBase;
  if (room1213 && room1210) {
    const rawEdgeFrom1213 = room1213.x - room1213.width / 2;
    const rawEdgeFrom1210 = room1210.x + room1210.width / 2;
    const rawLeft = Math.min(rawEdgeFrom1213, rawEdgeFrom1210);
    const rawRight = Math.max(rawEdgeFrom1213, rawEdgeFrom1210);
    if (rawRight - rawLeft > 0.4) {
      const worldA = mapX(rawLeft);
      const worldB = mapX(rawRight);
      const left = Math.min(worldA, worldB);
      const right = Math.max(worldA, worldB);
      const centerX = (left + right) / 2;
      const width = Math.max(right - left + 3.9, passageBase.width);
      passage = {
        ...passageBase,
        left: centerX - width / 2,
        right: centerX + width / 2,
        centerX,
        width
      };
    }
  }
  const adminBounds = state.data.floor1_extension.admin_svg_bounds || [1018, 70, 1310, 400];
  const outdoorBounds = state.data.floor1_extension.outdoor_corridor_svg_bounds || [1018, 410, 1310, 530];
  const extensionRightSvg = Math.max(adminBounds[2], outdoorBounds[2], 1310);
  const extensionFootprint = rect(
    Math.min(adminBounds[0], outdoorBounds[0]),
    Math.min(adminBounds[1], outdoorBounds[1]),
    extensionRightSvg,
    Math.max(adminBounds[3], outdoorBounds[3]),
    toExtensionZ
  );
  const outdoor = rect(outdoorBounds[0], outdoorBounds[1], extensionRightSvg, outdoorBounds[3], toExtensionZ);
  const admin = rect(adminBounds[0], adminBounds[1], extensionRightSvg, adminBounds[3], toExtensionZ);
  const mainEntranceLeft = toWorldX(634);
  const mainEntranceRight = toWorldX(696);
  const mainEntranceCenter = (mainEntranceLeft + mainEntranceRight) / 2;
  const adminDoorWidth = 2.8;

  return {
    toWorldX,
    restArea,
    passage,
    extensionFootprint,
    outdoor,
    admin,
    upperOuterZ,
    lowerOuterZ,
    corridorHalf,
    mainEntranceLeft,
    mainEntranceRight,
    mainEntranceCenter,
    mainEntranceWidth: mainEntranceRight - mainEntranceLeft,
    adminDoor: { center: admin.centerX, width: adminDoorWidth }
  };
}

function addFloor1Extension() {
  const wing = getFloor1ExtensionLayout();
  if (!wing) return;

  const wallHeight = 2.75;
  const targetColor = 0xffe2df;
  const floorColor = (id, color) => state.targetId === id ? targetColor : color;
  const addFloorRect = (box, color, name, id = name) => addBox(state.scene, {
    x: box.centerX,
    z: box.centerZ,
    w: box.width,
    d: box.depth,
    h: 0.11,
    y: 0.055,
    color: floorColor(id, color),
    name
  });
  const addDoorLeaf = ({ hingeX, hingeZ, length, rotation, name }) => {
    const directionX = Math.cos(rotation);
    const directionZ = -Math.sin(rotation);
    const mesh = new THREE.Mesh(
      new THREE.BoxGeometry(length, 2.15, 0.09),
      makeMat(0x475569, 0.5, 1, 0.18)
    );
    mesh.position.set(
      hingeX + directionX * length / 2,
      1.075 + (state.floorYOffset || 0),
      hingeZ + directionZ * length / 2
    );
    mesh.rotation.y = rotation;
    mesh.name = name;
    mesh.castShadow = true;
    state.scene.add(mesh);
  };

  addFloorRect(wing.restArea, 0xe8edf4, "1f-rest-area-floor", "REST-AREA");
  addFloorRect(wing.passage, 0xe8edf4, "1f-1213-1210-passage-floor");
  addFloorRect(wing.extensionFootprint, 0xe4e9ef, "1f-extension-aligned-footprint-floor", "ADMIN");
  addFloorRect(wing.outdoor, 0xf4d9e6, "1f-outdoor-corridor-floor", "OUTDOOR-CORRIDOR");
  addFloorRect(wing.admin, 0xdfe5eb, "1f-admin-floor", "ADMIN");

  addWall(state.scene, wing.restArea.centerX, wing.upperOuterZ, wing.restArea.width, 0.14, {
    height: wallHeight,
    name: "1f-rest-area-outer-wall"
  });

  const halfDoor = wing.mainEntranceWidth / 2;
  addDoorLeaf({
    hingeX: wing.mainEntranceLeft,
    hingeZ: wing.upperOuterZ,
    length: halfDoor,
    rotation: THREE.MathUtils.degToRad(-55),
    name: "1f-main-entrance-left-door"
  });
  addDoorLeaf({
    hingeX: wing.mainEntranceRight,
    hingeZ: wing.upperOuterZ,
    length: halfDoor,
    rotation: THREE.MathUtils.degToRad(-125),
    name: "1f-main-entrance-right-door"
  });

  addWall(state.scene, wing.admin.centerX, wing.admin.farZ, wing.admin.width, 0.16, {
    height: wallHeight,
    name: "1f-admin-far-wall"
  });
  addWall(state.scene, wing.admin.left, wing.admin.centerZ, 0.16, wing.admin.depth, {
    height: wallHeight,
    name: "1f-admin-left-wall"
  });
  addWall(state.scene, wing.admin.right, wing.admin.centerZ, 0.16, wing.admin.depth, {
    height: wallHeight,
    name: "1f-admin-right-wall"
  });
  addWallXSegments(wing.admin.nearZ, wing.admin.left, wing.admin.right, [wing.adminDoor], {
    height: wallHeight,
    name: "1f-admin-entry-wall"
  });
  addDoorLeaf({
    hingeX: wing.adminDoor.center - wing.adminDoor.width / 2,
    hingeZ: wing.admin.nearZ,
    length: wing.adminDoor.width / 2,
    rotation: THREE.MathUtils.degToRad(-50),
    name: "1f-admin-left-door"
  });
  addDoorLeaf({
    hingeX: wing.adminDoor.center + wing.adminDoor.width / 2,
    hingeZ: wing.admin.nearZ,
    length: wing.adminDoor.width / 2,
    rotation: THREE.MathUtils.degToRad(-130),
    name: "1f-admin-right-door"
  });

  [wing.outdoor.left, wing.outdoor.right].forEach((x, index) => {
    addWall(state.scene, x, wing.outdoor.centerZ, 0.12, wing.outdoor.depth, {
      height: 0.95,
      color: 0xb86a8a,
      name: `1f-outdoor-edge-${index + 1}`
    });
  });

  addWall(state.scene, wing.passage.centerX, wing.lowerOuterZ, wing.passage.width, 0.14, {
    height: wallHeight,
    name: "1f-1213-1210-passage-end-wall"
  });
  addBox(state.scene, {
    x: wing.passage.centerX,
    z: wing.corridorHalf,
    w: wing.passage.width,
    d: 0.12,
    h: 0.035,
    y: 0.16,
    color: palette.door,
    metalness: 0.25,
    name: "1f-1213-1210-passage-threshold"
  });

  addLabel("정문", wing.mainEntranceCenter, wing.upperOuterZ - 0.38, 3.15, 0.62, "#0369a1");
  addLabel("휴식공간", wing.restArea.centerX, wing.restArea.centerZ, 1.25, 0.7, "#334155");
  addLabel("야외 복도", wing.outdoor.centerX, wing.outdoor.centerZ, 1.25, 0.72, "#9d174d");
  addLabel("행정실", wing.admin.centerX, wing.admin.centerZ, 1.6, 1.0, "#1f2937");
  addLabel("문 통로", wing.passage.centerX, wing.passage.centerZ, 1.05, 0.46, "#334155");
}

function addFreeRoom(room) {
  const x = room.world_x;
  const z = room.world_z;
  const width = room.width || 4.5;
  const depth = room.depth || 6;
  const target = room.id === state.targetId;
  const wallHeight = 2.75;
  const wallThickness = 0.14;
  const doorWidth = Math.min(1.25, Math.max(0.9, Math.min(width, depth) * 0.24));
  const halfW = width / 2;
  const halfD = depth / 2;

  addBox(state.roomGroup, {
    x, z, w: width, d: depth, h: 0.1, y: 0.05,
    color: target ? 0xffe2df : palette.roomFloor,
    name: room.id
  });

  const splitHorizontalWall = (wallZ, sideName) => {
    if (room.door_side !== sideName) {
      addWall(state.roomGroup, x, wallZ, width, wallThickness, { height: wallHeight });
      return;
    }
    const segment = Math.max((width - doorWidth) / 2, 0.25);
    addWall(state.roomGroup, x - (doorWidth + segment) / 2, wallZ, segment, wallThickness, { height: wallHeight });
    addWall(state.roomGroup, x + (doorWidth + segment) / 2, wallZ, segment, wallThickness, { height: wallHeight });
  };
  const splitVerticalWall = (wallX, sideName) => {
    if (room.door_side !== sideName) {
      addWall(state.roomGroup, wallX, z, wallThickness, depth, { height: wallHeight });
      return;
    }
    const segment = Math.max((depth - doorWidth) / 2, 0.25);
    addWall(state.roomGroup, wallX, z - (doorWidth + segment) / 2, wallThickness, segment, { height: wallHeight });
    addWall(state.roomGroup, wallX, z + (doorWidth + segment) / 2, wallThickness, segment, { height: wallHeight });
  };

  splitHorizontalWall(z - halfD, "front");
  splitHorizontalWall(z + halfD, "back");
  splitVerticalWall(x - halfW, "left");
  splitVerticalWall(x + halfW, "right");

  const labelZ = room.door_side === "front" ? z - halfD + 0.35 : room.door_side === "back" ? z + halfD - 0.35 : z;
  const labelX = room.door_side === "left" ? x - halfW + 0.35 : room.door_side === "right" ? x + halfW - 0.35 : x;
  addLabel(room.label || room.id, labelX, labelZ, 3.15, target ? 0.9 : 0.7, target ? "#b91c1c" : "#1f2937");
}

function getFloor2ExtensionLayout() {
  if (!state.data.floor2_extension) return null;

  const layout = { ...DEFAULT_LAYOUT, ...state.data.layout_dimensions };
  const commonLeft = 70;
  const commonRight = 1310;
  const corridorCenterY = 732;
  const xScale = layout.main_length / (commonRight - commonLeft);
  const zScale = layout.room_depth / 110;
  const toWorldX = (svgX) => (svgX - (commonLeft + commonRight) / 2) * xScale;
  const toWorldZ = (svgY) => (svgY - corridorCenterY) * zScale;
  const rect = (x1, y1, x2, y2) => {
    const left = Math.min(toWorldX(x1), toWorldX(x2));
    const right = Math.max(toWorldX(x1), toWorldX(x2));
    const nearZ = Math.max(toWorldZ(y1), toWorldZ(y2));
    const farZ = Math.min(toWorldZ(y1), toWorldZ(y2));
    return {
      left,
      right,
      farZ,
      nearZ,
      centerX: (left + right) / 2,
      centerZ: (farZ + nearZ) / 2,
      width: right - left,
      depth: nearZ - farZ
    };
  };

  const sSpace = rect(1018, 85, 1068, 585);
  const room21052 = rect(1068, 85, 1146, 335);
  const room21051 = rect(1068, 335, 1146, 585);
  const studyRight = state.data.floor2_extension.study_right_svg_x ?? 1146;
  const extensionCorridorRight = state.data.floor2_extension.extension_corridor_right_svg_x ?? 1198;
  const tdmLeft = state.data.floor2_extension.tdm_left_svg_x ?? 1198;
  const extensionCorridor = rect(1146, 85, extensionCorridorRight, 585);
  const extensionRightSvg = 1310;
  const room21042 = rect(extensionCorridorRight, 85, extensionRightSvg, 335);
  const room21041 = rect(extensionCorridorRight, 335, extensionRightSvg, 585);
  const open2107Left = state.data.floor2_extension.open_2107_left_svg_x ?? 1018;
  const open2107 = rect(open2107Left, 590, 1080, 700);
  const study = rect(1080, 590, studyRight, 700);
  const tdm = rect(tdmLeft, 596, 1310, 700);
  const pillar = rect(1128, 682, 1146, 700);
  const entry = rect(studyRight, 590, tdmLeft, 700);

  return {
    toWorldX,
    toWorldZ,
    sSpace,
    room21052,
    room21051,
    extensionCorridor,
    room21042,
    room21041,
    open2107,
    study,
    tdm,
    pillar,
    entry,
    branchWorldX: (toWorldX(1146) + toWorldX(extensionCorridorRight)) / 2,
    mainEntryZ: toWorldZ(700),
    extensionEntryZ: toWorldZ(585),
    roomSplitZ: toWorldZ(335),
    farZ: toWorldZ(85),
    sSpaceOpening: {
      center: (toWorldX(state.data.floor2_extension.m_space_door_svg_start_x ?? 1035) + toWorldX(state.data.floor2_extension.m_space_door_svg_end_x ?? 1068)) / 2,
      width: Math.abs(toWorldX(state.data.floor2_extension.m_space_door_svg_end_x ?? 1068) - toWorldX(state.data.floor2_extension.m_space_door_svg_start_x ?? 1035))
    },
    corridorOpening: {
      center: (toWorldX(1146) + toWorldX(extensionCorridorRight)) / 2,
      width: Math.abs(toWorldX(extensionCorridorRight) - toWorldX(1146))
    }
  };
}

function addFloor2Extension() {
  const wing = getFloor2ExtensionLayout();
  if (!wing) return;

  const wallHeight = 2.75;
  const doorWidth = state.data.floor2_extension.room_door_width || 1.2;
  const doorColor = 0x38bdf8;
  const targetColor = 0xffe2df;
  const colorFor = (id, color) => state.targetId === id ? targetColor : color;
  const addFloorRect = (box, color, name, id = name) => addBox(state.scene, {
    x: box.centerX,
    z: box.centerZ,
    w: box.width,
    d: box.depth,
    h: 0.11,
    y: 0.045,
    color: colorFor(id, color),
    name
  });

  addFloorRect(wing.sSpace, 0xd9eee8, "2f-m-space-floor", "M-SPACE");
  addFloorRect(wing.room21052, 0xf7e9af, "2f-2105-2-floor", "2105-2");
  addFloorRect(wing.room21051, 0xf7e9af, "2f-2105-1-floor", "2105-1");
  addFloorRect(wing.extensionCorridor, 0xcfe7df, "2f-extension-corridor");
  addFloorRect(wing.room21042, 0xe5e7eb, "2f-2104-2-floor", "2104-2");
  addFloorRect(wing.room21041, 0xe5e7eb, "2f-2104-1-floor", "2104-1");
  addFloorRect(wing.open2107, 0xe8edf4, "2f-2107-open-floor", "2107");
  addFloorRect(wing.study, 0xead7b5, "2f-study-floor", "STUDY");
  addFloorRect(wing.entry, 0xcfe7df, "2f-study-entry-corridor-floor");
  addFloorRect(wing.tdm, 0xdce5f4, "2f-tdm-floor", "TDM");

  const extensionLeft = wing.sSpace.left;
  const extensionRight = Math.max(wing.room21042.right, wing.tdm.right);
  const extensionFarZ = Math.min(wing.sSpace.farZ, wing.room21042.farZ);
  const extensionNearZ = Math.max(wing.sSpace.nearZ, wing.room21041.nearZ);
  const extensionCenterZ = (extensionFarZ + extensionNearZ) / 2;
  const extensionDepth = extensionNearZ - extensionFarZ;
  addWall(state.scene, extensionLeft, extensionCenterZ, 0.14, extensionDepth, { height: wallHeight, name: "2f-extension-left-wall" });
  addWall(state.scene, extensionRight, extensionCenterZ, 0.14, extensionDepth, { height: wallHeight, name: "2f-extension-right-wall" });
  addWall(state.scene, (extensionLeft + extensionRight) / 2, wing.farZ, extensionRight - extensionLeft, 0.14, { height: wallHeight, name: "2f-extension-far-wall" });

  addWall(state.scene, wing.sSpace.right, wing.sSpace.centerZ, 0.14, wing.sSpace.depth, { height: wallHeight, name: "2f-m-space-room-wall" });
  addWallXSegments(wing.sSpace.nearZ, wing.sSpace.left, wing.sSpace.right, [wing.sSpaceOpening], {
    height: wallHeight,
    name: "2f-m-space-near-wall-with-door"
  });
  addWall(state.scene, wing.open2107.right, wing.open2107.centerZ, 0.14, wing.open2107.depth, {
    height: wallHeight,
    name: "2f-2107-study-exterior-wall"
  });
  addWallZSegments(wing.extensionCorridor.left, wing.extensionCorridor.farZ, wing.extensionCorridor.nearZ, [
    { center: wing.room21052.centerZ, width: doorWidth },
    { center: wing.room21051.centerZ, width: doorWidth }
  ], { height: wallHeight, name: "2f-2105-corridor-wall" });
  addWallZSegments(wing.extensionCorridor.right, wing.extensionCorridor.farZ, wing.extensionCorridor.nearZ, [
    { center: wing.room21042.centerZ, width: doorWidth },
    { center: wing.room21041.centerZ, width: doorWidth }
  ], { height: wallHeight, name: "2f-2104-corridor-wall" });
  addWall(state.scene, wing.room21052.centerX, wing.roomSplitZ, wing.room21052.width, 0.14, { height: wallHeight, name: "2f-2105-divider" });
  addWall(state.scene, wing.room21042.centerX, wing.roomSplitZ, wing.room21042.width, 0.14, { height: wallHeight, name: "2f-2104-divider" });
  addWall(state.scene, wing.room21051.centerX, wing.room21051.nearZ, wing.room21051.width, 0.14, { height: wallHeight, name: "2f-2105-1-near-outer-wall" });
  addWall(state.scene, wing.room21041.centerX, wing.room21041.nearZ, wing.room21041.width, 0.14, { height: wallHeight, name: "2f-2104-1-near-outer-wall" });
  addWall(state.scene, wing.tdm.left, wing.tdm.centerZ, 0.14, wing.tdm.depth, { height: wallHeight, name: "2f-tdm-left-wall" });
  addWall(state.scene, wing.tdm.right, wing.tdm.centerZ, 0.14, wing.tdm.depth, { height: wallHeight, name: "2f-tdm-right-wall" });
  addWall(state.scene, wing.tdm.centerX, wing.tdm.farZ, wing.tdm.width, 0.14, { height: wallHeight, name: "2f-tdm-far-wall" });
  addWall(state.scene, wing.tdm.centerX, wing.tdm.nearZ, wing.tdm.width, 0.14, { height: wallHeight, name: "2f-tdm-near-wall" });

  const pillarSize = Math.min(wing.pillar.width, wing.pillar.depth);
  addBox(state.scene, {
    x: wing.pillar.centerX,
    z: wing.pillar.centerZ,
    w: pillarSize,
    d: pillarSize,
    h: wallHeight,
    y: wallHeight / 2,
    color: 0xb88b2d,
    name: "2f-square-column"
  });

  const deskColor = 0x9a6a35;
  const addDesk = (x1, y1, x2, y2, name, color = deskColor) => {
    const box = {
      left: Math.min(wing.toWorldX(x1), wing.toWorldX(x2)),
      right: Math.max(wing.toWorldX(x1), wing.toWorldX(x2)),
      farZ: Math.min(wing.toWorldZ(y1), wing.toWorldZ(y2)),
      nearZ: Math.max(wing.toWorldZ(y1), wing.toWorldZ(y2))
    };
    addBox(state.scene, {
      x: (box.left + box.right) / 2,
      z: (box.farZ + box.nearZ) / 2,
      w: box.right - box.left,
      d: box.nearZ - box.farZ,
      h: 0.72,
      y: 0.38,
      color,
      name
    });
  };
  addDesk(1067, 590, 1080, 678, "2f-2107-high-ceiling-facing-study-desk", 0x4a4f57);
  addDesk(1080, 687, 1115, 700, "2f-u-desk-front");
  addDesk(1080, 620, 1093, 687, "2f-u-desk-side");
  [1080, 1094, 1108, 1122, 1136].forEach((x, index) => {
    addDesk(x, 590, x + 10, 598, `2f-study-single-table-${index + 1}`);
  });

  [
    [wing.extensionCorridor.left, wing.room21052.centerZ, "2f-2105-2-door"],
    [wing.extensionCorridor.left, wing.room21051.centerZ, "2f-2105-1-door"],
    [wing.extensionCorridor.right, wing.room21042.centerZ, "2f-2104-2-door"],
    [wing.extensionCorridor.right, wing.room21041.centerZ, "2f-2104-1-door"]
  ].forEach(([x, z, name]) => addBox(state.scene, { x, z, w: 0.12, d: doorWidth, h: 0.05, y: 0.16, color: doorColor, name }));
  addBox(state.scene, { x: wing.branchWorldX, z: wing.mainEntryZ, w: wing.corridorOpening.width, d: 0.12, h: 0.05, y: 0.16, color: doorColor, name: "2f-main-extension-entry" });
  addBox(state.scene, { x: wing.sSpaceOpening.center, z: wing.extensionEntryZ, w: wing.sSpaceOpening.width, d: 0.12, h: 0.05, y: 0.16, color: doorColor, name: "2f-2107-m-space-entry" });

  addLabel("M-space", wing.sSpace.centerX, wing.sSpace.centerZ, 1.05, 0.55, "#22584d");
  addLabel("2105-2", wing.room21052.centerX, wing.room21052.centerZ, 1.15, 0.62, "#1f2937");
  addLabel("2105-1", wing.room21051.centerX, wing.room21051.centerZ, 1.15, 0.62, "#1f2937");
  addLabel("증축부 복도", wing.extensionCorridor.centerX, wing.extensionCorridor.centerZ, 1.0, 0.5, "#22584d");
  addLabel("2104-2", wing.room21042.centerX, wing.room21042.centerZ, 1.15, 0.62, "#1f2937");
  addLabel("2104-1", wing.room21041.centerX, wing.room21041.centerZ, 1.15, 0.62, "#1f2937");
  addLabel("2107 개방공간", wing.open2107.centerX, wing.open2107.centerZ, 1.0, 0.52, "#334155");
  addLabel("ㄷ자 학습공간", wing.study.left + wing.study.width * 0.28, wing.study.centerZ, 1.25, 0.52, "#7c4a18");
  addLabel("진입 복도", wing.entry.centerX, wing.entry.centerZ, 0.92, 0.48, "#22584d");
  addLabel("TDM", wing.tdm.centerX, wing.tdm.centerZ, 1.15, 0.62, "#1e3a8a");
  addLabel("기둥", wing.pillar.centerX, wing.pillar.centerZ, 3.15, 0.4, "#8a5b12");
}

function getFloor3ExtensionLayout() {
  const ext = state.data.floor3_extension;
  if (!ext) return null;

  const layout = { ...DEFAULT_LAYOUT, ...state.data.layout_dimensions };
  const svg = {
    commonLeft: 70,
    commonRight: 1310,
    corridorCenterY: 470 + 230 + 32
  };
  const xScale = layout.main_length / (svg.commonRight - svg.commonLeft);
  const zScale = layout.room_depth / 110;
  const toWorldX = (svgX) => (svgX - (svg.commonLeft + svg.commonRight) / 2) * xScale;
  const toWorldZ = (svgY) => (svgY - svg.corridorCenterY) * zScale;
  const rect = (x1, y1, x2, y2) => {
    const left = Math.min(toWorldX(x1), toWorldX(x2));
    const right = Math.max(toWorldX(x1), toWorldX(x2));
    const nearZ = Math.max(toWorldZ(y1), toWorldZ(y2));
    const farZ = Math.min(toWorldZ(y1), toWorldZ(y2));
    return {
      left,
      right,
      farZ,
      nearZ,
      centerX: (left + right) / 2,
      centerZ: (farZ + nearZ) / 2,
      width: right - left,
      depth: nearZ - farZ
    };
  };

  const free = rect(1146, 455, 1282, 585);
  const corridor = rect(1146, 85, 1192, 455);
  const itHall = rect(1018, 85, 1146, 455);
  const itHallLower = rect(1018, 455, 1146, 585);
  const unknownSpace = rect(1082, 455, 1146, 520);
  const stair = rect(1082, 520, 1146, 585);
  const room31041 = rect(1198, 85, 1282, 270);
  const room31042 = rect(1198, 270, 1282, 455);
  const entryStartX = toWorldX(1180);
  const entryEndX = toWorldX(1248);
  const entryZ = toWorldZ(590);
  const branchWorldX = (entryStartX + entryEndX) / 2;
  const sideSign = -1;

  return {
    sideSign,
    branchWorldX,
    entryZ,
    entryStartX,
    entryEndX,
    entryWidth: Math.abs(entryEndX - entryStartX),
    leftBoundX: free.left,
    rightBoundX: free.right,
    corridorX: corridor.centerX,
    corridorLeftX: corridor.left,
    corridorRightX: corridor.right,
    totalWidth: free.width,
    corridorWidth: corridor.width,
    freeDepth: free.depth,
    corridorLength: corridor.depth,
    freeCenterZ: free.centerZ,
    freeBackZ: free.farZ,
    farZ: corridor.farZ,
    deepCenterZ: corridor.centerZ,
    splitZ: (room31041.nearZ + room31042.farZ) / 2,
    nearRoomCenterZ: room31042.centerZ,
    farRoomCenterZ: room31041.centerZ,
    itHallX: itHall.centerX,
    itHallWidth: itHall.width,
    room3104X: room31042.centerX,
    room3104Width: room31042.width,
    itHallDoorZ: stair.centerZ,
    itHallLowerX: itHallLower.centerX,
    itHallLowerZ: itHallLower.centerZ,
    room3104NearDoorZ: room31042.centerZ,
    room3104FarDoorZ: room31041.centerZ,
    free,
    corridor,
    itHall,
    itHallLower,
    unknownSpace,
    room31041,
    room31042,
    stair
  };
}

function addWallXSegments(z, xStart, xEnd, openings = [], options = {}) {
  const minX = Math.min(xStart, xEnd);
  const maxX = Math.max(xStart, xEnd);
  let cursor = minX;
  const sorted = openings
    .map(({ center, width }) => ({ start: center - width / 2, end: center + width / 2 }))
    .sort((a, b) => a.start - b.start);

  sorted.forEach((opening, index) => {
    const start = Math.max(minX, opening.start);
    const end = Math.min(maxX, opening.end);
    if (start - cursor > 0.08) {
      addWall(state.scene, (cursor + start) / 2, z, start - cursor, 0.14, {
        ...options,
        name: `${options.name || "x-wall"}-${index + 1}`
      });
    }
    cursor = Math.max(cursor, end);
  });
  if (maxX - cursor > 0.08) {
    addWall(state.scene, (cursor + maxX) / 2, z, maxX - cursor, 0.14, {
      ...options,
      name: `${options.name || "x-wall"}-end`
    });
  }
}

function addWallZSegments(x, zStart, zEnd, openings = [], options = {}) {
  const minZ = Math.min(zStart, zEnd);
  const maxZ = Math.max(zStart, zEnd);
  let cursor = minZ;
  const sorted = openings
    .map(({ center, width }) => ({ start: center - width / 2, end: center + width / 2 }))
    .sort((a, b) => a.start - b.start);

  sorted.forEach((opening, index) => {
    const start = Math.max(minZ, opening.start);
    const end = Math.min(maxZ, opening.end);
    if (start - cursor > 0.08) {
      addWall(state.scene, x, (cursor + start) / 2, 0.14, start - cursor, {
        ...options,
        name: `${options.name || "z-wall"}-${index + 1}`
      });
    }
    cursor = Math.max(cursor, end);
  });
  if (maxZ - cursor > 0.08) {
    addWall(state.scene, x, (cursor + maxZ) / 2, 0.14, maxZ - cursor, {
      ...options,
      name: `${options.name || "z-wall"}-end`
    });
  }
}

function addFloor3Extension() {
  const ext = state.data.floor3_extension;
  const wing = getFloor3ExtensionLayout();
  if (!ext || !wing) return;

  const wallHeight = 2.75;
  const doorWidth = ext.it_hall_door_width || 1.2;
  const entryOpen = { center: wing.branchWorldX, width: wing.entryWidth };
  const corridorDoorOpen = { center: wing.corridorX, width: wing.corridorWidth + 0.35 };
  const doorMarkerColor = 0x38bdf8;

  addBox(state.scene, {
    x: wing.branchWorldX,
    z: wing.freeCenterZ,
    w: wing.totalWidth,
    d: wing.freeDepth,
    h: 0.12,
    y: 0.03,
    color: 0xf4d7ef,
    name: "3f-front-free-space"
  });
  addBox(state.scene, {
    x: wing.corridorX,
    z: wing.deepCenterZ,
    w: wing.corridorWidth,
    d: wing.corridorLength,
    h: 0.12,
    y: 0.035,
    color: palette.scanRight,
    name: "3f-extension-corridor"
  });
  addBox(state.scene, {
    x: wing.itHallX,
    z: wing.deepCenterZ,
    w: wing.itHallWidth,
    d: wing.corridorLength,
    h: 0.1,
    y: 0.04,
    color: 0xddebf7,
    name: "3f-it-hall-floor"
  });
  addBox(state.scene, {
    x: wing.itHallLowerX,
    z: wing.itHallLowerZ,
    w: wing.itHallLower.width,
    d: wing.itHallLower.depth,
    h: 0.1,
    y: 0.04,
    color: 0xe8edf4,
    name: "3f-it-hall-lower-floor"
  });
  addBox(state.scene, {
    x: wing.unknownSpace.centerX,
    z: wing.unknownSpace.centerZ,
    w: wing.unknownSpace.width,
    d: wing.unknownSpace.depth,
    h: 0.11,
    y: 0.055,
    color: 0xf1f5f9,
    name: "3f-it-hall-lower-unknown-space"
  });
  addBox(state.scene, {
    x: wing.room3104X,
    z: wing.nearRoomCenterZ,
    w: wing.room3104Width,
    d: wing.room31042.depth,
    h: 0.1,
    y: 0.04,
    color: 0xe5e7eb,
    name: "3f-3104-2-floor"
  });
  addBox(state.scene, {
    x: wing.room3104X,
    z: wing.farRoomCenterZ,
    w: wing.room3104Width,
    d: wing.room31041.depth,
    h: 0.1,
    y: 0.04,
    color: 0xe5e7eb,
    name: "3f-3104-1-floor"
  });

  addWallXSegments(wing.entryZ, wing.leftBoundX, wing.rightBoundX, [entryOpen], {
    height: wallHeight,
    name: "3f-3203-boundary-blocked-wall"
  });
  addWallZSegments(wing.leftBoundX, wing.free.nearZ, wing.free.farZ, [
    { center: wing.stair.centerZ, width: Math.min(wing.stair.depth, doorWidth + 0.5) }
  ], {
    height: wallHeight,
    name: "3f-free-space-left-wall-with-stair-entry"
  });
  addWall(state.scene, wing.rightBoundX, wing.freeCenterZ, 0.14, wing.freeDepth, { height: wallHeight, name: "3f-free-space-right-wall" });
  addWallXSegments(wing.freeBackZ, wing.leftBoundX, wing.rightBoundX, [corridorDoorOpen], {
    height: wallHeight,
    name: "3f-free-space-back-wall-with-corridor-opening"
  });

  addWall(state.scene, wing.itHall.left, wing.deepCenterZ, 0.14, wing.corridorLength, { height: wallHeight, name: "3f-it-hall-outer-wall" });
  addWall(state.scene, wing.corridorLeftX, wing.deepCenterZ, 0.14, wing.corridorLength, {
    height: wallHeight,
    name: "3f-it-hall-corridor-wall"
  });
  addWall(state.scene, wing.itHallX, wing.farZ, wing.itHallWidth, 0.14, {
    height: wallHeight,
    name: "3f-it-hall-far-wall"
  });
  addWallZSegments(wing.itHall.left, wing.itHallLower.nearZ, wing.itHallLower.farZ, [], {
    height: wallHeight,
    name: "3f-it-hall-lower-left-wall"
  });
  addWallXSegments(wing.itHallLower.nearZ, wing.itHallLower.left, wing.itHallLower.right, [], {
    height: wallHeight,
    name: "3f-it-hall-lower-front-wall"
  });
  addWallZSegments(wing.itHallLower.right, wing.itHallLower.nearZ, wing.itHallLower.farZ, [
    { center: wing.stair.centerZ, width: Math.min(wing.stair.depth, doorWidth + 0.5) }
  ], {
    height: wallHeight,
    name: "3f-it-hall-lower-right-wall-with-free-space-entry"
  });

  addWall(state.scene, wing.rightBoundX, wing.deepCenterZ, 0.14, wing.corridorLength, { height: wallHeight, name: "3f-3104-outer-wall" });
  addWallZSegments(wing.corridorRightX, wing.freeBackZ, wing.farZ, [
    { center: wing.room3104NearDoorZ, width: doorWidth },
    { center: wing.room3104FarDoorZ, width: doorWidth }
  ], {
    height: wallHeight,
    name: "3f-3104-corridor-wall"
  });
  addWall(state.scene, wing.room3104X, wing.splitZ, wing.room3104Width, 0.14, {
    height: wallHeight,
    name: "3f-3104-room-divider"
  });
  addWall(state.scene, wing.room3104X, wing.farZ, wing.room3104Width, 0.14, {
    height: wallHeight,
    name: "3f-3104-far-wall"
  });

  addBox(state.scene, {
    x: wing.branchWorldX,
    z: wing.entryZ,
    w: wing.entryWidth,
    d: 0.11,
    h: 0.04,
    y: 0.13,
    color: doorMarkerColor,
    name: "3f-3203-free-space-entry"
  });
  addBox(state.scene, {
    x: wing.itHall.left + wing.itHallWidth * 0.28,
    z: wing.itHall.nearZ,
    w: doorWidth,
    d: 0.12,
    h: 0.05,
    y: 0.16,
    color: doorMarkerColor,
    name: "3f-it-hall-lower-door-1"
  });
  addBox(state.scene, {
    x: wing.itHall.left + wing.itHallWidth * 0.58,
    z: wing.itHall.nearZ,
    w: doorWidth,
    d: 0.12,
    h: 0.05,
    y: 0.16,
    color: doorMarkerColor,
    name: "3f-it-hall-lower-door-2"
  });
  const stairDepth = wing.stair.width;
  const stairWidth = wing.stair.depth;
  const stairCenterX = wing.stair.centerX;
  addBox(state.scene, {
    x: stairCenterX,
    z: wing.itHallDoorZ,
    w: stairDepth,
    d: stairWidth,
    h: 0.06,
    y: 0.08,
    color: 0xe6ecf5,
    opacity: 0.92,
    name: "3f-it-hall-entry-stair-floor"
  });
  for (let index = 0; index < 5; index += 1) {
    const progress = (index + 0.5) / 5;
    addBox(state.scene, {
      x: wing.stair.left + stairDepth * progress,
      z: wing.itHallDoorZ,
      w: 0.055,
      d: stairWidth - 0.12,
      h: 0.08 + index * 0.035,
      y: 0.12 + index * 0.018,
      color: 0xb8c5d1,
      name: `3f-it-hall-entry-stair-step-${index + 1}`
    });
  }
  addLabel("IT홀 진입계단", stairCenterX, wing.itHallDoorZ - stairWidth / 2 - 0.36, 0.72, 0.38, "#1d4ed8");
  addBox(state.scene, {
    x: wing.corridorRightX,
    z: wing.room3104NearDoorZ,
    w: 0.12,
    d: doorWidth,
    h: 0.05,
    y: 0.16,
    color: doorMarkerColor,
    name: "3f-3104-2-door"
  });
  addBox(state.scene, {
    x: wing.corridorRightX,
    z: wing.room3104FarDoorZ,
    w: 0.12,
    d: doorWidth,
    h: 0.05,
    y: 0.16,
    color: doorMarkerColor,
    name: "3f-3104-1-door"
  });

  addLabel("자유공간", wing.branchWorldX, wing.freeCenterZ, 0.95, 0.72, "#9d277c");
  addLabel("증축부 복도", wing.corridorX, wing.deepCenterZ, 1.05, 0.55, "#22584d");
  addLabel("IT홀", wing.itHallX, wing.deepCenterZ, 1.2, 0.75, "#0369a1");
  addLabel("3104-2", wing.room3104X, wing.nearRoomCenterZ, 1.15, 0.65, "#1f2937");
  addLabel("3104-1", wing.room3104X, wing.farRoomCenterZ, 1.15, 0.65, "#1f2937");
  addLabel("3203 라인 첫 입구", wing.branchWorldX, wing.entryZ + wing.sideSign * 0.8, 0.8, 0.5, "#2563eb");
  addLabel("나머지 경계는 벽", wing.leftBoundX + 1.15, wing.entryZ + wing.sideSign * 0.32, 0.85, 0.42, "#b91c1c");
}

function addFacility(facility) {
  if (["4F_4228_END_STAIRS", "4F_ELEVATOR_BANK", "4F_CENTER_STAIRS", "4F_MAIN_RESTROOM", "4F_RESTROOM", "4F_4204_END_STAIRS"].includes(facility.id)) {
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

function getRightEndStairPlacement(layout, stair = {}) {
  const width = stair.visual_width_along_corridor || stair.depth_from_corridor || 3.1;
  const depth = stair.visual_depth_from_corridor || stair.width_along_corridor || 6.87;
  const anchorWidth = stair.entry_anchor_width_along_corridor || Math.min(width, 3.1);
  const landingWidth = Math.min(
    Math.max(stair.entry_landing_width || 1.55, 1.1),
    Math.max(width - 1.45, 1.1)
  );
  const alignFirstFlightToCorridorEnd = new Set([1, 2, 3, 4, 5]).has(Number(state.floor));
  // For the selected floors, the left edge of the first 12-step flight—not
  // the entry landing—must meet the terminal line of the right corridor.
  const startX = mapX(0) - (alignFirstFlightToCorridorEnd ? landingWidth : anchorWidth);
  const sideSign = (stair.side || "lower") === "upper" ? -1 : 1;
  return {
    x: startX + width / 2,
    startX,
    endX: startX + width,
    z: sideSign * layout.corridor_width / 2 + sideSign * depth / 2,
    width,
    depth,
    sideSign,
    flightStartX: startX + landingWidth
  };
}

function addRoute() {
  state.routeGroup.clear();
  state.markerGroup.clear();
  const room = state.data.rooms.find((item) => item.id === state.targetId);
  if (!room) return;

  const layout = { ...DEFAULT_LAYOUT, ...state.data.layout_dimensions };
  const hub = state.data.routing.hub_junction;
  const junction = new THREE.Vector3(mapX(hub.x), 0.16, mapZ(hub.y));
  // 경로 수집과 동일하게 코어에서 메인복도로 나오는 교차점에서 시작한다.
  // 코어 내부 임시 좌표에서 시작하면 복도 중앙선과 어긋난 안내선이 생긴다.
  const start = junction.clone();
  let dest;
  let points;
  if (room.placement === "free" || room.placement === "extension-marker") {
    if (state.floor === 1) {
      const wing = getFloor1ExtensionLayout();
      const targetByZone = {
        "rest-area": wing.restArea,
        "outdoor-corridor": wing.outdoor,
        "admin": wing.admin
      };
      const target = targetByZone[room.extension_zone] || wing.restArea;
      const corridorBranch = new THREE.Vector3(target.centerX, 0.16, 0);
      dest = new THREE.Vector3(target.centerX, 0.16, target.centerZ);
      if (room.extension_zone === "rest-area") {
        points = [start, corridorBranch, dest];
      } else {
        const entranceBranch = new THREE.Vector3(wing.mainEntranceCenter, 0.16, 0);
        const mainEntrance = new THREE.Vector3(wing.mainEntranceCenter, 0.16, wing.upperOuterZ);
        const outdoorTurn = new THREE.Vector3(target.centerX, 0.16, wing.upperOuterZ);
        if (room.extension_zone === "admin") {
          const adminEntrance = new THREE.Vector3(wing.adminDoor.center, 0.16, wing.admin.nearZ);
          points = [start, entranceBranch, mainEntrance, outdoorTurn, adminEntrance, dest];
        } else {
          points = [start, entranceBranch, mainEntrance, outdoorTurn, dest];
        }
      }
    } else if (state.floor === 2) {
      const wing = getFloor2ExtensionLayout();
      const targetByZone = {
        "2107": wing.open2107,
        "m-space": wing.sSpace,
        "study": wing.study,
        "tdm": wing.tdm,
        "2105-1": wing.room21051,
        "2105-2": wing.room21052,
        "2104-1": wing.room21041,
        "2104-2": wing.room21042
      };
      const target = targetByZone[room.extension_zone] || wing.open2107;
      const extensionJunction = new THREE.Vector3(wing.branchWorldX, 0.16, 0);
      const mainEntry = new THREE.Vector3(wing.branchWorldX, 0.16, wing.mainEntryZ);
      const open2107Corridor = new THREE.Vector3(wing.open2107.centerX, 0.16, 0);
      const open2107Entry = new THREE.Vector3(wing.open2107.centerX, 0.16, wing.open2107.nearZ);
      dest = new THREE.Vector3(target.centerX, 0.16, target.centerZ);
      if (room.extension_zone === "2107") {
        // 2107은 메인복도에서 바로 들어간다. 학습공간 외벽을 가로지르지 않는다.
        points = [start, open2107Corridor, open2107Entry, dest];
      } else if (room.extension_zone === "study" || room.extension_zone === "tdm") {
        points = [start, extensionJunction, mainEntry, dest];
      } else if (room.extension_zone === "m-space") {
        const sSpaceEntry = new THREE.Vector3(wing.sSpaceOpening.center, 0.16, wing.extensionEntryZ);
        points = [start, open2107Corridor, open2107Entry, sSpaceEntry, dest];
      } else {
        const corridorEntry = new THREE.Vector3(wing.branchWorldX, 0.16, wing.extensionEntryZ);
        const corridorTarget = new THREE.Vector3(wing.extensionCorridor.centerX, 0.16, target.centerZ);
        points = [start, extensionJunction, mainEntry, corridorEntry, corridorTarget, dest];
      }
    } else {
      const wing = getFloor3ExtensionLayout();
    const targetByZone = {
      "it-hall": { x: wing.itHallX, z: wing.itHall.nearZ - 1.1, corridorZ: wing.itHallDoorZ },
      "3104-1": { x: wing.room3104X, z: wing.farRoomCenterZ, corridorZ: wing.room3104FarDoorZ },
      "3104-2": { x: wing.room3104X, z: wing.nearRoomCenterZ, corridorZ: wing.room3104NearDoorZ },
      "front-free-space": { x: wing.branchWorldX, z: wing.freeCenterZ, corridorZ: wing.freeCenterZ }
    };
    const target = room.placement === "extension-marker"
      ? targetByZone[room.extension_zone] || targetByZone["front-free-space"]
      : { x: room.destination_x, z: room.destination_z, corridorZ: room.destination_z };
    const extensionJunction = new THREE.Vector3(wing.branchWorldX, 0.16, 0);
    const entryPoint = new THREE.Vector3(wing.branchWorldX, 0.16, wing.entryZ);
    dest = new THREE.Vector3(target.x, 0.16, target.z);
    if (room.extension_zone === "it-hall") {
      const stairTurn = new THREE.Vector3(wing.branchWorldX, 0.16, wing.itHallDoorZ);
      const stairEntry = new THREE.Vector3(wing.stair.centerX, 0.16, wing.itHallDoorZ);
      points = [start, extensionJunction, entryPoint, stairTurn, stairEntry, dest];
    } else {
      const corridorPoint = new THREE.Vector3(wing.corridorX, 0.16, target.corridorZ);
      points = [start, extensionJunction, entryPoint, corridorPoint, dest];
    }
    }
  } else {
    // Standard-floor data is authored from the 2D room centerline. Floors that
    // do not need a separately measured doorway use that 2D coordinate at the
    // main-corridor centerline as their route entry point.
    const roomDepth = room.depth || layout.room_depth;
    const roomZ = room.side === "upper"
      ? -(layout.corridor_width / 2 + roomDepth / 2)
      : layout.corridor_width / 2 + roomDepth / 2;
    const visualFront = room.display_front_x ?? room.display_x ?? room.front_x;
    dest = new THREE.Vector3(mapX(room.display_x ?? room.x), 0.16, roomZ);
    points = [start, new THREE.Vector3(mapX(visualFront), 0.16, 0), dest];
  }
  for (let index = 0; index < points.length - 1; index += 1) {
    const from = points[index];
    const to = points[index + 1];
    const horizontal = Math.abs(to.x - from.x) >= Math.abs(to.z - from.z);
    addBox(state.routeGroup, {
      x: (from.x + to.x) / 2,
      z: (from.z + to.z) / 2,
      w: horizontal ? Math.abs(to.x - from.x) + 0.22 : 0.22,
      d: horizontal ? 0.22 : Math.abs(to.z - from.z) + 0.22,
      h: 0.055,
      y: 0.155,
      color: palette.route,
      name: `route-segment-${index + 1}`
    });
  }

  const currentMarker = new THREE.Mesh(
    new THREE.CylinderGeometry(0.42, 0.42, 0.08, 32),
    makeMat(palette.current, 0.65)
  );
  currentMarker.position.set(start.x, 0.2 + (state.floorYOffset || 0), start.z);
  currentMarker.name = "current-position";
  currentMarker.castShadow = true;
  state.markerGroup.add(currentMarker);
  addLabel("현재", start.x, start.z - 1.9, 1.45, 0.7, "#166534");

  const targetMarker = new THREE.Mesh(
    new THREE.CylinderGeometry(0.5, 0.5, 0.1, 32),
    makeMat(palette.target, 0.65)
  );
  targetMarker.position.set(dest.x, 0.22 + (state.floorYOffset || 0), dest.z);
  targetMarker.name = "target-position";
  targetMarker.castShadow = true;
  state.markerGroup.add(targetMarker);
  addLabel("목적지", dest.x, dest.z - 1.9, 1.55, 0.7, "#b91c1c");
}

function addScanHints(clear = true) {
  if (clear) state.hintGroup.clear();
  const layout = { ...DEFAULT_LAYOUT, ...state.data.layout_dimensions };
  const leftCenter = layout.left_corridor_length / 2;
  const rightStart = layout.left_corridor_length + layout.hub_outer_width;
  const rightCenter = rightStart + layout.right_corridor_length / 2;
  addBox(state.hintGroup, {
    x: mapX(leftCenter),
    z: 0,
    w: layout.left_corridor_length,
    d: 0.22,
    h: 0.05,
    y: 0.1,
    color: palette.scanLeft,
    opacity: 0.35,
    name: "left-scan-reference"
  });
  addBox(state.hintGroup, {
    x: mapX(rightCenter),
    z: 0,
    w: layout.right_corridor_length,
    d: 0.22,
    h: 0.05,
    y: 0.1,
    color: palette.scanRight,
    opacity: 0.36,
    name: "right-scan-reference"
  });
}

function resetScene() {
  state.scene.clear();
  state.scene.background = new THREE.Color(0xf5f7fa);

  const ambient = new THREE.HemisphereLight(0xffffff, 0xcbd5e1, 2.2);
  state.scene.add(ambient);

  const sun = new THREE.DirectionalLight(0xffffff, 2.4);
  sun.position.set(10, 24, 18);
  sun.castShadow = true;
  sun.shadow.mapSize.set(2048, 2048);
  sun.shadow.camera.left = -75;
  sun.shadow.camera.right = 75;
  sun.shadow.camera.top = 30;
  sun.shadow.camera.bottom = -30;
  state.scene.add(sun);

  state.roomGroup = new THREE.Group();
  state.labelGroup = new THREE.Group();
  state.hintGroup = new THREE.Group();
  state.routeGroup = new THREE.Group();
  state.markerGroup = new THREE.Group();
  state.scene.add(state.roomGroup, state.hintGroup, state.routeGroup, state.markerGroup, state.labelGroup);
}

function addFloorGeometry({ includeRoute = true, includeHints = true } = {}) {
  const layout = { ...DEFAULT_LAYOUT, ...state.data.layout_dimensions };
  const corridorEdge = layout.corridor_width / 2;
  const upperEndRoom = Number(state.floor) >= 6
    ? state.data.rooms.find((room) => room.id === `${state.floor}103`)
    : null;
  // Floors 6 and above stop their upper-side footprint at the 103 room end line.
  const upperFloorRightX = upperEndRoom
    ? mapX(upperEndRoom.x - upperEndRoom.width / 2)
    : mapX(0);
  const upperFloorLeftX = mapX(layout.main_length);
  const upperFloorLength = upperFloorRightX - upperFloorLeftX;
  const lowerFloorLength = layout.main_length;
  const upperBandMinZ = -layout.main_depth / 2;
  const upperBandMaxZ = corridorEdge;
  addBox(state.scene, {
    x: (upperFloorLeftX + upperFloorRightX) / 2,
    z: (upperBandMinZ + upperBandMaxZ) / 2,
    w: upperFloorLength,
    d: upperBandMaxZ - upperBandMinZ,
    h: 0.18,
    y: -0.09,
    color: palette.floor,
    opacity: state.combinedLayerRendering ? 0.38 : 1,
    name: "main-floor-base-upper"
  });
  addBox(state.scene, {
    x: mapX(lowerFloorLength / 2),
    z: (corridorEdge + layout.main_depth / 2) / 2,
    w: lowerFloorLength,
    d: layout.main_depth / 2 - corridorEdge,
    h: 0.18,
    y: -0.09,
    color: palette.floor,
    opacity: state.combinedLayerRendering ? 0.38 : 1,
    name: "main-floor-base-lower"
  });
  addBox(state.scene, {
    x: HUB_X,
    z: layout.corridor_width / 2 + layout.hub_length / 2,
    w: layout.hub_outer_width,
    d: layout.hub_length,
    h: 0.18,
    y: -0.09,
    color: palette.floor,
    opacity: state.combinedLayerRendering ? 0.34 : 1,
    name: "hub-floor-base"
  });
  addBox(state.scene, {
    x: mapX(layout.main_length / 2),
    z: 0,
    w: layout.main_length,
    d: layout.corridor_width,
    h: 0.12,
    y: 0.02,
    color: palette.corridor,
    name: "main-corridor"
  });
  const corridorEdgeColor = 0x607d98;
  const corridorEdgeOffset = layout.corridor_width / 2 - 0.045;
  [-corridorEdgeOffset, corridorEdgeOffset].forEach((z, index) => {
    addBox(state.scene, {
      x: mapX(layout.main_length / 2),
      z,
      w: layout.main_length,
      d: 0.075,
      h: 0.035,
      y: 0.095,
      color: corridorEdgeColor,
      name: `main-corridor-edge-${index + 1}`
    });
  });
  const connectorEdgeOffset = layout.hub_width / 2 - 0.045;
  [-connectorEdgeOffset, connectorEdgeOffset].forEach((offset, index) => {
    addBox(state.scene, {
      x: HUB_X + offset,
      z: layout.corridor_width / 2 + layout.hub_length / 2,
      w: 0.075,
      d: layout.hub_length,
      h: 0.035,
      y: 0.095,
      color: corridorEdgeColor,
      name: `hub-corridor-edge-${index + 1}`
    });
  });
  const wingFloorDepth = layout.corridor_width - 0.18;
  addBox(state.scene, {
    x: mapX(layout.left_corridor_length / 2),
    z: 0,
    w: layout.left_corridor_length,
    d: wingFloorDepth,
    h: 0.028,
    y: 0.105,
    color: palette.scanLeft,
    opacity: 0.34,
    name: "left-wing-corridor-color"
  });
  const rightWingStart = layout.left_corridor_length + layout.hub_outer_width;
  addBox(state.scene, {
    x: mapX(rightWingStart + layout.right_corridor_length / 2),
    z: 0,
    w: layout.right_corridor_length,
    d: wingFloorDepth,
    h: 0.028,
    y: 0.105,
    color: palette.scanRight,
    opacity: 0.34,
    name: "right-wing-corridor-color"
  });
  if (state.floor === 1) addFloor1Extension();
  if (state.floor === 2) addFloor2Extension();
  if (state.floor === 3) addFloor3Extension();

  const corridorHalf = layout.corridor_width / 2;
  // Room fronts define the corridor walls. Low curbs preserve the corridor edge
  // without closing room doors or the elevator/stair hub entrance.
  const corridorCenterX = mapX(layout.main_length / 2);
  const corridorLeftX = corridorCenterX - layout.main_length / 2;
  const corridorRightX = corridorCenterX + layout.main_length / 2;
  const corridorCurbOpenings = [];
  if (state.floor === 2) {
    const wing = getFloor2ExtensionLayout();
    if (wing) {
      const openingLeft = Math.min(wing.open2107.left, wing.study.left) - 0.12;
      const openingRight = Math.max(wing.open2107.right, wing.study.right) + 0.12;
      corridorCurbOpenings.push({
        center: (openingLeft + openingRight) / 2,
        width: openingRight - openingLeft
      });
    }
  }
  if (corridorCurbOpenings.length) {
    addWallXSegments(-corridorHalf, corridorLeftX, corridorRightX, corridorCurbOpenings, { height: 0.12, name: "upper-corridor-low-curb" });
    addWallXSegments(corridorHalf, corridorLeftX, corridorRightX, corridorCurbOpenings, { height: 0.12, name: "lower-corridor-low-curb" });
  } else {
    addWall(state.scene, corridorCenterX, -corridorHalf, layout.main_length, 0.12, { height: 0.12 });
    addWall(state.scene, corridorCenterX, corridorHalf, layout.main_length, 0.12, { height: 0.12 });
  }

  for (const room of state.data.rooms) addRoom(room);
  for (const facility of state.data.facilities) addFacility(facility);

  addElevatorHub();
  addMainRestroom();
  addRightEndFacilities();
  addLeftEndFacilities();
  if (state.floor === 5) addFloor5OutdoorAccess();

  if (includeHints) addScanHints(false);
  if (includeRoute) addRoute();
}

function addFloorLayer(floor, yOffset, includeRoute) {
  const savedData = state.data;
  const savedFloor = state.floor;
  const savedYOffset = state.floorYOffset;
  const savedTarget = state.targetId;
  const savedCombinedLayerRendering = state.combinedLayerRendering;
  state.floor = floor;
  state.data = state.maps[floor];
  state.floorYOffset = yOffset;
  state.combinedLayerRendering = true;
  if (!state.data.rooms.some((room) => room.id === state.targetId)) {
    state.targetId = defaultTargetForFloor(floor);
  }
  addFloorGeometry({ includeRoute, includeHints: true });
  state.data = savedData;
  state.floor = savedFloor;
  state.floorYOffset = savedYOffset;
  state.targetId = savedTarget;
  state.combinedLayerRendering = savedCombinedLayerRendering;
}

function addCombinedFloorGuide() {
  const x = HUB_X - 3.15;
  const z = DEFAULT_LAYOUT.corridor_width / 2 + EV_FRONT_Z - 0.5;
  COMBINED_FLOORS.forEach((floor, index) => {
    const y = index * COMBINED_FLOOR_GAP + 0.55;
    addBox(state.scene, {
      x,
      z,
      w: 1.15,
      d: 1.15,
      h: 0.12,
      y,
      color: 0x111827,
      name: `combined-floor-display-panel-${floor}f`
    });
    addLabel(`${floor}F`, x, z, y + 0.27, 0.45, "#f59e0b");
  });
}

function getVerticalLinkFootprint(link) {
  const layout = { ...DEFAULT_LAYOUT, ...state.maps[4]?.layout_dimensions };
  const sideBayWidth = (layout.hub_outer_width - layout.hub_width) / 2;
  if (link.id === "LEFT_END_STAIR_3F_4F") {
    const stair = state.maps[4]?.facilities.find((item) => item.id === "4F_4228_END_STAIRS");
    const width = stair?.visual_width_along_corridor || 3.1;
    const depth = stair?.visual_depth_from_corridor || 6.87;
    const sideSign = (stair?.side || "lower") === "upper" ? -1 : 1;
    const endX = mapX(layout.main_length);
    return {
      x: endX - width / 2,
      z: sideSign * layout.corridor_width / 2 + sideSign * depth / 2,
      w: width,
      d: depth,
      label: "왼쪽 계단실"
    };
  }
  if (link.id === "RIGHT_END_STAIR_3F_4F") {
    const stair = state.maps[4]?.facilities.find((item) => item.id === "4F_4204_END_STAIRS");
    const placement = getRightEndStairPlacement(layout, stair || {});
    return {
      x: placement.x,
      z: placement.z,
      w: placement.width,
      d: placement.depth,
      label: "오른쪽 계단실"
    };
  }
  if (link.id === "CENTER_STAIR_3F_4F") {
    const stair = state.maps[4]?.facilities.find((item) => item.id === "4F_CENTER_STAIRS");
    const stairX = mapX(stair?.x ?? HUB_MAP_X + 3.7);
    const coreStartZ = layout.corridor_width / 2;
    const stairStartZ = coreStartZ + (state.maps[4]?.floor_core?.stair_start_from_main_corridor || 2.44);
    const depth = coreStartZ + layout.hub_length - stairStartZ;
    return {
      x: stairX,
      z: stairStartZ + depth / 2,
      w: sideBayWidth - 0.28,
      d: depth,
      label: "중앙 계단실"
    };
  }
  if (link.id === "EV_CORE_3F_4F") {
    const elevator = state.maps[4]?.facilities.find((item) => item.id === "4F_ELEVATOR_BANK");
    return {
      x: mapX(elevator?.x ?? HUB_MAP_X - 3.7),
      z: mapZ(elevator?.y ?? -5.29),
      w: sideBayWidth - 0.3,
      d: 4.95,
      label: "엘레베이터"
    };
  }
  return {
    x: mapX(link.x),
    z: mapZ(link.y),
    w: 1.4,
    d: 1.4,
    label: link.label
  };
}

function addInterfloorStairBridge(link, footprint, floorGap, baseY = 0, levelName = "3f-4f") {
  const { x, z, w, d } = footprint;
  const sideSign = z >= 0 ? 1 : -1;
  const isRotatedRightStair = link.id === "RIGHT_END_STAIR_3F_4F";
  const isSideStair = link.id === "LEFT_END_STAIR_3F_4F" || isRotatedRightStair;
  const rotationDegrees = isRotatedRightStair ? 90 : sideSign < 0 ? 180 : 0;
  const rotationRadians = THREE.MathUtils.degToRad(rotationDegrees);
  const moduleWidth = isRotatedRightStair ? d : w;
  const moduleDepth = isRotatedRightStair ? w : d;
  const rightEndStairData = isRotatedRightStair
    ? state.maps[4]?.facilities.find((item) => item.id === "4F_4204_END_STAIRS")
    : null;
  const rightEntryLandingDepth = rightEndStairData
    ? Math.min(
        Math.max(rightEndStairData.entry_landing_width || 1.55, 0.9),
        Math.max(moduleDepth - 1.2, 0.9)
      )
    : null;
  const rightRunStartZ = isRotatedRightStair
    ? -moduleDepth / 2 + rightEntryLandingDepth
    : null;
  const root = new THREE.Group();
  root.name = `${link.id}-${levelName}-interfloor-stair-module`;
  root.position.set(x, baseY + 0.08, z);
  root.rotation.y = rotationRadians;
  state.scene.add(root);

  const addCutawayPart = (part) => {
    const partColor = new THREE.Color(part.color);
    const isAccessLanding = part.name.includes("access-landing");
    const stepNumber = Number(part.name.match(/-(\d+)$/)?.[1] || 0);
    if (part.name.includes("riser")) {
      partColor.offsetHSL(0, 0, -0.12);
    } else if (stepNumber % 2 === 0) {
      partColor.offsetHSL(0, 0, 0.055);
    }
    const mesh = new THREE.Mesh(
      new THREE.BoxGeometry(part.w, part.h, part.d),
      new THREE.MeshStandardMaterial({
        color: partColor,
        roughness: isAccessLanding ? 0.9 : 0.68,
        metalness: isAccessLanding ? 0 : 0.02,
        emissive: isAccessLanding ? 0x000000 : partColor.clone().multiplyScalar(0.08),
        transparent: false,
        depthTest: true,
        depthWrite: true,
        side: THREE.DoubleSide
      })
    );
    mesh.position.set(part.x, part.y ?? part.h / 2, part.z);
    mesh.name = part.name;
    mesh.frustumCulled = false;
    mesh.renderOrder = 40;
    if (part.name.includes("step") || part.name.includes("half-landing")) {
      const edgeColor = part.name.includes("half-landing") ? 0x312e81 : 0x1e293b;
      const edges = new THREE.LineSegments(
        new THREE.EdgesGeometry(mesh.geometry, 20),
        new THREE.LineBasicMaterial({
          color: edgeColor,
          transparent: true,
          opacity: 0.9,
          depthTest: false,
          depthWrite: false
        })
      );
      edges.name = `${part.name}-edge`;
      edges.frustumCulled = false;
      edges.renderOrder = 110;
      mesh.add(edges);
    }
    root.add(mesh);
    return mesh;
  };

  const anchors = buildInterfloorStairModule({
    group: root,
    addPart: addCutawayPart,
    name: link.id,
    width: moduleWidth,
    depth: moduleDepth,
    floorGap,
    upperColor: 0x2563eb,
    lowerColor: 0x16a34a,
    landingColor: 0x7c3aed,
    padColor: palette.roomFloor,
    swapFlights: isSideStair,
    accessLandingDepth: isRotatedRightStair ? rightEntryLandingDepth : isSideStair ? 1.15 : null,
    addAccessLandings: !isRotatedRightStair,
    runStartZ: rightRunStartZ
  });

  if (isRotatedRightStair && rightEntryLandingDepth) {
    const entryFloorDepth = Math.max(rightEntryLandingDepth - 0.06, 0.5);
    const entryFloorZ = -moduleDepth / 2 + entryFloorDepth / 2;
    const entryFloorWidth = Math.max(moduleWidth - 0.24, 1.4);
    const restroomSideDepth = Math.max(moduleDepth - rightEntryLandingDepth - 0.08, 0.5);
    const restroomSideZ = rightRunStartZ + restroomSideDepth / 2;
    [
      { floor: "3f", y: 0.055 },
      { floor: "4f", y: floorGap + 0.055 }
    ].forEach(({ floor, y }) => {
      const floorMesh = addBox(root, {
        x: 0,
        z: entryFloorZ,
        w: entryFloorWidth,
        d: entryFloorDepth,
        h: 0.11,
        y,
        color: palette.roomFloor,
        opacity: 1,
        name: `${link.id}-${floor}-solid-entry-floor`
      });
      floorMesh.frustumCulled = false;
      floorMesh.renderOrder = 38;

      const restroomSideFloorMesh = addBox(root, {
        x: 0,
        z: restroomSideZ,
        w: entryFloorWidth,
        d: restroomSideDepth,
        h: 0.1,
        y,
        color: palette.roomFloor,
        opacity: 1,
        name: `${link.id}-${floor}-restroom-side-solid-floor`
      });
      restroomSideFloorMesh.frustumCulled = false;
      restroomSideFloorMesh.renderOrder = 36;
    });
  }

  // Keep stair outlines readable through both translucent floor slabs.
  root.traverse((object) => {
    object.frustumCulled = false;
    if (object.isLine || object.isLineSegments) {
      const materials = Array.isArray(object.material) ? object.material : [object.material];
      materials.filter(Boolean).forEach((material) => {
        material.depthTest = false;
        material.depthWrite = false;
        material.needsUpdate = true;
      });
      object.renderOrder = 110;
    }
  });

  const labelPosition = anchors.landing.clone().applyAxisAngle(
    new THREE.Vector3(0, 1, 0),
    rotationRadians
  );
  labelPosition.x += x;
  labelPosition.z += z;
  addLabel("중간참 · 12+12계단", labelPosition.x, labelPosition.z, baseY + labelPosition.y + 0.42, 0.32, "#312e81");
}

function addVerticalTransitionGuides(baseY = 0, lowerFloor = 3, upperFloor = 4) {
  const links = state.maps[4]?.routing?.vertical_links || [];
  const floorGap = COMBINED_FLOOR_GAP;
  const levelName = `${lowerFloor}f-${upperFloor}f`;
  links.forEach((link) => {
    const footprint = getVerticalLinkFootprint(link);
    const { x, z } = footprint;
    const isElevator = link.type === "elevator";
    const radius = isElevator ? 0.62 : 0.48;
    const color = isElevator ? palette.verticalLinkElevator : palette.verticalLink;
    if (isElevator) {
      addBox(state.scene, {
        x,
        z,
        w: Math.max(footprint.w, radius * 2.8),
        d: Math.max(footprint.d, radius * 2.8),
        h: floorGap - 0.08,
        y: baseY + floorGap / 2,
        color,
        opacity: 0.12,
        name: `${link.id}-floor-to-floor-shaft`
      });
      const railInsetX = Math.max(footprint.w / 2 - 0.16, 0.2);
      const railInsetZ = Math.max(footprint.d / 2 - 0.16, 0.2);
      [
        [-railInsetX, -railInsetZ],
        [railInsetX, -railInsetZ],
        [-railInsetX, railInsetZ],
        [railInsetX, railInsetZ]
      ].forEach(([offsetX, offsetZ], index) => {
        addBox(state.scene, {
          x: x + offsetX,
          z: z + offsetZ,
          w: 0.08,
          d: 0.08,
          h: floorGap + 0.24,
          y: baseY + floorGap / 2,
          color,
          opacity: 0.74,
          name: `${link.id}-vertical-rail-${index + 1}`
        });
      });
    }
    if (isElevator) {
      const column = new THREE.Mesh(
        new THREE.CylinderGeometry(radius, radius, floorGap - 0.35, 24),
        makeMat(color, 0.7, 0.68)
      );
      column.position.set(x, baseY + floorGap / 2, z);
      column.name = `${link.id}-${levelName}-vertical-link`;
      column.castShadow = false;
      column.receiveShadow = false;
      state.scene.add(column);
    } else {
      addInterfloorStairBridge(link, footprint, floorGap, baseY, levelName);
    }

    if (isElevator) {
      addBox(state.scene, {
        x,
        z,
        w: Math.max(footprint.w * 0.72, radius * 3.2),
        d: Math.max(footprint.d * 0.72, radius * 3.2),
        h: 0.08,
        y: baseY + 0.22,
        color,
        opacity: 0.86,
        name: `${link.id}-${lowerFloor}f-link-pad`
      });
      addBox(state.scene, {
        x,
        z,
        w: Math.max(footprint.w * 0.72, radius * 3.2),
        d: Math.max(footprint.d * 0.72, radius * 3.2),
        h: 0.08,
        y: baseY + floorGap + 0.22,
        color,
        opacity: 0.86,
        name: `${link.id}-${upperFloor}f-link-pad`
      });
    }
    addLabel(
      isElevator ? `${lowerFloor}F↔${upperFloor}F EV` : `${lowerFloor}F↔${upperFloor}F ${footprint.label}`,
      x,
      z + footprint.d / 2 + 0.72,
      baseY + floorGap + 0.72,
      0.42,
      isElevator ? "#0369a1" : "#6d28d9"
    );
  });
}

function getTargetFloor(targetId = state.targetId) {
  return FLOORS.find((floor) => state.maps[floor]?.rooms.some((room) => room.id === targetId)) || 3;
}

function buildScene() {
  resetScene();

  if (state.floor === "both") {
    const savedData = state.data;
    const savedYOffset = state.floorYOffset;
    const targetFloor = getTargetFloor();
    COMBINED_FLOORS.forEach((floor, index) => {
      addFloorLayer(floor, index * COMBINED_FLOOR_GAP, targetFloor === floor);
    });
    state.data = savedData;
    state.floorYOffset = savedYOffset;
    addCombinedFloorGuide();
    COMBINED_FLOORS.slice(0, -1).forEach((lowerFloor, index) => {
      addVerticalTransitionGuides(index * COMBINED_FLOOR_GAP, lowerFloor, lowerFloor + 1);
    });
  } else {
    state.floorYOffset = 0;
    addFloorGeometry({ includeRoute: true, includeHints: true });
  }

  state.hintGroup.visible = $("scanHintToggle").checked;
  state.labelGroup.visible = $("labelToggle").checked;
}

function resizeRenderer() {
  const canvas = $("clayCanvas");
  const rect = canvas.getBoundingClientRect();
  state.camera.aspect = rect.width / rect.height;
  state.camera.updateProjectionMatrix();
  state.renderer.setSize(rect.width, rect.height, false);
  resizeStairPreview();
}

function setIsoView() {
  state.viewMode = "iso";
  state.labelGroup.visible = $("labelToggle").checked;
  state.camera.up.set(0, 1, 0);
  if (state.floor === "both") {
    state.camera.position.set(30, 182, 122);
    state.controls.target.set(9, combinedCenterY(), -2);
    state.controls.update();
    return;
  }
  const isExtensionFloor = state.floor === 1 || state.floor === 2 || state.floor === 3;
  state.camera.position.set(
    isExtensionFloor ? 16 : 4,
    state.floor === 1 ? 126 : state.floor === 2 ? 112 : state.floor === 3 ? 88 : 72,
    state.floor === 1 ? 88 : state.floor === 2 ? 76 : state.floor === 3 ? 68 : 52
  );
  state.controls.target.set(isExtensionFloor ? 8 : 0, 0, state.floor === 1 ? -15 : state.floor === 2 ? -8 : state.floor === 3 ? 9 : 2.5);
  state.controls.update();
}

function setTopView() {
  state.viewMode = "top";
  state.labelGroup.visible = $("labelToggle").checked;
  // Keep the same left/right orientation as the navigation coordinate frame.
  state.camera.up.set(0, 0, -1);
  if (state.floor === "both") {
    state.camera.position.set(8, 194, 7.01);
    state.controls.target.set(8, combinedCenterY(), -2);
    state.controls.update();
    return;
  }
  const isExtensionFloor = state.floor === 1 || state.floor === 2 || state.floor === 3;
  state.camera.position.set(isExtensionFloor ? 8 : 0, state.floor === 1 ? 132 : isExtensionFloor ? 110 : 88, state.floor === 1 ? -14.99 : state.floor === 2 ? -7.99 : state.floor === 3 ? 9.01 : 0.01);
  state.controls.target.set(isExtensionFloor ? 8 : 0, 0, state.floor === 1 ? -15 : state.floor === 2 ? -8 : state.floor === 3 ? 9 : 2.5);
  state.controls.update();
}

function setHubView() {
  state.viewMode = "hub";
  state.labelGroup.visible = $("labelToggle").checked;
  state.camera.up.set(0, 1, 0);
  state.camera.position.set(HUB_X + 12.5, state.floor === "both" ? 22.5 : 10.5, 15.5);
  state.controls.target.set(HUB_X, state.floor === "both" ? combinedCenterY() : 1.0, 2.8);
  state.controls.update();
}

function setEndStairView() {
  state.viewMode = "end-stair";
  state.labelGroup.visible = $("labelToggle").checked;
  if (state.floor === 3 && state.maps[3]?.floor3_extension) {
    const savedData = state.data;
    state.data = state.maps[3];
    const wing = getFloor3ExtensionLayout();
    state.data = savedData;
    state.camera.up.set(0, 1, 0);
    const focusZ = (wing.freeCenterZ + wing.deepCenterZ) / 2;
    state.camera.position.set(wing.branchWorldX - 8, state.floor === "both" ? 17.5 : 13.5, focusZ - wing.sideSign * 9);
    state.controls.target.set(wing.branchWorldX, state.floor === "both" ? 2.1 : 0.45, focusZ);
    state.controls.update();
    return;
  }
  if (state.floor === 2 && state.maps[2]?.floor2_extension) {
    const savedData = state.data;
    state.data = state.maps[2];
    const wing = getFloor2ExtensionLayout();
    state.data = savedData;
    const focusX = (wing.open2107.left + wing.study.right) / 2;
    const focusZ = (wing.study.centerZ + wing.extensionCorridor.centerZ) / 2;
    state.camera.up.set(0, 1, 0);
    state.camera.position.set(focusX - 24, 32, focusZ + 28);
    state.controls.target.set(focusX, 0.7, focusZ);
    state.controls.update();
    return;
  }
  const layout = { ...DEFAULT_LAYOUT, ...state.data.layout_dimensions };
  const endStairs = state.data.facilities.find((item) => item.id === "4F_4204_END_STAIRS");
  const placement = getRightEndStairPlacement(layout, endStairs || {});
  const stairX = placement.x;
  const endDirection = 1;
  const sideSign = placement.sideSign;
  const stairZ = placement.z;
  state.camera.up.set(0, 1, 0);
  if (state.floor === "both") {
    state.camera.position.set(stairX + 5.8, 19.5, stairZ + sideSign * 7.2);
    state.controls.target.set(stairX, combinedCenterY(), stairZ);
    state.controls.update();
    return;
  }
  state.camera.position.set(stairX - endDirection * 5.8, 10.8, stairZ + sideSign * 7.2);
  state.controls.target.set(stairX, 0.25, stairZ);
  state.controls.update();
}

function setWalkView() {
  state.viewMode = "walk";
  state.labelGroup.visible = false;
  state.camera.up.set(0, 1, 0);
  const layout = { ...DEFAULT_LAYOUT, ...state.data.layout_dimensions };
  state.camera.position.set(HUB_X, state.floor === "both" ? 12.2 : 1.65, layout.corridor_width / 2 + layout.hub_length + 1.4);
  state.controls.target.set(HUB_X, state.floor === "both" ? 11.85 : 1.35, -1.2);
  state.controls.update();
}

function populateTargets() {
  const select = $("targetSelect");
  if (state.floor === "both") {
    select.innerHTML = COMBINED_FLOORS.map((floor) => `
      <optgroup label="${floor}F">
        ${state.maps[floor].rooms.map((room) => `<option value="${room.id}">${floor}F · ${room.label || room.id}</option>`).join("")}
      </optgroup>
    `).join("");
  } else {
    select.innerHTML = state.data.rooms.map((room) => `<option value="${room.id}">${room.label || room.id}</option>`).join("");
  }
  select.value = state.targetId;
}

function updateDetail() {
  if (state.floor === "both") {
    const targetFloor = getTargetFloor();
    $("detail").innerHTML = `
      <strong>${COMBINED_LONG_LABEL} 통합 보기</strong>
      1층부터 10층까지 동일한 코어와 계단 좌표에 적층해 전체 건물 관계를 확인한다.<br>
      계단과 엘리베이터는 각 층 사이를 연결하며, 층마다 12+12계단 구조를 사용한다.<br>
      현재 선택한 목적지는 ${targetFloor}층에 있으며 경로도 해당 층에만 표시된다.
    `;
    return;
  }
  const room = state.data.rooms.find((item) => item.id === state.targetId);
  if (!room) return;
  if (state.floor === 1) {
    const isOutdoor = room.extension_zone === "admin" || room.extension_zone === "outdoor-corridor";
    $("detail").innerHTML = `
      <strong>${room.label || room.id} 안내 기준</strong>
      ${isOutdoor ? "1119 오른쪽 정문으로 나간 뒤 야외 복도를 통해 행정실 방향으로 이동한다." : "코어와 양쪽 계단은 위층과 같은 고정 위치를 사용한다."}<br>
      휴식공간은 정문 오른쪽부터 명칭 미확정 통합공간 시작선 전까지만 차지하며 정문 영역을 침범하지 않는다.<br>
      1122는 iSPACE, 1221은 S-SPACE이며 기존 1107~1103 구간은 하나의 통합공간으로 표시한다.<br>
      행정실은 본동과 분리된 하나의 건물로 표시하고, 사이 공간은 야외 복도로 연결한다.<br>
      1213과 1210 사이에는 별도 강의실이 아닌 출입문이 있는 빈 통로가 있다.
    `;
    return;
  }
  if (state.floor === 2) {
    const isExtension = room.placement === "extension-marker";
    $("detail").innerHTML = `
      <strong>${room.label || room.id} 안내 기준</strong>
      ${isExtension ? "메인복도에서 2107 개방공간으로 진입한 뒤 목적 구역으로 이동한다." : "코어와 양쪽 계단은 3·4층과 같은 고정 위치를 사용한다."}<br>
      2107은 2210 오른쪽 선에서 끝나며, 그 옆 같은 건물 틀 안에 ㄷ자 학습공간과 TDM이 이어진다.<br>
      M-space는 별도 외벽 증축이 아니라 2105-1·2 왼쪽에 남는 세로 공간이며 2107에서 진입한다.<br>
      정사각형 기둥과 TDM 사이의 넓은 입구를 지나 증축부 복도와 2104·2105 구역으로 이동한다.
    `;
    return;
  }
  if (state.floor === 3) {
    const isExtension = room.placement === "free" || room.placement === "extension-marker";
    $("detail").innerHTML = `
      <strong>${room.label || room.id} 안내 기준</strong>
      ${isExtension ? "엘리베이터 코어에서 오른쪽 복도 3203 라인까지 이동한 뒤, 첫 입구로 자유공간에 진입한다." : "코어 복도와 공통 좌우 복도는 4층 실측 구조를 재사용한다."}<br>
      3층 증축부는 자유공간 뒤로 증축부 복도가 이어지고, 복도 좌측은 IT홀, 우측은 3104-1·3104-2로 나뉜다.<br>
      3203 라인에서는 첫 입구만 열고 나머지 경계는 벽으로 막아 피난안내도 기준의 진입 방향을 유지한다.<br>
      실제 이동 위치는 복도 그래프에 제한된 PDR과 자기장 기준점으로 보정한다.
    `;
    return;
  }
  if (state.floor === 5) {
    $("detail").innerHTML = `
      <strong>${room.label || room.id} 안내 기준</strong>
      5층은 빨간박스 공통 본동 틀과 야외공간을 함께 표시합니다.<br>
      코어, 화장실, 엘레베이터, 메인계단, 좌우 사이드계단은 4층과 같은 위치로 고정합니다.<br>
      5123 왼쪽 구간은 하나의 5126 심리상담센터로 통합합니다.<br>
      기존 노란 증축 외형과 복도 위 빈 공간은 하나의 야외공간으로 통합합니다.<br>
      야외 출입문은 5111 오른쪽 복도 위 경계와 오른쪽 복도 끝에 표시합니다.<br>
      5205와 5205-1은 편의점으로 통합 표기했습니다.<br>
      사진 판독이 흐린 5227 계열 등은 추후 현장 확인 후 보정합니다.
    `;
    return;
  }
  if (state.floor === 6) {
    $("detail").innerHTML = `
      <strong>${room.label || room.id} 안내 기준</strong>
      6층은 4층과 같은 중앙 코어와 오른쪽 계단 위치를 사용합니다.<br>
      강의실 행은 6층 2D 도면의 상대 폭을 유지하면서 코어 경계에 빈틈이나 겹침 없이 맞춥니다.<br>
      오른쪽 끝은 6203·통로·6202와 고정 오른쪽 계단의 연결 관계를 사용합니다.
    `;
    return;
  }
  if (Number(state.floor) >= 7) {
    const floorPrefix = String(state.floor);
    $("detail").innerHTML = `
      <strong>${room.label || room.id} 안내 기준</strong>
      ${state.floor}층은 6층에서 확정한 중앙 코어와 좌우 계단 위치를 그대로 사용합니다.<br>
      강의실 행은 ${state.floor}층 피난안내도의 방 순서와 상대 폭을 적용하고 코어 경계에 빈틈이나 겹침 없이 연결합니다.<br>
      오른쪽 끝은 ${floorPrefix}206에서 통로를 지나 ${floorPrefix}202로 진입하며, ${floorPrefix}103·${floorPrefix}206 끝선과 고정 오른쪽 계단 입구를 맞춥니다.
    `;
    return;
  }
  const hubX = state.data.routing.hub_junction.x;
  const dir = room.x < hubX ? "엘레베이터에서 내려 왼쪽, 4218 방향" : "엘레베이터에서 내려 오른쪽, 4213/4210 방향";
  $("detail").innerHTML = `
    <strong>${state.targetId} 안내 기준</strong>
    ${dir}<br>
    출발점은 첫 번째 엘레베이터 앞이고, 폭 2.34m인 메인 복도 가장자리부터 약 9.20m 깊이의 코어 복도를 따라 나온다.<br>
    계단은 메인 복도에서 2.44m 뒤부터 시작하고, 첫 엘레베이터 문은 3.59m 뒤에 있다.<br>
    첫 엘레베이터 뒤 2.27m 벽을 지나 약 6.96m 지점에서 두 번째 엘레베이터가 시작된다.<br>
    GLB 축척: 왼쪽 64.44m + 시설 포함 코어 12.73m + 오른쪽 58.24m = 전체 135.41m.
  `;
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

function updateFloorTiles() {
  document.querySelectorAll("[data-floor-jump]").forEach((button) => {
    button.classList.toggle("active", button.dataset.floorJump === String(state.floor));
  });
  const currentDisplay = $("currentFloorDisplay");
  const viewerDisplay = $("viewerFloorDisplay");
  if (currentDisplay) currentDisplay.textContent = state.floor === "both" ? COMBINED_LONG_LABEL : `${state.floor}F`;
  if (viewerDisplay) viewerDisplay.textContent = state.floor === "both" ? COMBINED_LABEL : `${state.floor}F`;
  document.querySelectorAll("[data-floor-step]").forEach((button) => {
    const step = button.dataset.floorStep;
    button.disabled =
      state.floor === "both" ||
      (state.floor === Math.max(...FLOORS) && step === "up") ||
      (state.floor === 1 && step === "down");
  });
  updateStairPreview();
}

function updateStairPreview() {
  const stateLabel = $("stairPreviewState");
  const stateText = $("stairPreviewText");
  const upperTag = $("stairUpperFloorTag");
  const lowerTag = $("stairLowerFloorTag");
  const preview = state.stairPreview;
  if (!stateLabel) return;

  const numericFloor = Number(state.floor);
  if (upperTag) upperTag.textContent = state.floor === "both" ? "10F" : `${Math.min(numericFloor + 1, Math.max(...FLOORS))}F`;
  if (lowerTag) lowerTag.textContent = state.floor === "both" ? "1F" : `${Math.max(numericFloor - 1, 1)}F`;

  if (state.floor === "both") {
    stateLabel.textContent = "1F↔2F↔3F↔4F↔5F↔6F↔7F↔8F↔9F↔10F 이동중";
    if (stateText) stateText.textContent = "층마다 12계단을 지나 중간참에서 반대로 돌아 다시 12계단을 이동하며, 같은 구조가 아홉 개 층간 구간에 이어집니다.";
    if (preview?.marker && preview.anchors) {
      preview.marker.position.copy(preview.anchors.landing);
      preview.marker.position.y += 0.2;
    }
    return;
  }

  stateLabel.textContent = state.floor >= 6 ? `${state.floor}F 계단 입구` : state.floor === 5 ? "5F 계단 입구" : state.floor === 4 ? "4F 계단 구간" : state.floor === 3 ? "3F 계단 구간" : state.floor === 2 ? "2F 계단 구간" : "1F 계단 출구";
  if (stateText) {
    stateText.textContent = state.floor >= 6
      ? `${state.floor}층 계단 입구에서 12계단 내려가 중간참을 돌고, 다시 12계단 내려가면 ${state.floor - 1}층입니다.`
      : state.floor === 5
      ? "5층 계단 입구에서 12계단 내려가 중간참을 돌고, 다시 12계단 내려가면 4층입니다."
      : state.floor === 4
        ? "4층에서 같은 12+12계단 구조를 통해 3층 또는 5층으로 이동합니다."
      : state.floor === 3
        ? "3층에서 같은 12+12계단 구조를 통해 2층 또는 4층으로 이동합니다."
        : state.floor === 2
          ? "2층에서 같은 12+12계단 구조를 통해 1층 또는 3층으로 이동합니다."
          : "1층 계단 출구에서 12계단 올라가 중간참을 돌고, 다시 12계단 올라가면 2층입니다.";
  }
  if (preview?.marker && preview.anchors) {
    preview.marker.position.copy(state.floor >= 4 ? preview.anchors.upperEntry : preview.anchors.lowerExit);
    preview.marker.position.y += 0.18;
  }
}

function parseFloorValue(value) {
  return value === "both" ? "both" : Number(value);
}

function applyFloor(floor, preferredTargetId = null) {
  state.floor = floor;
  state.data = floor === "both" ? state.maps[3] : state.maps[floor];
  const rooms = floor === "both" ? COMBINED_FLOORS.flatMap((floorNumber) => state.maps[floorNumber].rooms) : state.data.rooms;
  const defaultTargetId = floor === "both" ? defaultTargetForFloor(3) : defaultTargetForFloor(floor);
  state.targetId = rooms.some((room) => room.id === preferredTargetId) ? preferredTargetId : defaultTargetId;
  $("floorSelect").value = String(floor);
  $("pageTitle").textContent = floor === "both" ? `IT융합대학 ${COMBINED_LONG_LABEL} 통합 클레이 지도` : `IT융합대학 ${floor}층 클레이 지도`;
  $("pageSubtitle").textContent = floor === "both"
    ? "1층부터 10층까지 함께 띄워 코어와 계단의 층 이동 관계를 확인하는 모델"
    : floor === 1
      ? "공통 코어 기준틀에 정문, 휴식공간, 야외복도와 행정실을 결합한 1층 모델"
      : floor === 2
      ? "공통 코어 기준틀에 M-space, 학습공간, TDM과 2층 증축부를 결합한 모델"
      : floor === 3
      ? "4층 기준틀과 실제 3층 GLB 신규 공간을 결합한 3층 초안"
    : floor >= 7
      ? `6층에서 확정한 고정 코어·계단 틀에 ${floor}층 2D 강의실 행과 ${floor}202 연결 통로를 반영한 모델`
    : floor === 6
      ? "4층 공통 코어와 고정 계단을 유지하고, 6층 2D 기준 강의실 행과 6202 끝구역을 반영한 모델"
    : floor === 5
      ? "공통 본동 기준틀에 5층 오른쪽 라인, 편의점, 야외공간을 배치한 모델"
      : "GLB 복도와 12.73m 중앙 코어를 결합한 4층 안내 모델";
  $("scanSourceLink").hidden = floor !== 3 && floor !== "both";
  $("clayCanvas").setAttribute("aria-label", floor === "both" ? "IT융합대학 1층부터 10층 통합 클레이형 3D 지도" : `IT융합대학 ${floor}층 클레이형 3D 지도`);
  updateFloorTiles();
  populateTargets();
  buildScene();
  updateDetail();
  setIsoView();
}

async function init() {
  const cacheVersion = Date.now();
  const [baseResponse, floor3Response, floor2Response, floor1Response, floor5Response, floor6Response, floor7Response, floor8Response, floor9Response, floor10Response] = await Promise.all([
    fetch(`./data/maps/floor-04.json?v=${cacheVersion}`),
    fetch(`./data/maps/floor-03.json?v=${cacheVersion}`),
    fetch(`./data/maps/floor-02.json?v=${cacheVersion}`),
    fetch(`./data/maps/floor-01.json?v=${cacheVersion}`),
    fetch(`./data/maps/floor-05.json?v=${cacheVersion}`),
    fetch(`./data/maps/floor-06.json?v=${cacheVersion}`),
    fetch(`./data/maps/floor-07.json?v=${cacheVersion}`),
    fetch(`./data/maps/floor-08.json?v=${cacheVersion}`),
    fetch(`./data/maps/floor-09.json?v=${cacheVersion}`),
    fetch(`./data/maps/floor-10.json?v=${cacheVersion}`)
  ]);
  const base = await baseResponse.json();
  const floor3Override = await floor3Response.json();
  const floor2Override = await floor2Response.json();
  const floor1Override = await floor1Response.json();
  const floor5Override = await floor5Response.json();
  const floor6Override = await floor6Response.json();
  const floor7Override = await floor7Response.json();
  const floor8Override = await floor8Response.json();
  const floor9Override = await floor9Response.json();
  const floor10Override = await floor10Response.json();
  state.maps[4] = base;
  state.maps[3] = composeFloor3(base, floor3Override);
  state.maps[2] = composeFloor3(base, floor2Override);
  state.maps[1] = composeFloor3(base, floor1Override);
  state.maps[5] = composeFloor3(base, floor5Override);
  state.maps[6] = composeFloor3(base, floor6Override);
  state.maps[7] = composeFloor3(base, floor7Override);
  state.maps[8] = composeFloor3(base, floor8Override);
  state.maps[9] = composeFloor3(base, floor9Override);
  state.maps[10] = composeFloor3(base, floor10Override);
  state.data = state.maps[3];

  state.scene = new THREE.Scene();
  state.camera = new THREE.PerspectiveCamera(48, 1, 0.1, 500);
  state.renderer = new THREE.WebGLRenderer({ canvas: $("clayCanvas"), antialias: true });
  state.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  state.renderer.shadowMap.enabled = true;
  state.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  state.renderer.outputColorSpace = THREE.SRGBColorSpace;
  state.renderer.toneMapping = THREE.ACESFilmicToneMapping;
  state.renderer.toneMappingExposure = 0.94;

  state.controls = new OrbitControls(state.camera, state.renderer.domElement);
  state.controls.enableDamping = true;
  state.controls.minDistance = 2.2;
  state.controls.maxDistance = 160;
  state.controls.maxPolarAngle = Math.PI / 2.05;

  resizeRenderer();
  initStairPreview();
  const requestedFloor = pageParams.get("floor");
  const requestedFloorNumber = Number(requestedFloor);
  const initialFloor = requestedFloor === "both"
    ? "both"
    : FLOORS.includes(requestedFloorNumber)
      ? requestedFloorNumber
      : "both";
  applyFloor(initialFloor, pageParams.get("target"));

  $("targetSelect").addEventListener("change", (event) => {
    state.targetId = event.target.value;
    buildScene();
    updateDetail();
  });

  $("floorSelect").addEventListener("change", (event) => {
    applyFloor(parseFloorValue(event.target.value));
  });

  document.querySelectorAll("[data-floor-jump]").forEach((button) => {
    button.addEventListener("click", () => {
      applyFloor(parseFloorValue(button.dataset.floorJump));
    });
  });

  document.querySelectorAll("[data-floor-step]").forEach((button) => {
    button.addEventListener("click", () => {
      if (state.floor === "both") return;
      const floor = button.dataset.floorStep === "up"
        ? Math.min(Number(state.floor) + 1, Math.max(...FLOORS))
        : Math.max(Number(state.floor) - 1, 1);
      applyFloor(floor);
    });
  });

  $("labelToggle").addEventListener("change", (event) => {
    state.labelGroup.visible = state.viewMode !== "walk" && event.target.checked;
  });

  $("scanHintToggle").addEventListener("change", (event) => {
    state.hintGroup.visible = event.target.checked;
  });

  $("viewIso").addEventListener("click", setIsoView);
  $("viewTop").addEventListener("click", setTopView);
  $("viewHub").addEventListener("click", setHubView);
  $("viewEndStair").addEventListener("click", setEndStairView);
  $("viewWalk").addEventListener("click", setWalkView);
  window.addEventListener("resize", resizeRenderer);

  function animate() {
    requestAnimationFrame(animate);
    state.controls.update();
    state.renderer.render(state.scene, state.camera);
    renderStairPreview();
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
