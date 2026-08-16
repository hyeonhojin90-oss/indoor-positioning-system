# Indoor Navigation Prototype

Chosun University IT College indoor navigation prototype.

## Current Focus

- Building: IT융합대학
- Floor: 4F first
- Goal: 2D floor map, clay-style 3D map, and indoor guidance using PDR plus magnetic fingerprint experiments.

## Run Locally

Open a terminal in this repository and run:

```powershell
cd .\it_4f_prototype
python -m http.server 8125
```

Then open:

```text
http://127.0.0.1:8125/
http://127.0.0.1:8125/clay.html
```

## Important Files

- `it_4f_prototype/index.html`: 2D/PDR prototype
- `it_4f_prototype/src/app.js`: 2D map and guidance logic
- `it_4f_prototype/clay.html`: clay 3D prototype page
- `it_4f_prototype/src/clay4f.js`: clay 3D model logic
- `it_4f_prototype/data/it_4f_map.json`: 4F map data
- `it_4f_prototype/data/it_4f_magnetic_measurements.json`: magnetic measurement data
- `glb_viewer/`: LiDAR/GLB scan viewer and assets

## Handoff

Before continuing work with another Codex account, read `HANDOFF.md` and `TODO.md`.
