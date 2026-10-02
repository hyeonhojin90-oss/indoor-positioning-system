"""Separate non-bus setup and static public-photo component checks, not field GT."""
import hashlib
import json
from pathlib import Path


def main():
    import cv2
    config=json.loads(Path('configs/bus-portal-measured-strict-exit-resume3.json').read_text(encoding='utf-8'))
    for name in ('bus_gate','bus_visual_fallback','bus_model','bus_detector','door_acquisition_fallback','door_primary_model','cascade'):
        config.pop(name,None)
    config.update(door_model='models/doors-v8s.pt',imgsz=640,door_selection={'enabled':False},
                  experiment_note='Classroom camera setup candidate only: generic door, no bus gate or passenger-support acquisition. Existing measured-person/pose counting unchanged. Direction/geometry require installation review; closed doors and reflections are not verified traversable apertures.')
    path=Path('configs/classroom-door-smoke-resume4.json')
    with path.open('x',encoding='utf-8') as stream:json.dump(config,stream,indent=2)
    root=Path('data/classroom-static-smoke-resume4');root.mkdir(exist_ok=False)
    for name,filename in [('door','IMG_20190624_105116.jpg'),('no-door','IMG_20190624_104925.jpg')]:
        source=Path('data/public-doors-date-split/images')/filename
        before=hashlib.sha256(source.read_bytes()).hexdigest();image=cv2.imread(str(source))
        if image is None:raise ValueError('Cannot decode public photo')
        height,width=image.shape[:2];target=root/(name+'.mp4')
        writer=cv2.VideoWriter(str(target),cv2.VideoWriter_fourcc(*'mp4v'),30.,(width,height))
        if not writer.isOpened():raise ValueError('Cannot create component clip')
        try:
            for _ in range(15):writer.write(image)
        finally:writer.release()
        if before!=hashlib.sha256(source.read_bytes()).hexdigest():raise ValueError('Public source changed')
        proof=dict(source=str(source),source_sha256=before,source_split='train',frames=15,fps=30.,
                   derivative_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
                   transformation='Repeat same original photo15 times; mp4v encoding; no crop, overlays, or spatial adjustment',
                   source_dataset='https://www.kaggle.com/datasets/sayedmohamed1/doors-detection',license='CC BY 4.0',
                   component_smoke_only=True,actual_classroom_recording=False,independent_accuracy_validated=False,
                   expected_stationary_counts={'in':0,'out':0},
                   limitations='Photo contains reflections; generic closed-door detection is not proof of an open passage or real boarding.')
        with target.with_suffix('.source.json').open('x',encoding='utf-8') as stream:json.dump(proof,stream,indent=2)
    print('Prepared separate classroom configuration and two static component clips')


if __name__=='__main__':main()
