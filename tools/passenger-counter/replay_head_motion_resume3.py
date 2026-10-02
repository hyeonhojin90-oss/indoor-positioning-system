"""Source-verified frozen detections + head flow experiment, not new detector proof."""
import argparse,hashlib,json,copy,time
from pathlib import Path
import cv2
from motion_head_bridge import MotionHeadBridge
from person_anchor import measured_points
from replay_counter import replay_rows

def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    s=json.loads((a.run/'summary.json').read_text());rows=[json.loads(x) for x in (a.run/'tracks.jsonl').read_text().splitlines()]
    assert hashlib.sha256(Path(s['source']).read_bytes()).hexdigest()==s['source_sha256']
    audit=json.loads((a.run/'completion-audit.json').read_text());assert audit['complete_source'] and audit['replay_parity']
    cv2.setNumThreads(2);cap=cv2.VideoCapture(s['source']);assert cap.isOpened()
    assert int(cap.get(cv2.CAP_PROP_FRAME_COUNT))==len(rows)==s['frames']
    a.output.mkdir(exist_ok=False);bridge=MotionHeadBridge();generation=None;out=[];links=[];start=time.perf_counter()
    implementation={n:hashlib.sha256(Path(n).read_bytes()).hexdigest() for n in ['motion_head_bridge.py','replay_head_motion_resume3.py','person_anchor.py','multi_anchor_counter.py','exit_evidence_guard.py','replay_counter.py']}
    try:
        with (a.output/'tracks.jsonl').open('x') as stream:
            for row in rows:
                ok,frame=cap.read();assert ok
                if row['door'] is None or row['door_generation']!=generation:bridge.reset()
                generation=row['door_generation'];raw=list(zip(row['raw_ids'],row['raw_boxes']))
                before=len(bridge.audit)
                pairs=bridge.update(frame,raw,row['time_s']) if row['door'] is not None else raw
                links.extend(dict(e,frame=row['frame'],door_generation=generation) for e in bridge.audit[before:])
                poses={int(k):v for k,v in row['raw_keypoints'].items()}
                pts=measured_points(pairs,raw,poses,s['config'])
                r=dict(row,ids=[i for i,_ in pairs],boxes=[b for _,b in pairs],points=pts)
                out.append(r);stream.write(json.dumps(r)+'\n')
        cfg=copy.deepcopy(s['config']);cfg['track_bridge']['enabled']=False
        result=replay_rows(out,cfg)
        report=dict(reference_run=str(a.run),source=s['source'],source_sha256=s['source_sha256'],
                    frames=len(rows),counts=result['counts'],events=result['events'],head_links=links,
                    elapsed_s=time.perf_counter()-start,config=cfg,frozen_detections=True,
                    implementation_sha256=implementation,
                    full_detector_rerun=False,independent_accuracy_validated=False,jetson_validated=False,
                    note='Replaces nested box aliases with short-gap unique head optical flow; original raw measured detections/poses/door generations retained. No threshold/window tuning.')
        with (a.output/'replay.json').open('x') as f:json.dump(report,f,indent=2)
        print(json.dumps(dict(frames=len(rows),counts=result['counts'],head_links=len(links))))
    finally:cap.release()

if __name__=='__main__':main()
