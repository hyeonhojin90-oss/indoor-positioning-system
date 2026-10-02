"""Reproducible selected-surface measurements for the 2026-09-21 2F scan."""
from pathlib import Path
import json
import hashlib
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from analyze_glb_plan import read_glb, accessor_array

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / 'indoor/data/raw/scans/2026-09-21/2f-rescan.glb'
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

def fit_wall(zlo,zhi):
    mask=(abs(n[:,2])>.9)&(c[:,0]>-3)&(c[:,0]<19)&(c[:,2]>zlo)&(c[:,2]<zhi)
    q,w=c[mask],a[mask]
    coef=np.polyfit(q[:,0],q[:,2],1,w=np.sqrt(w))
    residual=q[:,2]-np.polyval(coef,q[:,0])
    return dict(slope=float(coef[0]),intercept=float(coef[1]),area_m2=float(w.sum()),
                rms_m=float(np.sqrt(np.average(residual**2,weights=w))),
                selection=dict(x=[-3,19],z=[zlo,zhi],normal_z_min=.9))

s={
 'main_entry_adjacent_face':surface(0,[(0,-12.9,-12.3),(2,14,18)]),
 'extension_start':surface(0,[(0,-6.3,-5.1),(2,5,10)]),
 'extension_end':surface(0,[(0,19.3,19.8),(2,11,14)]),
 'open_back':surface(0,[(0,-5.6,-5.1),(2,-1.5,3.5)]),
 'study_back':surface(0,[(0,-6.3,-5.1),(2,5,10)]),
 'open_study_divider':surface(2,[(0,-11.5,-6),(2,3.8,4.7)]),
}
walls=[fit_wall(10.5,12),fit_wall(14,15.8)]
slope=sum(w['slope'] for w in walls)/2
start=s['extension_start']['coordinate_m'];end=s['extension_end']['coordinate_m']
widths={str(x):float((np.polyval([walls[1]['slope'],walls[1]['intercept']],x)-np.polyval([walls[0]['slope'],walls[0]['intercept']],x))/np.sqrt(1+slope*slope)) for x in [0,10,18]}
measurements=dict(extension_start_wall_to_end_wall_m=float((end-start)*np.sqrt(1+slope*slope)),
 main_entry_to_extension_start_m=float((start-s['main_entry_adjacent_face']['coordinate_m'])*np.sqrt(1+slope*slope)),
 main_entry_to_end_m=float((end-s['main_entry_adjacent_face']['coordinate_m'])*np.sqrt(1+slope*slope)),
 extension_local_widths_m=widths,axis_angle_deg=float(np.degrees(np.arctan(slope))))
result=dict(source=str(SRC.relative_to(ROOT)),sha256=hashlib.sha256(SRC.read_bytes()).hexdigest(),
 measurements=measurements,surfaces=s,wall_fits=walls,
 limitations=['Start is the study back-wall continuation, not main corridor center or stair entrance.',
 'End is scanned transverse wall, not a verified classroom threshold.',
 'Widths vary in the mesh; taper may include scan drift. Do not treat as survey precision.',
 'GLB meter scale assumed. Unscanned room interiors and illegible door numbers are not established.'])
(OUT/'2f-extension-measurements.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
im=Image.new('RGB',(1300,1000),'#f8fafc');d=ImageDraw.Draw(im)
font=ImageFont.truetype('C:/Windows/Fonts/malgun.ttf',22)
small=ImageFont.truetype('C:/Windows/Fonts/malgun.ttf',18)
scale=29
def xy(x,z):return (round(75+(x+17)*scale),round(115+(z+6)*scale))
q=p[(p[:,0]>-17)&(p[:,2]>-6)&(p[:,2]<18)]
for pt in q[::2]:d.point(xy(pt[0],pt[2]),fill='#8e9b9c')
for w in walls:
 d.line([xy(x,np.polyval([w['slope'],w['intercept']],x)) for x in [-3,19]],fill='#2563eb',width=3)
for x in [start,end]:d.line([xy(x,10),xy(x,16.5)],fill='#dc2626',width=3)
for x,z,t in [(-15,-5,'메인복도'),(-11,0,'2107 대응 공간'),(-11,6,'책상공간'),(-10,15.7,'증축부 연결공간'),(1,16.5,'안쪽 직선 복도')]:d.text(xy(x,z),t,font=small,fill='#172554')
d.text((35,25),'2층 새 GLB — 벽 기준 분석 / 같은 축척 X·Z',font=font,fill='#172554')
d.text((35,65),f"빨강 기준선 사이 약 {measurements['extension_start_wall_to_end_wall_m']:.2f}m · 파랑은 양쪽 벽 적합선",font=small,fill='#172554')
d.text((35,860),'복도 폭: 입구 쪽~안쪽 약 '+ ' / '.join(f'{v:.2f}m' for v in widths.values()),font=small,fill='#172554')
d.text((35,900),'호실 번호는 기존 설명과 대응. 방 내부 크기·출입문 번호를 이 스캔만으로 확정하지 않음.',font=small,fill='#333333')
d.text((35,938),'폭 변화에는 스캔 변형이 포함될 수 있음. 기둥/TDM 사이 최소 유효 폭과는 다른 값.',font=small,fill='#333333')
im.save(OUT/'2f-extension-measured-plan.png')
print(json.dumps(result['measurements'],indent=2))
