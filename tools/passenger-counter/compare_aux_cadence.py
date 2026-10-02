"""Measure event loss when auxiliary foot observations are skipped, never carried."""
import argparse,json,copy
from pathlib import Path
from replay_counter import replay_rows

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();summary=json.loads((a.run/'summary.json').read_text());rows=[json.loads(x) for x in (a.run/'tracks.jsonl').read_text().splitlines()]
    results=[]
    for interval in (1,2,3,5):
        for phase in range(interval):
            sample=[dict(r,points=r['points'] if r['frame']%interval==phase else [None]*len(r['ids'])) for r in rows]
            result=replay_rows(sample,summary['config']);results.append(dict(interval=interval,phase=phase,**result))
            print(interval,phase,result['counts'],[(e['frame'],e['track_id'],e['direction']) for e in result['events']])
    with a.output.open('x') as f:json.dump(dict(source_run=str(a.run),results=results,observation_skipping_only=True,no_stale_foot_coordinates=True),f,indent=2)
