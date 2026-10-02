"""Measure visually selected planes; not bbox distance or an adopted PDR target."""
import json
from pathlib import Path
import numpy as np
from analyze_glb_plan import read_glb, accessor_array

ROOT = Path(__file__).resolve().parents[2]
source = ROOT / 'indoor/data/raw/scans/2026-09-21/4f-left-corridor.glb'
g, b = read_glb(source)
assert all(not any(k in n for k in ('matrix', 'translation', 'rotation', 'scale'))
           for n in g['nodes']), 'Requires world-space identity nodes'
centers, areas = [], []
for mesh in g['meshes']:
    for primitive in mesh['primitives']:
        p = accessor_array(g, b, primitive['attributes']['POSITION']).astype(float)
        tri = p[accessor_array(g, b, primitive['indices']).reshape(-1, 3)]
        normal = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
        norm = np.linalg.norm(normal, axis=1)
        keep = (norm > 1e-8) & (abs(normal[:, 2]) > .9 * norm)
        centers.append(tri.mean(axis=1)[keep])
        areas.append(norm[keep] / 2)
c, a = np.vstack(centers), np.concatenate(areas)

def plane(mask):
    q, w = c[mask], a[mask]
    return dict(z_m=float(np.average(q[:, 2], weights=w)),
                triangle_count=int(len(q)), surface_area_m2=float(w.sum()),
                centroid_z_range_m=[float(q[:, 2].min()), float(q[:, 2].max())])

restroom = plane((c[:, 0] < -1.5) & (c[:, 2] > 16.10) & (c[:, 2] < 16.35))
end = plane((c[:, 2] > -23.85) & (c[:, 2] < -23.60))
result = dict(source=str(source.relative_to(ROOT)),
              method='Area-weighted centroids of selected transverse wall triangles; Z-axis projection',
              restroom_corridor_end_side_wall=restroom, scanned_end_wall=end,
              restroom_to_scanned_end_wall_m=restroom['z_m'] - end['z_m'],
              status='visually_identified_wall_distance_candidate_not_runtime_adopted',
              limitations=['End wall is not automatically the side-stair entrance threshold.',
                           'Core-left to restroom-left joining segment still needs registration.',
                           'Coordinate units assume GLB meter scale; scan drift is not independently assessed.',
                           'Selected centroid spread is not a survey accuracy confidence interval.'])
core_source = ROOT / 'indoor/data/analysis/detailed-20260915/core-20260915.glb'
cg, cb = read_glb(core_source)
assert all(not any(k in n for k in ('matrix', 'translation', 'rotation', 'scale'))
           for n in cg['nodes']), 'Core measurement requires identity nodes'
def core_wall(name):
    node = next(n for n in cg['nodes'] if n.get('name') == name)
    parts = cg['meshes'][node['mesh']]['primitives']
    pts = np.vstack([accessor_array(cg, cb, pr['attributes']['POSITION']) for pr in parts])
    lo, hi = float(pts[:, 0].min()), float(pts[:, 0].max())
    return dict(node=name, x_min_m=lo, x_max_m=hi, center_x_m=(lo + hi) / 2)

core_edge, restroom_edge = core_wall('Wall_2'), core_wall('Wall_4')
join = restroom_edge['center_x_m'] - core_edge['center_x_m']
result['core_connection'] = dict(source=str(core_source.relative_to(ROOT)),
    core_left_wall=core_edge, restroom_corridor_end_side_wall=restroom_edge,
    reference='Wall-center X-axis separation in structured core model; core width excluded',
    length_m=join)
result['joined_core_left_to_scanned_end_wall_m'] = join + result['restroom_to_scanned_end_wall_m']
result['limitations'][1] = 'Visual correspondence of restroom side wall across scans; no rigid point-cloud registration or independent tape survey. Structured model uses wall centers; textured scan uses observed faces, so wall-thickness convention may differ by centimeters.'
result['status'] = 'joined_glb_reference_to_end_wall_not_runtime_adopted'
out = ROOT / 'indoor/data/analysis/scan-geometry-20260921/left-restroom-planes.json'
out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(result, ensure_ascii=False, indent=2))
