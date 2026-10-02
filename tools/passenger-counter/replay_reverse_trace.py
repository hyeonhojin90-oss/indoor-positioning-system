"""Reverse saved observations to diagnose direction rules before new inference."""
import argparse,json
from pathlib import Path
from replay_counter import replay_rows

def reverse_rows(rows,fps):
    if fps<=0 or any(r['frame']!=i for i,r in enumerate(rows)):raise ValueError('Invalid complete trace')
    return [dict(row,frame=i,time_s=i/fps) for i,row in enumerate(reversed(rows))]

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();s=json.loads((a.run/'summary.json').read_text());rows=[json.loads(x) for x in (a.run/'tracks.jsonl').read_text().splitlines()]
    result=replay_rows(reverse_rows(rows,s['source_fps']),s['config'])
    result.update(source_run=str(a.run),reversed_observations_only=True,independent_validation=False)
    with a.output.open('x') as f:json.dump(result,f,indent=2)
    print(json.dumps(result))
