"""Reuse reviewed identities only under full exact-input and surviving-event parity."""
import copy,json
from pathlib import Path
from evaluate_events import evaluate_windows

def read(p):return [json.loads(x) for x in p.read_text().splitlines()]
key=lambda e:(e['frame'],e['track_id'],e['direction'],e['time_s'],e.get('observation_frame'),e.get('commit_time_s'),e.get('anchor_evidence'))
truth=read(Path('reviews/green-development-windows.jsonl'))
for n in ['green','green-right80','green-left80']:
    before=Path('runs')/(n+'-current-detection-boxes-resume3-full');after=Path('runs')/(n+'-measured-strict-exit-resume3-full')
    a,b=[json.loads((p/'summary.json').read_text()) for p in [before,after]]
    assert a['source_sha256']==b['source_sha256'] and a['frames']==b['frames']==513
    assert read(before/'tracks.jsonl')==read(after/'tracks.jsonl')
    cfgs=[copy.deepcopy(s['config']) for s in [a,b]]
    for cfg in cfgs:cfg.pop('experiment_note',None);cfg['dual_anchor'].pop('exit_unknown_requires_inside',None)
    assert cfgs[0]==cfgs[1]
    old,new=[read(p/'events.jsonl') for p in [before,after]];oldkeys={key(e):e for e in old}
    assert all(key(e) in oldkeys for e in new)
    removed=[e for e in old if key(e) not in {key(x) for x in new}]
    assert all(e['direction']=='out' for e in removed)
    oldreviews={(r['frame'],r['track_id'],r['direction']):r for r in read(before/'identity-review.jsonl')}
    reviews=[]
    for e in new:
        r=copy.deepcopy(oldreviews[(e['frame'],e['track_id'],e['direction'])]);r['review_provenance']=dict(reference=str(before),full_input_trace_exact=True,surviving_event_exact=True,human_reviewed=False);reviews.append(r)
    with (after/'identity-review.jsonl').open('x') as f:
        for r in reviews:f.write(json.dumps(r)+'\n')
    result=evaluate_windows(new,truth,0,reviews);result.update(assistant_review=True,human_reviewed=False,independent_accuracy_validated=False)
    with (after/'identity-evaluation.json').open('x') as f:json.dump(result,f,indent=2)
    with (after/'strict-exit-comparison.json').open('x') as f:json.dump(dict(input_trace_exact=True,surviving_events_exact=True,removed_events=removed,passed=True),f,indent=2)
    print(n,result['matched_reviewed_events'],'/6',b['counts'])
root=Path('runs/green-reverse-measured-strict-exit-resume3-full');events=read(root/'events.jsonl');assert [e['frame'] for e in events]==[191,259,419,454,484]
mirrored=[]
for t in truth:
    a,b=t['frames'];mirrored.append(dict(t,direction='out',frames=[512-b,512-a],start_s=(512-b)/30,end_s=(512-a)/30))
reviews=[]
for e,i in zip(events,[4,5,1,0,None]):
    r={k:e[k] for k in ['frame','track_id','direction']};r.update(status='accepted' if i is not None else 'uncertain',note='Assistant viewed actual reversed-source event collage; canonical mixed/changed IN remains uncertain. Original fixed windows mirrored without tuning.')
    if i is not None:r['person']=truth[i]['person']
    reviews.append(r)
with (root/'identity-review.jsonl').open('x') as f:
    for r in reviews:f.write(json.dumps(r)+'\n')
result=evaluate_windows(events,mirrored,0,reviews);result.update(assistant_review=True,human_reviewed=False,synthetic_reverse=True,independent_accuracy_validated=False)
with (root/'identity-evaluation.json').open('x') as f:json.dump(result,f,indent=2)
print('reverse',result['matched_reviewed_events'],'/6')
