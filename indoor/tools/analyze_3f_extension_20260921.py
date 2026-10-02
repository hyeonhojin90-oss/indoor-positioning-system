"""Reproducible selected-surface measurements for the 2026-09-21 3F scan."""
from pathlib import Path
import json
import hashlib
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from analyze_glb_plan import read_glb, accessor_array

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / 'indoor/data/raw/scans/2026-09-21/3f-right-corridor.glb'
OUT = ROOT / 'indoor/data/analysis/scan-geometry-20260921'
g,b = read_glb(SRC)
assert all(not any(k in n for k in ('matrix','translation','rotation','scale')) for n in g['nodes'])
cs, ns, areas, points = [], [], [], []
for mesh in g['meshes']:
    for pr in mesh['primitives']:
        p = accessor_array(g,b,pr['attributes']['POSITION']).astype(float)
        tri = p[accessor_array(g,b,pr['indices']).reshape(-1,3)]
        n = np.cross(tri[:,1]-tri[:,0], tri[:,2]-tri[:,0])
        norm = np.linalg.norm(n,axis=1)
        ok = norm > 1e-8
        cs.append(tri.mean(axis=1)[ok]); ns.append(n[ok]/norm[ok,None])
        areas.append(norm[ok]/2); points.append(p)
c,n,a = np.vstack(cs),np.vstack(ns),np.concatenate(areas)
p = np.vstack(points)

def surface(axis, limits):
    mask = abs(n[:,axis]) > .95
    for ax,lo,hi in limits:
        mask &= (c[:,ax]>lo)&(c[:,ax]<hi)
    q,w = c[mask],a[mask]
    assert len(q)>10
    return dict(axis=axis,coordinate_m=float(np.average(q[:,axis],weights=w)),
                area_m2=float(w.sum()),triangles=int(len(q)),
                selection_box=limits,centroid_range_m=[float(q[:,axis].min()),float(q[:,axis].max())])

s = {
 'branch_end':surface(0,[(0,-23.85,-23.25),(2,-14.7,-12.1)]),
 'free_branch_boundary':surface(0,[(0,1.55,1.95),(2,-25,-15)]),
 'branch_side_a':surface(2,[(0,-22,0),(2,-12.55,-12.1)]),
 'branch_side_b':surface(2,[(0,-22,0),(2,-14.7,-14.2)]),
 'free_main_boundary':surface(0,[(0,8.25,8.7),(2,-26,-15)]),
 'free_far_wall':surface(2,[(0,2.3,8),(2,-27.0,-26.4)]),
 'free_near_wall':surface(2,[(0,2.3,8),(2,-12.7,-12.1)]),
}
v = lambda key:s[key]['coordinate_m']
measurements = {
 'branch_straight_length_m':v('free_branch_boundary')-v('branch_end'),
 'branch_wall_face_width_m':v('branch_side_a')-v('branch_side_b'),
 'free_wall_reference_width_m':v('free_main_boundary')-v('free_branch_boundary'),
 'free_wall_reference_length_m':v('free_near_wall')-v('free_far_wall'),
}
result = dict(source=str(SRC.relative_to(ROOT)),sha256=hashlib.sha256(SRC.read_bytes()).hexdigest(),
 measurements=measurements,surfaces=s,
 method='Area-weighted transverse/longitudinal wall triangle centroids after visual region identification. Axis projected distances, not full bbox.',
 limitations=['Free-space dimensions describe selected wall lines, not obstacle-free clearance.',
              'Wall recesses, columns, door setbacks and scan drift mean local clear widths differ.',
              'Door presence is visually observed; room-number assignment requires legible signage or independent floorplan correspondence.',
              'Unscanned room interiors cannot establish room depth or equal room split.',
              'GLB meter scale assumed; no independent tape or calibrated survey validation.'])
(OUT/'3f-extension-measurements.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

# Equal-scale wall/floor evidence plot, clipped only to the surveyed extension region.
W,H=1500,850; scale=34; xmin=-25; zmin=-29
im=Image.new('RGB',(W,H),'#f7f8fa');d=ImageDraw.Draw(im)
font=ImageFont.truetype('C:/Windows/Fonts/malgun.ttf',20)
small=ImageFont.truetype('C:/Windows/Fonts/malgun.ttf',17)
def xy(x,z):return (round(70+(x-xmin)*scale),round(80+(z-zmin)*scale))
q=p[(p[:,0]>-25)&(p[:,0]<14)&(p[:,2]>-29)&(p[:,2]<-10)]
for pt in q[::2]:d.point(xy(pt[0],pt[2]),fill='#869398' if pt[1]>-.7 else '#c0d7d0')
for key,axis,other1,other2,color in [('branch_end',0,-15.5,-11.5,'#cc3333'),('free_branch_boundary',0,-27,-11.5,'#cc3333'),('branch_side_a',2,-23.5,1.7,'#2563eb'),('branch_side_b',2,-23.5,1.7,'#2563eb')]:
    val=v(key);ends=[xy(val,other1),xy(val,other2)] if axis==0 else [xy(other1,val),xy(other2,val)]
    d.line(ends,fill=color,width=3)
d.text((45,15),'3층 새 GLB 증축부 — 실제 벽 기준 평면 분석 (등축척)',font=font,fill='#172033')
d.text(xy(-21,-16.4),f"안쪽 직선 복도 약 {measurements['branch_straight_length_m']:.2f}m / 벽 사이 폭 약 {measurements['branch_wall_face_width_m']:.2f}m",font=small,fill='#143f80')
d.text(xy(2,-24),'넓은 연결공간',font=small,fill='#163b30')
d.text(xy(2,-23),f"벽 기준 약 {measurements['free_wall_reference_width_m']:.2f} × {measurements['free_wall_reference_length_m']:.2f}m",font=small,fill='#163b30')
d.text(xy(9,-18),'메인복도',font=small,fill='#163b30')
d.text((45,770),'빨강: 복도 길이 기준선 / 파랑: 복도 양쪽 벽. 문 번호·방 내부 분할은 이 그림에서 확정하지 않음.',font=small,fill='#333333')
d.text((45,805),'스캔의 빈 조각을 통행 가능한 입구로 해석하지 않음. 치수는 GLB 좌표 기반이며 실측 정확도 보증값이 아님.',font=small,fill='#333333')
im.save(OUT/'3f-extension-measured-plan.png')
print(json.dumps(measurements,indent=2))
