"""Inspect real simultaneous auxiliary feet against a verified body trace."""
import argparse,json,os,hashlib
from pathlib import Path
from person_anchor import measured_points
from associate_pose import associated_keypoints
from runtime_threads import configure_model_threads

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--model',type=Path,required=True)
    p.add_argument('--frames',nargs='+',type=int,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    os.environ.setdefault('YOLO_CONFIG_DIR',str(Path.cwd()/'runs/settings'))
    import cv2
    from ultralytics import YOLO
    s=json.loads((a.run/'summary.json').read_text());rows=[json.loads(x) for x in (a.run/'tracks.jsonl').read_text().splitlines()]
    if hashlib.sha256(Path(s['source']).read_bytes()).hexdigest()!=s['source_sha256']:raise ValueError('Source differs')
    model=YOLO(str(a.model),task='pose');configure_model_threads(model,2);cap=cv2.VideoCapture(s['source']);output=[]
    try:
        for index in a.frames:
            cap.set(cv2.CAP_PROP_POS_FRAMES,index);ok,frame=cap.read()
            if not ok:raise ValueError('Undecodable frame')
            pose=model.predict(frame,imgsz=s['config']['person_imgsz'],conf=.1,verbose=False)[0]
            row=rows[index];raw=list(zip(row['raw_ids'],row['raw_boxes']))
            matches,proof=associated_keypoints(raw,pose.boxes.xyxy.tolist(),pose.keypoints.data.tolist())
            points=measured_points(list(zip(row['ids'],row['boxes'])),raw,matches,s['config'])
            output.append(dict(row,points=points,raw_keypoints=matches,pose_association=proof))
            print(index,[(tid,point) for tid,point in zip(row['ids'],points) if tid==2])
    finally:cap.release()
    a.output.mkdir(parents=True,exist_ok=False)
    (a.output/'tracks.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in output))
    (a.output/'probe.json').write_text(json.dumps(dict(model=str(a.model),model_sha256=hashlib.sha256(a.model.read_bytes()).hexdigest(),source_sha256=s['source_sha256'],frames=a.frames,not_complete_run=True),indent=2))
