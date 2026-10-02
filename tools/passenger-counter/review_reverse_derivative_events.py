"""Assistant review of reversed source; mirror existing windows without retuning."""
import json
from pathlib import Path
from evaluate_events import evaluate_windows

root=Path('runs/green-reverse-segment-trained-box-20261001-r2-full')
s=json.loads((root/'summary.json').read_text());assert s['frames']==513 and s['source_fps']==30
truth=[json.loads(x) for x in Path('reviews/green-development-windows.jsonl').read_text().splitlines()]
reversed_truth=[]
for t in truth:
    a,b=t['frames'];reversed_truth.append(dict(t,direction='out',frames=[512-b,512-a],start_s=(512-b)/30,end_s=(512-a)/30))
events=[json.loads(x) for x in (root/'events.jsonl').read_text().splitlines()]
assert [e['frame'] for e in events]==[191,260,420,454,485]
reviews=[]
for e,i in zip(events,[4,5,1,0,None]):
    r={k:e[k] for k in ['frame','track_id','direction']}
    r.update(status='accepted' if i is not None else 'uncertain',note='Assistant viewed actual reverse-source event frames; identity acceptance does not establish a correct passage time or direction.')
    if i is not None:r['person']=truth[i]['person']
    else:r['note']+=' Mixed/changed canonical ID197 retains a false IN in reversed boarding; not classified as a legitimate arrival.'
    reviews.append(r)
with (root/'identity-review.jsonl').open('x') as f:
    for r in reviews:f.write(json.dumps(r)+'\n')
result=evaluate_windows(events,reversed_truth,0,reviews)
result.update(assistant_review=True,human_reviewed=False,synthetic_reverse=True,independent_accuracy_validated=False,original_windows_unchanged=True,source_sha256=s['source_sha256'])
with (root/'identity-evaluation.json').open('x') as f:json.dump(result,f,indent=2)
with (root/'mirrored-development-windows.json').open('x') as f:json.dump(reversed_truth,f,indent=2)
print('Mirrored fixed windows',result['matched_reviewed_events'],'/6; counts',s['counts'])
