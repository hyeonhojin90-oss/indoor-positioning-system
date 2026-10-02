"""Synthetic reacquisition stress: two existing bus scenes separated by no bus."""
import argparse
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np


def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--first',type=Path,required=True)
    p.add_argument('--second',type=Path,required=True)
    p.add_argument('--negative',type=Path,required=True)
    p.add_argument('--gap-seconds',type=float,default=3)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if a.output.exists() or a.output.with_suffix('.source.json').exists() or not 2<=a.gap_seconds<=10:
        raise ValueError('New output and bounded gap required')
    cap=cv2.VideoCapture(str(a.first))
    if not cap.isOpened():raise ValueError('First source cannot open')
    w,h=round(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),round(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps=cap.get(cv2.CAP_PROP_FPS);cap.release()
    a.output.parent.mkdir(parents=True,exist_ok=True)
    writer=cv2.VideoWriter(str(a.output),cv2.VideoWriter_fourcc(*'mp4v'),fps,(w,h))
    if not writer.isOpened():raise ValueError('Output cannot open')
    segments=[];offset=0
    try:
        for role,source in [('first',a.first),('negative_gap',a.negative),('second',a.second)]:
            cap=cv2.VideoCapture(str(source))
            if not cap.isOpened():raise ValueError('Source cannot open')
            source_fps=cap.get(cv2.CAP_PROP_FPS);total=round(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            if role!='negative_gap' and abs(source_fps-fps)>.001:
                raise ValueError('Positive scenes must have the same frame rate')
            count=round(a.gap_seconds*fps) if role=='negative_gap' else total
            used=[];previous=-1;image=None
            try:
                for n in range(count):
                    fid=round(n*source_fps/fps) if role=='negative_gap' else n
                    if fid>=total:raise ValueError('Gap requires more real negative footage')
                    if fid!=previous:
                        if fid!=previous+1:cap.set(cv2.CAP_PROP_POS_FRAMES,fid)
                        ok,image=cap.read()
                        if not ok:raise ValueError('Missing source frame')
                        previous=fid
                    if role=='negative_gap':
                        ih,iw=image.shape[:2];scale=min(w/iw,h/ih)
                        resized=cv2.resize(image,(round(iw*scale),round(ih*scale)))
                        canvas=np.zeros((h,w,3),dtype=np.uint8)
                        x=(w-resized.shape[1])//2;y=(h-resized.shape[0])//2
                        canvas[y:y+resized.shape[0],x:x+resized.shape[1]]=resized
                    else:
                        if image.shape[:2]!=(h,w):raise ValueError('Positive frame size differs')
                        canvas=image
                    writer.write(canvas);used.append(fid)
            finally:cap.release()
            segments.append(dict(role=role,source=str(source),source_sha256=digest(source),
                                 start_frame=offset,frames=count,source_frames=used,
                                 source_fps=source_fps,whole_source=count==total and used==list(range(total))))
            offset+=count
    finally:writer.release()
    cap=cv2.VideoCapture(str(a.output));observed=round(cap.get(cv2.CAP_PROP_FRAME_COUNT));cap.release()
    if observed!=offset:raise ValueError('Output frame count mismatch')
    metadata=dict(output_sha256=digest(a.output),frames=offset,fps=fps,dimensions=[w,h],segments=segments,
                  synthetic=True,independent_footage=False,real_bus_motion_simulated=False,
                  note='Hard cuts between existing full bus videos and a real no-bus excerpt. Negative clip letterboxed and sampled at output fps. mp4v re-encoding may alter detector outputs. State reacquisition stress only; normal video cuts should still be separate runs.')
    a.output.with_suffix('.source.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
    print(json.dumps(dict(frames=offset,segments=[{k:v for k,v in s.items() if k!='source_frames'} for s in segments])))


if __name__=='__main__':main()
