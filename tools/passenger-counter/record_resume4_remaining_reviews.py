"""Save identities from actually viewed right-shift/reverse event montages."""
import json
from pathlib import Path
from evaluate_events import evaluate_windows, evaluate_person_directions


def read(path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]


def main():
    truth=read(Path('reviews/green-development-windows.jsonl'))
    mirrored=[]
    for row in truth:
        start,end=row['frames']
        mirrored.append(dict(row,direction='out',frames=[512-end,512-start],
                             start_s=(512-end)/30,end_s=(512-start)/30))
    cases=[('green-right80-osnet-observed-resume4-full',truth,
            {2:truth[1]['person'],56:truth[2]['person'],3:truth[3]['person'],
             105:truth[4]['person'],108:truth[5]['person']}),
           ('green-reverse-osnet-observed-resume4-full',mirrored,
            {14:truth[4]['person'],43:truth[5]['person'],151:truth[1]['person'],
             172:truth[0]['person']})]
    for name,windows,mapping in cases:
        root=Path('runs')/name
        events=read(root/'events.jsonl')
        reviews=[]
        for event in events:
            row={k:event[k] for k in ('frame','track_id','direction')}
            accepted=event['track_id'] in mapping
            row.update(status='accepted' if accepted else 'uncertain',
                       assistant_review=True,human_reviewed=False,
                       review_basis='Actual source event montage and separate mixed-track frames viewed; original timing windows unchanged')
            if accepted:row['person']=mapping[event['track_id']]
            if name.startswith('green-reverse') and event['track_id']==172:
                row['note']='Olive identity follows the reviewed original canonical box; overlapping brown body remains a limitation.'
            if not accepted:
                row['note']='Mixed olive/brown partial box; IN is not an accepted reversed OUT passage.'
            reviews.append(row)
        with (root/'identity-review-resume4.jsonl').open('x',encoding='utf-8') as stream:
            for row in reviews:stream.write(json.dumps(row)+'\n')
        result=evaluate_windows(events,windows,0,reviews)
        result.update(assistant_review=True,human_reviewed=False,
                      synthetic_transform=True,independent_accuracy_validated=False)
        with (root/'reviewed-evaluation-resume4.json').open('x',encoding='utf-8') as stream:
            json.dump(result,stream,indent=2)
        with (root/'person-direction-review.json').open('x',encoding='utf-8') as stream:
            json.dump(evaluate_person_directions(events,windows,reviews),stream,indent=2)
        print(json.dumps(dict(run=name,matched=result['matched_reviewed_events'],expected=6)))


if __name__=='__main__':main()
