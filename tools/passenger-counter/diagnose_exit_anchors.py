"""Diagnose measured-foot/body OUT disagreement; no event suppression or tuning."""
import argparse
import hashlib
import json
from pathlib import Path

def main():
    p=argparse.ArgumentParser();p.add_argument('--runs',nargs='+',required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    report=[]
    for filename in a.runs:
        root=Path(filename)
        summary=json.loads((root/'summary.json').read_text())
        assert summary['config'].get('person_anchor_kind')=='pose_dual'
        assert hashlib.sha256(Path(summary['source']).read_bytes()).hexdigest()==summary['source_sha256']
        rows=[json.loads(s) for s in (root/'tracks.jsonl').read_text().splitlines()]
        assert len(rows)==summary['frames']
        events=[json.loads(s) for s in (root/'events.jsonl').read_text().splitlines()]
        cfg=summary['config']['counting'];items=[]
        for e in events:
            if e['direction']!='out':continue
            fid=e['observation_frame'];r=rows[fid];tid=e['track_id']
            assert tid in r['ids']
            idx=r['ids'].index(tid);foot=r['points'][idx];door=r['door']
            item=dict(event=e,body_box=r['boxes'][idx],foot=foot,door=door)
            if foot:
                u=(foot[1]-door[1])/(door[3]-door[1]);v=(foot[0]-door[0])/(door[2]-door[0])
                band=cfg.get('transverse_band',0)
                item.update(foot_u=u,foot_v=v,
                            confident_foot_outside=u>cfg['high'] or v< -band or v>1+band)
            else:item['confident_foot_outside']=None
            # Current leading foot and future observed evidence, no guessed feet.
            future=[]
            for rr in rows[fid+1:min(len(rows),fid+31)]:
                if rr['door_generation']!=r['door_generation'] or not rr['door']:break
                if tid not in rr['ids']:continue
                pt=rr['points'][rr['ids'].index(tid)]
                if pt:future.append(dict(frame=rr['frame'],point=pt))
            item['next_second_measured_feet']=future
            items.append(item)
        report.append(dict(run=filename,counts=summary['counts'],exits=items,
                           source_sha256=summary['source_sha256']))
        print(filename,[(x['event']['frame'],x['event']['track_id'],x['confident_foot_outside']) for x in items])
    with a.output.open('x') as f:
        json.dump(dict(runs=report,diagnostic_only=True,events_unchanged=True,
                       no_independent_alighting_validation=True),f,indent=2)

if __name__=='__main__':main()
