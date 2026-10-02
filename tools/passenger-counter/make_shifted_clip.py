"""Translation stress test of a whole scene, not a new bus/camera validation."""
import argparse,hashlib,json
from pathlib import Path
import cv2,numpy as np

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--dx',type=int,required=True);a=p.parse_args()
    if a.output.exists():raise FileExistsError(a.output)
    cap=cv2.VideoCapture(str(a.source));w,h=int(cap.get(3)),int(cap.get(4));fps=cap.get(5)
    if not cap.isOpened() or abs(a.dx)>=w/2:raise ValueError('Invalid source or excessive displacement')
    writer=cv2.VideoWriter(str(a.output),cv2.VideoWriter_fourcc(*'mp4v'),fps,(w,h));n=0
    if not writer.isOpened():raise ValueError('Cannot write video')
    try:
        while True:
            ok,frame=cap.read()
            if not ok:break
            writer.write(cv2.warpAffine(frame,np.float32([[1,0,a.dx],[0,1,0]]),(w,h),borderValue=(114,114,114)));n+=1
    finally:cap.release();writer.release()
    info=dict(source=str(a.source),source_sha256=hashlib.sha256(a.source.read_bytes()).hexdigest(),
        output_sha256=hashlib.sha256(a.output.read_bytes()).hexdigest(),frames=n,fps=fps,dx=a.dx,
        derived_not_independent=True,note='Whole-scene translation with edge clipping/padding; does not simulate an independently moving bus.')
    with a.output.with_suffix('.source.json').open('x') as f:json.dump(info,f,indent=2)
    print(json.dumps(info))
