"""Bounded-memory temporal stress clip, derived from a local recording."""
import argparse,hashlib,json,math
from pathlib import Path
import cv2

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists() or a.output.with_suffix('.source.json').exists():raise FileExistsError(a.output)
    cap=cv2.VideoCapture(str(a.source))
    if not cap.isOpened():raise ValueError('Cannot open source')
    count=round(cap.get(cv2.CAP_PROP_FRAME_COUNT));fps=cap.get(cv2.CAP_PROP_FPS)
    width,height=(round(cap.get(k)) for k in (cv2.CAP_PROP_FRAME_WIDTH,cv2.CAP_PROP_FRAME_HEIGHT))
    if not count>0 or not math.isfinite(fps) or fps<=0 or min(width,height)<=0:raise ValueError('Invalid source metadata')
    a.output.parent.mkdir(parents=True,exist_ok=True)
    writer=cv2.VideoWriter(str(a.output),cv2.VideoWriter_fourcc(*'mp4v'),fps,(width,height))
    if not writer.isOpened():cap.release();raise ValueError('Cannot open output writer')
    try:
        for f in range(count-1,-1,-1):
            cap.set(cv2.CAP_PROP_POS_FRAMES,f);ok,frame=cap.read()
            if not ok:raise ValueError(f'Cannot decode frame {f}')
            writer.write(frame)
    finally:cap.release();writer.release()
    verify=cv2.VideoCapture(str(a.output));written=round(verify.get(cv2.CAP_PROP_FRAME_COUNT));verify.release()
    if written!=count:raise ValueError('Incomplete derived clip')
    report=dict(source=str(a.source),source_sha256=hashlib.sha256(a.source.read_bytes()).hexdigest(),
        output_sha256=hashlib.sha256(a.output.read_bytes()).hexdigest(),frames=count,fps=fps,
        transformation='output frame i derives from source frame N-1-i; reencoded, no audio',
        derived_not_independent=True,physical_alighting_validation=False)
    with a.output.with_suffix('.source.json').open('x') as f:json.dump(report,f,indent=2)
    print(json.dumps(report))
