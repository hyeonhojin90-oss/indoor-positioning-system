"""Freeze source-visual annotations before any extra-photo model predictions."""
import hashlib
import argparse
import json
from pathlib import Path

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',default='portal-review.json')
    a=p.parse_args()
    if Path(a.output).name!=a.output:raise ValueError('Use a filename within the photo directory')
    root=Path('data/commons-door-photos-20261001-r2-extra')
    sources=json.loads(Path('reviews/commons-door-photo-sources-r2-extra.json').read_text())
    targets={
        'waltham-mbta70-20260119.jpg':(None,[], 'Front-on bus body and passengers obscure the entrance boundaries; positive boarding scene, not a negative label.'),
        'apsrtc-boarding-20120712.jpg':(None,[], 'Crowd obscures the lower portal boundary; no precise full-door rectangle asserted, not a negative label.'),
        'nigeria-boarding-20200215.jpg':([715,63,881,492],[[0,72,130,447]], 'Foreground front entrance with visible step; open rear entrance at left is a separate positive door.'),
        'kenya-matatu-20200320.jpg':([462,210,564,758],[], 'Visible narrow passenger entrance with lower step and upper frame; decorative neighboring windows are not entrance labels.'),
    }
    rows=[]
    for s in sources:
        box,others,note=targets[s['name']]
        rows.append(dict(name=s['name'],sha256=hashlib.sha256((root/s['name']).read_bytes()).hexdigest(),
                         target_box=box,status='visible_open_front' if box else 'portal_occluded_unlocalizable',
                         other_visible_doors=[dict(box=b,state='open_rear') for b in others],
                         note=note,recording_group=s['recording_group']))
    review=dict(images=rows,assistant_annotations=True,human_reviewed=False,
                annotations_before_predictions=True,no_passenger_event_labels=True,
                diagnostic_only=True,training_performed=False,
                unknown_geometry_is_not_negative=True)
    with (root/a.output).open('x') as f:json.dump(review,f,indent=2)

if __name__=='__main__':main()
