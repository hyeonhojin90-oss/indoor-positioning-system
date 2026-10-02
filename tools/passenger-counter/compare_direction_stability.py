"""Predeclared debounce comparisons; saved observations are development diagnostics."""
import argparse,json,copy
from pathlib import Path
from replay_counter import replay_rows
from replay_reverse_trace import reverse_rows

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();summary=json.loads((a.run/'summary.json').read_text());rows=[json.loads(x) for x in (a.run/'tracks.jsonl').read_text().splitlines()]
    results=[]
    for confirm in (2,4,6,10):
        cfg=copy.deepcopy(summary['config']);cfg['counting'].update(confirm=confirm,min_entry_displacement=0)
        f=replay_rows(rows,cfg);r=replay_rows(reverse_rows(rows,summary['source_fps']),cfg)
        results.append(dict(confirm=confirm,forward=f,reverse=r,config=cfg))
        print(confirm,[(e['frame'],e['track_id'],e['direction']) for e in f['events']],[(e['frame'],e['track_id'],e['direction']) for e in r['events']])
    with a.output.open('x') as f:json.dump(dict(source_run=str(a.run),results=results,development_replay_only=True),f,indent=2)
