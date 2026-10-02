import json
from pathlib import Path

def main():
    paths=['green-person-seg-exit-guard-onnx-box-render-20261001-r2-full','green-photo-enriched-confidence-20261001-r2-full',
           'green-right80-person-seg-exit-guard-onnx-box-render-20261001-r2-full','green-right80-photo-enriched-confidence-20261001-r2-full']
    report=[]
    for name in paths:
        root=Path('runs')/name;summary=json.loads((root/'summary.json').read_text())
        rows=[json.loads(x) for x in (root/'tracks.jsonl').read_text().splitlines()]
        geometries={};samples=[]
        for r in rows:
            if r['door']:geometries.setdefault(str(r['door_generation']),set()).add(tuple(r['door']))
            if not r['door'] or not 60<=r['frame']<=100:continue
            for i,tid in enumerate(r['ids']):
                if tid not in (2,4,19,31):continue
                b=r['boxes'][i];d=r['door'];foot=r.get('points',[None]*len(r['ids']))[i]
                samples.append(dict(frame=r['frame'],tid=tid,body_u=(b[3]-d[1])/(d[3]-d[1]),
                    body_v=((b[0]+b[2])/2-d[0])/(d[2]-d[0]),
                    foot_u=(foot[1]-d[1])/(d[3]-d[1]) if foot else None,
                    foot_v=(foot[0]-d[0])/(d[2]-d[0]) if foot else None))
        report.append(dict(run=name,counts=summary['counts'],source_sha256=summary['source_sha256'],
            locked_boxes_by_generation={k:list(v) for k,v in geometries.items()},samples=samples))
    with Path('runs/door-band-body-foot-diagnostic-r2.json').open('x') as f:json.dump(report,f,indent=2)
    for r in report:
        print(r['run'],r['locked_boxes_by_generation'])
        for s in r['samples']:
            if s['foot_u'] is not None or s['frame'] in [63,77,89,92,95]:print(s)

if __name__=='__main__':main()
