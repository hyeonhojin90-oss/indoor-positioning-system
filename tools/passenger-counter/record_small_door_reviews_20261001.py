import json
from pathlib import Path
from evaluate_events import evaluate_windows

def read(p):return [json.loads(x) for x in Path(p).read_text().splitlines() if x.strip()]
truth=read('reviews/green-development-windows.jsonl')
cases={
 'green-small-last-door-20261001-full':[(353,93,'in','white-shirt-grey-shorts','accepted'),(372,89,'in','yellow-bag-umbrella','accepted')],
 'green-shift-left80-small-last-door-20261001-full':[(64,21,'in','olive-shirt-white-bag','accepted'),(349,76,'in','white-shirt-grey-shorts','accepted'),(419,71,'in','yellow-bag-umbrella','accepted')],
 'green-shift-right80-small-last-door-20261001-full':[(56,6,'out',None,'uncertain'),(114,3,'in',None,'uncertain'),(305,74,'in','yellow-bag-umbrella','accepted'),(370,82,'in','white-shirt-grey-shorts','accepted')]
}
for name,entries in cases.items():
    run=Path('runs')/name
    reviews=[dict(frame=f,track_id=i,direction=d,person=person,status=status,
                  note='Actual source event/observation montage reviewed. Fixed windows unchanged; accepted identifies a person only. Mixed brown-to-olive ID and unreviewed inside-person alighting excluded.',
                  derived_scene='shift-' in name,independent_validation=False) for f,i,d,person,status in entries]
    with (run/'identity-review.jsonl').open('x') as stream:
        for row in reviews:stream.write(json.dumps(row)+'\n')
    result=evaluate_windows(read(run/'events.jsonl'),truth,0,reviews)
    with (run/'identity-evaluation.json').open('x') as stream:json.dump(result,stream,indent=2)
    print(name,result['matched_reviewed_events'])
