"""Derived diagnostics, not new independent scenes or training data."""
import cv2
import numpy as np
from pathlib import Path
import json


def main():
    dest=Path('data/regression');dest.mkdir(exist_ok=True)
    cap=cv2.VideoCapture('data/bus-3132290.mp4');fps=cap.get(5);frames=[]
    while True:
        ok,im=cap.read()
        if not ok:break
        frames.append(im)
    cap.release();h,w=frames[0].shape[:2]
    for name,indices,shift in [('shift-left',range(len(frames)),-320),
                               ('reverse',reversed(range(len(frames))),0),
                               ('stationary', [0]*60,0),
                               ('bus-absence-reentry', list(range(35))+[-1]*35+list(range(35)),0)]:
        path=dest/f'{name}.mp4'
        if path.exists():raise FileExistsError(path)
        writer=cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*'mp4v'),fps,(w,h))
        if not writer.isOpened():raise RuntimeError('writer')
        for i in indices:
            frame=np.zeros((h,w,3),dtype=np.uint8) if i < 0 else frames[i].copy()
            if shift:frame=cv2.warpAffine(frame,np.float32([[1,0,shift],[0,1,0]]),(w,h),borderValue=(114,114,114))
            writer.write(frame)
        writer.release()
    (dest/'README.json').write_text(json.dumps({'source':'bus-3132290.mp4','derived_not_independent':True,
        'expected':{'shift-left':{'in':1,'out':0},'reverse':{'in':0,'out':1},
                    'stationary':{'in':0,'out':0},'bus-absence-reentry':{'in':2,'out':0}},
        'note':'Reverse and reentry are artificial trajectory checks, not real alighting or second-bus evidence.'},indent=2),encoding='utf-8')


if __name__=='__main__':main()
