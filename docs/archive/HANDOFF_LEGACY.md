# Project Handoff

## Project Goal

Create a campus indoor navigation prototype for Chosun University IT융합대학.

The current phase focuses on the 4th floor:

- 2D floor view
- clay-style 3D view
- classroom search
- freshman guidance mode
- PDR and magnetic fingerprint based indoor positioning experiment

The 4th-floor prototype is also the reference for the next phase: reconstructing the 3rd floor and stacking later floors without shifting elevator or stair axes.

## Reconstruction Source Policy

Apply this hierarchy to the 3rd floor and all later floors:

1. GLB/LiDAR geometry is the primary source for walls, corridors, doors, openings, stairs, elevators, restrooms, orientation, and relative proportions.
2. Polycam floor plans and spatial reports validate dimensions and scale.
3. Site photos, user notes, and direct measurements resolve direction and scan omissions.
4. Evacuation plans are used only to map room numbers and rough room ordering. They must not determine geometry or proportions.

Preserve every door and opening visible in a GLB. Treat missing scan data as unknown rather than automatically filling it with a wall or open space. Complete the evidence and ambiguity report before editing geometry.

The full reusable 3rd-floor work prompt is in `3f_rebuild_prompt.md`.

## Floor Reuse Structure

- Floors 4 through 10 are standard floors. Use the confirmed 4th-floor geometry as their shared base and stack it vertically.
- Floors 1 through 3 retain the common left-corridor side of the standard floor.
- On the current right-corridor side, floors 1 through 3 connect to an additional vertical `|`-shaped building wing.
- Model the 3rd floor as `standard-floor shared geometry + low-floor vertical-wing extension`, then store verified room, door, and partition differences as floor-specific overrides.
- `Left corridor` and `right corridor` are temporary project region names. Always pair them with coordinates and the viewing reference to prevent another mirrored layout.

## Core 4F Layout Understanding

The 4F structure should be treated as a `ㅗ` shape, not `ㅜ`.

- A long main corridor runs horizontally.
- The elevator/stair hub corridor connects into the main corridor.
- The user starts around the 4F elevator hub.

Direction 기준:

- From the elevator hub, left direction: `4218`, `4222`, `4225`, `4228`, and lower-side rooms such as `4120~4128`.
- From the elevator hub, right direction: `4213`, `4212`, `4211`, `4210`, `4209`, `4208`, `4207`, `4206`, `4204`.
- `4213` is reached by going right from the elevator.
- `4218` is closer to the elevator than `4210`.

Important correction:

- A previous clay 3D draft had some directions reversed.
- Preserve the latest project orientation unless the user explicitly corrects it again.

## Current Data

Main project folder:

```text
it_4f_prototype/
```

Useful files:

```text
it_4f_prototype/data/it_4f_map.json
it_4f_prototype/data/it_4f_magnetic_measurements.json
it_4f_prototype/index.html
it_4f_prototype/src/app.js
it_4f_prototype/clay.html
it_4f_prototype/src/clay4f.js
it_4f_prototype/src/clay.css
```

GLB/LiDAR viewer folder:

```text
glb_viewer/
```

Known GLB assets:

```text
glb_viewer/assets/it_4f_elevator_stairs.glb
glb_viewer/assets/it_4f_right_from_elevator_left_wing.glb
glb_viewer/assets/it_4f_left_from_elevator_right_wing.glb
```

## Magnetic Measurements

The user collected 4F magnetic measurements around:

- 4F_EV_FRONT
- 4F_4213_FRONT
- 4F_4212_FRONT
- 4F_4210_FRONT
- 4F_4208_FRONT
- 4F_4204_FRONT
- left stairs/front and inside
- 4F_4218_FRONT
- 4F_4225_FRONT
- 4F_4227_FRONT
- 4F_4128_FRONT

Use these as rough fingerprints, not exact absolute positions.

## Latest 2D/PDR Update

The 2D prototype was revised to version 4F map graph v0.4.

- The full layout is a ㅗ shape: horizontal main corridor plus a lower elevator/stair hub connector.
- Screen left from the elevator contains 4218~4228 and 4120~4128.
- Screen right from the elevator contains 4213~4204.
- 4213 is the first room next to the hub on the right side; 4212, 4211, and 4210 continue outward.
- Room widths now follow the evacuation-plan proportions instead of equal-size blocks.
- PDR starts at the elevator hub, moves along the connector to the main corridor, and then turns left/right.
- Magnetic correction uses Total difference, each point's provisional standard deviation, and PDR proximity.
- Desktop and 390 px mobile layouts were checked with no console errors.

The room coordinates are still first-pass map alignment values. Ask the user to point out any remaining room-position mismatch before treating them as final.

## Current Concern

- 3층 끝 화장실 통로와 사이드계단은 4층 구조를 그대로 재사용한다.
- 화장실 통로 뒤 약 `1.77m` 벽이 끝난 지점이 계단 입구이며, 입구 이후 같은 경계 벽을 더 연장하지 않는다.
- 위에서 볼 때 신규 공간/IT홀은 세로 확장 복도의 왼쪽, `3104-1/2`는 반대편이다.

Files from `Downloads` may be newer but are not automatically safe to overwrite:

```text
C:\Users\20222967\Downloads\clay.html
C:\Users\20222967\Downloads\clay4f.js
```

The downloaded `clay4f.js` contains useful features such as magnetic fingerprint display and center stair drawing, but it may conflict with the latest corrected room/elevator/stair orientation.

Recommended merge approach:

1. Keep the current project orientation.
2. Bring useful visualization features from the downloaded `clay4f.js`.
3. Do not blindly replace the project file.

## How To Continue In A New Codex Account

Tell Codex:

```text
This project is being continued from another account.
First read README.md, HANDOFF.md, TODO.md,
it_4f_prototype/data/it_4f_map.json,
and it_4f_prototype/src/clay4f.js.
Then summarize the current state before editing.
```
