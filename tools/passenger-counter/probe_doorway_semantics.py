"""Diagnostic only: doorway prompts around an automatically acquired door."""
import argparse
import json
import os
from pathlib import Path
os.environ.setdefault('YOLO_CONFIG_DIR',str(Path(__file__).resolve().parent/'runs'/'settings'))
import cv2
import torch
from grounding_detector import GroundingDoorDetector


def main():
    p=argparse.ArgumentParser();p.add_argument('--source',required=True)
    p.add_argument('--run',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--frames',type=int,nargs='+',default=[350,400,440]);a=p.parse_args()
    torch.set_num_threads(2)
    a.output.mkdir(parents=True,exist_ok=False)
    doors=[json.loads(x) for x in (a.run/'doors.jsonl').read_text().splitlines()]
    detector=GroundingDoorDetector('models/hf/models--IDEA-Research--grounding-dino-tiny/snapshots/a2bb814dd30d776dcf7e30523b00659f4f141c71')
    cap=cv2.VideoCapture(a.source);rows=[]
    try:
        for f in a.frames:
            prior=[r for r in doors if r['frame']<=f and r['locked'] is not None]
            if not prior:raise ValueError('No automatic lock before requested frame')
            b=prior[-1]['locked'];bw,bh=b[2]-b[0],b[3]-b[1]
            cap.set(cv2.CAP_PROP_POS_FRAMES,f);ok,frame=cap.read()
            if not ok:raise ValueError('Cannot decode requested frame')
            h,w=frame.shape[:2]
            for margin in [1,2]:
                x1,y1,x2,y2=(max(0,int(b[0]-margin*bw)),max(0,int(b[1]-.3*bh)),
                             min(w,int(b[2]+margin*bw)),min(h,int(b[3]+.3*bh)))
                for prompt in ['a bus door.','a bus doorway.','an open bus doorway.']:
                    detector.prompt=prompt
                    pred=detector.predict(frame[y1:y2,x1:x2],conf=.2)[0]
                    boxes=[[v[0]+x1,v[1]+y1,v[2]+x1,v[3]+y1] for v in pred.boxes.xyxy.tolist()]
                    row={'frame':f,'prompt':prompt,'margin':margin,'region':[x1,y1,x2,y2],
                         'boxes':boxes,'confidence':pred.boxes.conf.tolist()}
                    rows.append(row);print(json.dumps(row),flush=True)
                    (a.output/'detections.json').write_text(json.dumps(rows,indent=2))
    finally:cap.release()


if __name__=='__main__':main()
