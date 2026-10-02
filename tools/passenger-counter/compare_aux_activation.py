"""Skip auxiliary observations outside observed doorway approach bands."""
import argparse,json
from pathlib import Path
from replay_counter import replay_rows

def approach_visible(row,upper):
    door=row['door']
    if door is None:return False
    x1,y1,x2,y2=door
    for b in row['raw_boxes']:
        u=(b[3]-y1)/(y2-y1);v=((b[0]+b[2])/2-x1)/(x2-x1)
        if .9<=u<=upper and -.1<=v<=1.1:return True
    return False

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();s=json.loads((a.run/'summary.json').read_text());rows=[json.loads(x) for x in (a.run/'tracks.jsonl').read_text().splitlines()];results=[]
    for upper in (1.2,1.3,1.5):
        calls=[approach_visible(r,upper) for r in rows]
        sampled=[dict(r,points=r['points'] if active else [None]*len(r['ids'])) for r,active in zip(rows,calls)]
        result=replay_rows(sampled,s['config']);results.append(dict(approach_upper=upper,aux_calls=sum(calls),**result))
        print(upper,sum(calls),result['counts'],[(e['frame'],e['track_id']) for e in result['events']])
    with a.output.open('x') as f:json.dump(dict(source_run=str(a.run),results=results,development_replay_only=True),f,indent=2)
