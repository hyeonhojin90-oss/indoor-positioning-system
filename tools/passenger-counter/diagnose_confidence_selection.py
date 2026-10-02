"""Fixed score*passenger-support hypothesis on saved photo predictions only."""
import hashlib,json
from pathlib import Path
from counter import iou
from door_selection import passenger_support
from confidence_door_selection import select_confident_door

def main():
    paths=[Path('runs')/p/'diagnostic.json' for p in [
        'new-door-photos-20261001-r2-probe','new-door-photos-grounding-crops-20261001-r2-probe',
        'extra-door-photos-20261001-r2-current-probe','extra-door-photos-grounding-20261001-r2-probe',
        'new-door-photos-enriched-20261001-r2-probe','extra-door-photos-enriched-20261001-r2-probe']]
    rows=[]
    for path in paths:
        d=json.loads(path.read_text());review=json.loads(Path(d['review']).read_text())
        truths={r['name']:r['target_box'] for r in review['images']}
        for m in d['measurements']:
            entries=[]
            for box in m['gated_candidates']:
                score=max(s for b,s in zip(m['raw_boxes'],m['raw_scores']) if b==box)
                support=passenger_support(box,m['person_boxes'])
                entries.append(dict(box=box,confidence=score,support=support,weighted=score*support))
            eligible=[r for r in entries if r['support']>=.2]
            index=select_confident_door([r['box'] for r in entries],m['person_boxes'],[r['confidence'] for r in entries])
            chosen=entries[index]['box'] if index is not None else None
            truth=truths[m['image']]
            rows.append(dict(diagnostic=str(path),model=m['model'],image=m['image'],
                old_selected_iou=m['selected_iou'],weighted_selected_iou=iou(truth,chosen) if truth and chosen else (0 if truth else None),
                oracle_best_iou=m['oracle_best_iou'],candidates=entries))
    result=dict(rows=rows,formula='model_confidence * passenger_support; original min support .2',
                input_hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
                runtime_changed=False,diagnostic_only=True,ground_truth_used_only_for_evaluation=True,
                photos_previously_inspected=True,independent_video_accuracy_validated=False,jetson_validated=False)
    with Path('runs/confidence-weighted-photo-selection-r2.json').open('x') as f:json.dump(result,f,indent=2)
    for r in rows:print(r['model'],r['image'],r['old_selected_iou'],r['weighted_selected_iou'])

if __name__=='__main__':main()
