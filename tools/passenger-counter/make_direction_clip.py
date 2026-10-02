"""Bounded-memory artificial direction test; never independent footage."""
import argparse,hashlib,json
from pathlib import Path
import cv2

def main():
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists():raise FileExistsError(a.output)
    cap=cv2.VideoCapture(str(a.source))
    if not cap.isOpened():raise ValueError('Cannot open input')
    frames=int(cap.get(cv2.CAP_PROP_FRAME_COUNT));fps=cap.get(cv2.CAP_PROP_FPS)
    w,h=int(cap.get(3)),int(cap.get(4));a.output.parent.mkdir(exist_ok=True,parents=True)
    writer=cv2.VideoWriter(str(a.output),cv2.VideoWriter_fourcc(*'mp4v'),fps,(w,h))
    if not writer.isOpened():raise ValueError('Cannot open output')
    try:
        for index in reversed(range(frames)):
            cap.set(cv2.CAP_PROP_POS_FRAMES,index);ok,im=cap.read()
            if not ok:raise ValueError(f'Undecodable frame {index}')
            writer.write(im)
    finally:cap.release();writer.release()
    info=dict(source=str(a.source),source_sha256=hashlib.sha256(a.source.read_bytes()).hexdigest(),
        output_sha256=hashlib.sha256(a.output.read_bytes()).hexdigest(),frames=frames,
        fps=fps,derived_not_independent=True,frame_map='output frame = frames-1-input frame',
        expected_reviewed_directions='Original reviewed IN become OUT and OUT become IN; full-scene truth unavailable.')
    with a.output.with_suffix('.json').open('x') as f:json.dump(info,f,indent=2)
    print(json.dumps(info))
if __name__=='__main__':main()
