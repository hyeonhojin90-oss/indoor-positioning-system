"""Describe saved person trajectories without guessing an identity or adding counts."""
import argparse
import hashlib
import json
from pathlib import Path

def inspect(run,start,end,step=5):
    rows=[json.loads(x) for x in (run/'tracks.jsonl').read_text().splitlines()]
    result=[]
    for row in rows[start:end+1:step]:
        door=row['door']
        if door is None:continue
        dw,dh=door[2]-door[0],door[3]-door[1]
        people=[]
        for tid,b in zip(row.get('raw_ids',row['ids']),row.get('raw_boxes',row['boxes'])):
            u=((b[0]+b[2])/2-door[0])/dw;v=(b[3]-door[1])/dh
            if -.5<=u<=1.5:
                people.append(dict(id=tid,x=round(u,3),foot=round(v,3),head=round((b[1]-door[1])/dh,3),
                                   box=[round(z,1) for z in b]))
        result.append(dict(frame=row['frame'],generation=row['door_generation'],
                           people=sorted(people,key=lambda p:p['x'])))
    return dict(run=str(run),tracks_sha256=hashlib.sha256((run/'tracks.jsonl').read_bytes()).hexdigest(),
                start=start,end=end,step=step,rows=result,identity_inferred=False)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True)
    p.add_argument('--start',type=int,required=True);p.add_argument('--end',type=int,required=True)
    p.add_argument('--step',type=int,default=5);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if a.start<0 or a.end<a.start or a.step<1:p.error('Invalid frame range')
    value=inspect(a.run,a.start,a.end,a.step)
    with a.output.open('x',encoding='utf-8') as f:json.dump(value,f,indent=2)
    for r in value['rows']:print(r['frame'],[(q['id'],q['x'],q['foot'],q['head']) for q in r['people']])
