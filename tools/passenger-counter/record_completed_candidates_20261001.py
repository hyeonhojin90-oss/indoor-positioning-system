"""Persist source-image reviews of completed, rejected development candidates."""
import json
from pathlib import Path
from evaluate_events import evaluate_windows

def read(p):
    return [json.loads(x) for x in Path(p).read_text().splitlines() if x.strip()]

people=['olive-shirt-white-bag','brown-shirt-white-bag','grey-hair-backpack','teal-shirt','yellow-bag-umbrella','white-shirt-grey-shorts']
truth=read('reviews/green-development-windows.jsonl')
cases={
 'green-retention-door-20261001-full':[(64,26,'in',0,'accepted'),(260,1,'in',3,'accepted'),(327,89,'in',4,'accepted'),(366,93,'in',5,'accepted')],
 'green-shift-right80-retention-door-20261001-full':[(56,6,'out',None,'uncertain'),(114,3,'in',None,'uncertain'),(176,67,'in',2,'accepted'),(304,74,'in',4,'accepted'),(356,82,'in',5,'accepted')],
 'green-shift-left80-retention-door-20261001-full':[(64,21,'in',0,'accepted'),(179,55,'in',2,'accepted'),(306,71,'in',4,'accepted'),(320,71,'out',4,'accepted'),(349,71,'in',4,'duplicate'),(358,76,'in',5,'accepted')],
 'green-single-pose-onnx-20261001-full':[(66,19,'in',0,'accepted'),(121,2,'in',1,'accepted'),(182,40,'in',2,'accepted'),(333,50,'in',4,'accepted'),(357,52,'in',5,'accepted')],
 'green-shift-right80-single-pose-onnx-20261001-full':[(107,29,'out',None,'uncertain'),(113,1,'in',None,'uncertain'),(182,33,'in',2,'accepted'),(300,43,'in',4,'accepted'),(354,44,'in',5,'accepted')],
 'green-shift-right80-single-pose-medium-20261001-full':[(115,3,'in',None,'uncertain'),(119,30,'out',3,'accepted'),(180,34,'in',2,'accepted'),(247,30,'in',3,'accepted'),(298,42,'in',4,'accepted'),(354,49,'in',5,'accepted')],
 'green-reverse-aux-20261001-full':[(192,78,'out',4,'accepted'),(262,61,'out',5,'accepted'),(418,200,'out',1,'accepted'),(482,262,'in',0,'accepted')],
}
for name, entries in cases.items():
    run=Path('runs')/name
    shifted='shift-' in name; reverse='reverse-' in name
    reviews=[dict(frame=f,track_id=i,direction=d,status=s,person=None if who is None else people[who],
                  note='Assistant reviewed exact source event/observation images and tracked boxes. Accepted identifies the person only; timing/direction still must match unchanged windows. Uncertain excludes mixed IDs or persons outside the reviewed six.',
                  derived_scene=shifted or reverse,independent_validation=False)
             for f,i,d,who,s in entries]
    with (run/'identity-review.jsonl').open('x',encoding='utf-8') as stream:
        for row in reviews:stream.write(json.dumps(row)+'\n')
    windows=truth
    if reverse:
        windows=[dict(t,direction='out',frames=[512-t['frames'][1],512-t['frames'][0]],
                      start_s=(512-t['frames'][1])/30,end_s=(512-t['frames'][0])/30,
                      derived_from='reviews/green-development-windows.jsonl',independent_validation=False) for t in truth]
        with (run/'derived-review-windows.jsonl').open('x') as stream:
            for row in windows:stream.write(json.dumps(row)+'\n')
    result=evaluate_windows(read(run/'events.jsonl'),windows,0,reviews)
    with (run/'identity-evaluation.json').open('x') as stream:json.dump(result,stream,indent=2)
    print(name,result['matched_reviewed_events'])
