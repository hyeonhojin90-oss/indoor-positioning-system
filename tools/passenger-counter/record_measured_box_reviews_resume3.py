"""Record actual source reviews before strict-exit comparison; truth remains fixed."""
import json
from pathlib import Path
from evaluate_events import evaluate_windows

truth=[json.loads(x) for x in Path('reviews/green-development-windows.jsonl').read_text().splitlines()]
specs={'green':[None,0,1,2,3,4,5],'green-right80':[None,2,3,4,5],'green-left80':[0,1,2,4,5]}
for name,labels in specs.items():
    root=Path('runs')/(name+'-current-detection-boxes-resume3-full')
    audit=json.loads((root/'completion-audit.json').read_text());assert audit['complete_source'] and audit['replay_parity']
    events=[json.loads(x) for x in (root/'events.jsonl').read_text().splitlines()];assert len(events)==len(labels)
    reviews=[]
    for e,index in zip(events,labels):
        r={k:e[k] for k in ['frame','track_id','direction']}
        r.update(status='uncertain' if index is None else 'accepted',note='Assistant reviewed actual source event frames; identity acceptance is distinct from correct time/direction. Fixed original truth windows unchanged.')
        if index is not None:r['person']=truth[index]['person']
        else:r['note']+=' Unknown-ankle false OUT or early mixed/canonical ID retains uncertainty.'
        reviews.append(r)
    with (root/'identity-review.jsonl').open('x') as f:
        for r in reviews:f.write(json.dumps(r)+'\n')
    result=evaluate_windows(events,truth,0,reviews);result.update(assistant_review=True,human_reviewed=False,independent_accuracy_validated=False)
    with (root/'identity-evaluation.json').open('x') as f:json.dump(result,f,indent=2)
    print(name,result['matched_reviewed_events'],'/6')
