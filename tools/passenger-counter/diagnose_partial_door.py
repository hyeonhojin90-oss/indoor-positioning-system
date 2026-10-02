"""Replay saved candidates: keep TTL unchanged when a contained shrink is ignored."""
import argparse,copy,json
from pathlib import Path
from counter import DoorLock
from door_occlusion_guard import contained_shrink
from replay_counter import replay_rows

def shadow(run,guard):
    summary=json.loads((run/'summary.json').read_text());cfg=summary['config']
    lock=DoorLock(**cfg['door_lock'])
    detections={r['frame']:r for r in map(json.loads,(run/'doors.jsonl').read_text().splitlines())}
    rows=list(map(json.loads,(run/'tracks.jsonl').read_text().splitlines()));output=copy.deepcopy(rows);rejected=[]
    for row in output:
        now=row['time_s'];d=detections.get(row['frame'])
        if d:
            if not d['bus_visible']:lock.reset()
            else:
                chosen=d['candidate']
                if guard and contained_shrink(lock.valid_box(now),chosen,lock.min_iou):
                    rejected.append(dict(frame=row['frame'],candidate=chosen,reference=lock.box,
                                         last_seen=lock.last_seen,ttl=lock.ttl))
                    chosen=None
                lock.observe(chosen,now)
        if now-lock.last_seen>lock.ttl:lock.observe(None,now)
        row['door']=lock.box;row['door_generation']=lock.generation
    parity=all(a['door']==(list(b['door']) if b['door'] else None) and a['door_generation']==b['door_generation'] for a,b in zip(rows,output))
    return dict(saved_geometry_parity=parity,rejected=rejected,replay=replay_rows(output,cfg))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    baseline=shadow(a.run,False)
    if not baseline['saved_geometry_parity']:raise ValueError('Unmodified geometry does not reproduce source run')
    result=dict(run=str(a.run),diagnostic_only=True,new_inference=False,independent_validation=False,
                limitation='Inference schedule, bus acceptance, selected candidates, bridge and auxiliary feet depend on original door history.',
                baseline=baseline,guard=shadow(a.run,True))
    with a.output.open('x') as f:json.dump(result,f,indent=2)
    print(json.dumps(dict(baseline=baseline['replay']['counts'],guard=result['guard']['replay']['counts'],rejected_frames=[r['frame'] for r in result['guard']['rejected']])))
