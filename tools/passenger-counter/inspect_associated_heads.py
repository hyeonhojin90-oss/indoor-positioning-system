"""Diagnose simultaneous head/body observations without matching unrelated IDs."""
import argparse,json
from pathlib import Path

def associate_heads(body_pairs,head_boxes):
    votes=[]
    for tid,b in body_pairs:
        w,h=b[2]-b[0],b[3]-b[1];candidates=[]
        for index,head in enumerate(head_boxes):
            x,y=(head[0]+head[2])/2,(head[1]+head[3])/2
            if b[0]-.05*w<=x<=b[2]+.05*w and b[1]-.05*h<=y<=b[1]+.4*h:
                candidates.append((index,(x,y)))
        if len(candidates)==1:votes.append((tid,*candidates[0]))
    return {tid:point for tid,index,point in votes if sum(other==index for _,other,_ in votes)==1}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--body',type=Path,required=True);p.add_argument('--heads',type=Path,required=True)
    p.add_argument('--track-id',type=int,required=True);p.add_argument('--start',type=int,required=True);p.add_argument('--end',type=int,required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    summaries=[json.loads((x/'summary.json').read_text()) for x in (a.body,a.heads)]
    if summaries[0]['source_sha256']!=summaries[1]['source_sha256']:raise ValueError('Different source')
    logs=[[json.loads(x) for x in (d/'tracks.jsonl').read_text().splitlines()] for d in (a.body,a.heads)]
    if len(logs[0])!=len(logs[1]):raise ValueError('Different coverage')
    rows=[]
    for body,head in zip(*logs):
        if body['frame']!=head['frame'] or abs(body['time_s']-head['time_s'])>1e-6:raise ValueError('Not simultaneous')
        if not a.start<=body['frame']<=a.end or not body['door']:continue
        points=associate_heads(list(zip(body['ids'],body['boxes'])),head['raw_boxes'])
        point=points.get(a.track_id);d=body['door']
        value=dict(frame=body['frame'],point=point,normalized_head=[(point[0]-d[0])/(d[2]-d[0]),(point[1]-d[1])/(d[3]-d[1])] if point else None)
        rows.append(value)
        if body['frame']%2==0:print(value)
    with a.output.open('x') as f:json.dump(dict(body=str(a.body),heads=str(a.heads),rows=rows,development_diagnostic_only=True),f,indent=2)
