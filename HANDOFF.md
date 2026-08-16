# Project Handoff

## Project Goal

Create a campus indoor navigation prototype for Chosun University IT융합대학.

The current phase focuses on the 4th floor:

- 2D floor view
- clay-style 3D view
- classroom search
- freshman guidance mode
- PDR and magnetic fingerprint based indoor positioning experiment

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

## Current Concern

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
