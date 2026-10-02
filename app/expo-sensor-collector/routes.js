const floor01 = require("../../indoor/web/data/maps/floor-01.json");
const floor02 = require("../../indoor/web/data/maps/floor-02.json");
const floor03 = require("../../indoor/web/data/maps/floor-03.json");
const floor04 = require("../../indoor/web/data/maps/floor-04.json");
const floor05 = require("../../indoor/web/data/maps/floor-05.json");
const floor06 = require("../../indoor/web/data/maps/floor-06.json");
const floor07 = require("../../indoor/web/data/maps/floor-07.json");
const floor08 = require("../../indoor/web/data/maps/floor-08.json");
const floor09 = require("../../indoor/web/data/maps/floor-09.json");
const floor10 = require("../../indoor/web/data/maps/floor-10.json");

const FLOOR_MAPS = [floor01, floor02, floor03, floor04, floor05, floor06, floor07, floor08, floor09, floor10];
const CORE_CENTER_X = floor04.layout_dimensions.left_corridor_length + floor04.layout_dimensions.hub_outer_width / 2;

function pointLocation(point) {
  const unchangedSuffixes = ["입구", "중앙", "중앙선", "끝", "공간", "교차점", "아래", "회전점", "출입문", "진입점"];
  return unchangedSuffixes.some((suffix) => point.endsWith(suffix)) ? point : `${point} 앞`;
}

function preferredRoomRow(rooms) {
  const upper = rooms.filter((room) => room.side === "upper");
  return upper.length ? upper : rooms.filter((room) => room.side === "lower");
}

function preferredRightRoomRow(floor, rooms) {
  const preferredSide = [2, 3, 4, 5].includes(floor) ? "lower" : "upper";
  const preferred = rooms.filter((room) => room.side === preferredSide);
  return preferred.length ? preferred : preferredRoomRow(rooms);
}

function basicRoute(floor, sideId, stairs, rooms) {
  const passage=sideId==='RIGHT' ? ([2,3,4].includes(floor)?'오른쪽 끝 화장실 통로 앞':floor>=6?'오른쪽 끝방 연결 통로 앞':null) : null;
  const destination=stairs;
  const isFloorTwoRightMain = floor === 2 && sideId === "RIGHT";
  const remainingFloorTwoRooms = rooms
    .filter((room) => !["2211", "2210", "2210-1"].includes(room.id))
    .map((room) => pointLocation(room.id));
  // 현장 확인 순서: 2107의 메인복도 쪽 진입 가능점과 끝점은 2210의 두 문 사이에 있다.
  const laps = isFloorTwoRightMain
    ? [
        "2211 문 1",
        "2211 문 2",
        "2210 문 1",
        "2107 진입 가능점",
        "2210 문 2 · 2107 끝점",
        "2210-1 앞",
        ...remainingFloorTwoRooms,
        ...(passage ? [passage] : []),
        stairs
      ]
    : [...rooms.map((room) => pointLocation(room.id)), ...(passage?[passage]:[]), stairs];
  return {
    id: `${floor}F_CORE_TO_${sideId}_STAIRS`,
    title: `${floor}층 코어 출구 → ${stairs}`,
    floor: String(floor),
    start: isFloorTwoRightMain ? "코어·오른쪽 메인복도 교차점" : "코어복도 출구 중앙점",
    destination,
    routeRevision: isFloorTwoRightMain ? 'floor2-main-right-door-order-20260915' : 'corridor-roundtrip-20260914',
    laps
  };
}

function specialRoute(id, title, floor, start, destination, laps) {
  return { id, title, floor: String(floor), start, destination, laps };
}

function specialRoutes(floor) {
  if (floor === 1) {
    return [
      specialRoute(
        "1F_OUTDOOR_ADMIN_CORRIDOR",
        "1층 본동·행정실 사이 야외복도",
        1,
        "정문 출입문 앞",
        "야외복도 끝",
        ["본동·행정실 사이 야외복도 입구", "행정실 문", "야외복도 중앙", "야외복도 끝"]
      ),
      {
        ...specialRoute("1F_TO_4F_ELEVATOR", "1층 → 4층 엘리베이터 층 추적", 1, "1층 엘리베이터 내부 정지", "4층 엘리베이터 도착", ["4층 도착"]),
        mode: "floor_tracking",
        startFloor: 1,
        destinationFloor: 4
      },
      {
        ...specialRoute("1F_TO_4F_STAIRS", "1층 → 4층 계단 층 추적", 1, "1층 계단 입구 정지", "4층 계단 도착", ["4층 도착"]),
        mode: "floor_tracking",
        startFloor: 1,
        destinationFloor: 4
      }
    ];
  }
  if (floor === 2) {
    return [
      specialRoute(
        "2F_STUDY_V3",
        "2층 메인복도 → 기둥·TDM 사이 → 책상공간",
        2,
        "책상공간 하단 진입구 정면 · 메인복도 중앙선",
        "책상공간 내부 · ㄴ자 책상 열린 쪽 통로 중앙",
        [
          "책상공간 진입 전 · 책상공간 하단 진입구 정면 · 메인복도 중앙선",
          "기둥·TDM 사이 · 메인복도와 증축복도 중심축 교차점",
          "책상공간 내부 · ㄴ자 책상 열린 쪽 통로 중앙"
        ]
      ),
      specialRoute(
        "2F_EXTENSION_V3",
        "2층 기둥·TDM 사이 → 증축복도",
        2,
        "기둥·TDM 사이 · 메인복도와 증축복도 중심축 교차점",
        "증축복도 계단 진입 전 · 복도 중앙선",
        [
          "기둥·TDM 사이 · 메인복도와 증축복도 중심축 교차점",
          "TDM 옆 · TDM 외벽 가로폭 중앙 정면 · 증축복도 중앙선",
          "2105-1·2104-1 사이 · 증축복도 중앙선",
          "2105-2·2104-2 사이 · 증축복도 중앙선",
          "증축복도 계단 진입 전 · 복도 중앙선"
        ]
      )
    ];
  }
  if (floor === 3) {
    return [
      specialRoute("3F_EXTENSION", "3층 증축부 라인 별도 측정", 3, "메인복도·증축부 교차점", "3104-1", ["증축부 입구", "자유공간", "3104-2 앞", "3104-1 앞"]),
      specialRoute("3F_IT_HALL", "3층 IT홀 계단 별도 측정", 3, "자유공간 IT홀 계단 아래", "IT홀 입구", ["IT홀 계단 아래", "IT홀 계단 위 회전점", "IT홀 입구"])
    ];
  }
  if (floor === 5) {
    return [specialRoute("5F_OUTDOOR", "5층 야외공간 별도 측정", 5, "오른쪽 복도 야외문", "야외공간 끝", ["야외공간 입구", "야외공간 중앙", "야외공간 끝"])];
  }
  return [];
}

function floorRoutes(map) {
  const floor = Number(map.floor);
  const rooms = (map.rooms || [])
    .filter((room) => Number.isFinite(room.x) && !room.provisional)
    .map((room) => ({ id: room.id, x: room.x, side: room.side || "lower" }));
  const rightRooms = rooms.filter((room) => room.x < CORE_CENTER_X);
  const leftRooms = rooms.filter((room) => room.x > CORE_CENTER_X);

  if (floor === 1) {
    const entranceLeft = rightRooms.filter((room) => room.side === "lower").sort((a, b) => b.x - a.x);
    const entranceRight = preferredRoomRow(leftRooms).sort((a, b) => a.x - b.x);
    return [
      {
        id: "1F_MAIN_ENTRANCE_TURN_LEFT",
        title: "1층 정문 진입 후 왼쪽 복도",
        floor: "1",
        start: "정문 바깥 중앙 기준점",
        destination: "정문 기준 왼쪽 끝 계단 입구",
        laps: ["정문 출입문", "정문·메인복도 진입점", ...entranceLeft.map((room) => pointLocation(room.id)), "정문 기준 왼쪽 끝 계단 입구"]
      },
      {
        id: "1F_MAIN_ENTRANCE_TURN_RIGHT",
        title: "1층 정문 진입 후 오른쪽 복도",
        floor: "1",
        start: "정문 바깥 중앙 기준점",
        destination: "정문 기준 오른쪽 끝 계단 입구",
        laps: ["정문 출입문", "정문·메인복도 진입점", ...entranceRight.map((room) => pointLocation(room.id)), "정문 기준 오른쪽 끝 계단 입구"]
      },
      ...specialRoutes(floor)
    ];
  }

  const right = preferredRightRoomRow(floor, rightRooms).sort((a, b) => b.x - a.x);
  const left = preferredRoomRow(leftRooms).sort((a, b) => a.x - b.x);
  return [
    basicRoute(floor, "RIGHT", "오른쪽 계단 입구", right),
    basicRoute(floor, "LEFT", "왼쪽 계단 입구", left),
    ...specialRoutes(floor)
  ];
}

function passageRoutes(floor) {
  const label=[2,3,4].includes(floor)?"화장실 연결 통로":floor>=6?`${floor}층 끝방 연결 통로`:null;
  if(!label)return [];
  return [{...specialRoute(`${floor}F_PASSAGE_ENTRY_RETURN`,`${floor}층 ${label} 앞·진입·복귀`,floor,
    `${label} 앞 메인복도`,`${label} 앞 메인복도`,
    [`${label} 앞 10초 정지 완료`,`${label} 진입 후 10초 정지 완료`,`${label} 앞 복귀`]),
    collectionOnly:true,geometryStatus:"entry-coordinate-unverified"}];
}
function stairRoute(floor){return {...specialRoute(`${floor}F_RIGHT_STAIR_INTERIOR`,`${floor}층 오른쪽 계단 입구→내부→입구`,floor,
  '오른쪽 계단 입구','오른쪽 계단 입구',['오른쪽 계단 내부 · 같은 층 평탄부 10초 정지 완료','오른쪽 계단 입구']),collectionOnly:true};}
const ROUTES = FLOOR_MAPS.flatMap(map=>[...floorRoutes(map),...passageRoutes(Number(map.floor)),stairRoute(Number(map.floor))]);
const FLOORS = FLOOR_MAPS.map((map) => String(map.floor));

function reverseRoute(route) {
  const endpoint = route.laps[route.laps.length - 1] || route.destination;
  return {
    ...route,
    id: `${route.id}_REVERSE`,
    sourceRouteId: route.id,
    travelDirection: "reverse",
    title: `${route.floor}층 ${endpoint} → ${route.start} (역방향)`,
    start: endpoint,
    destination: route.start,
    laps: [...route.laps.slice(0, -1).reverse(), route.start]
  };
}

module.exports = { CORE_CENTER_X, FLOOR_MAPS, FLOORS, ROUTES, reverseRoute };
