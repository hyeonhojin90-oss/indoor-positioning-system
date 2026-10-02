"""Pair simultaneous detector logs for a development-only auxiliary pose replay."""
import argparse,json,hashlib
from pathlib import Path
from associate_pose import associated_keypoints
from person_anchor import measured_points
from replay_counter import replay_rows

def pair_rows(body,pose,cfg):
    if len(body)!=len(pose):raise ValueError('Frame counts differ')
    for index,(b,p) in enumerate(zip(body,pose)):
        if b['frame']!=index:raise ValueError('Incomplete or repeated frame sequence')
        if b['frame']!=p['frame'] or abs(b['time_s']-p['time_s'])>1e-6:
            raise ValueError('Frames are not simultaneous')
        poses=p.get('raw_keypoints',{})
        boxes=[];keypoints=[]
        for tid,box in zip(p['raw_ids'],p['raw_boxes']):
            kp=poses.get(str(tid),poses.get(tid))
            if kp is not None:boxes.append(box);keypoints.append(kp)
        raw=list(zip(b['raw_ids'],b['raw_boxes']))
        matches,proof=associated_keypoints(raw,boxes,keypoints)
        yield dict(b,points=measured_points(list(zip(b['ids'],b['boxes'])),raw,matches,cfg),pose_association=proof)

def main():
    a=argparse.ArgumentParser();a.add_argument('--body',type=Path,required=True)
    a.add_argument('--pose',type=Path,required=True);a.add_argument('--output',type=Path,required=True)
    a.add_argument('--foot-choice',choices=['leading','trailing'],default='leading')
    a.add_argument('--defer-ankle',action='store_true')
    args=a.parse_args()
    summaries=[json.loads((p/'summary.json').read_text()) for p in (args.body,args.pose)]
    if summaries[0]['source_sha256']!=summaries[1]['source_sha256']:raise ValueError('Source differs')
    if hashlib.sha256(Path(summaries[0]['source']).read_bytes()).hexdigest()!=summaries[0]['source_sha256']:
        raise ValueError('Original source hash mismatch')
    logs=[[json.loads(x) for x in (p/'tracks.jsonl').read_text().splitlines()] for p in (args.body,args.pose)]
    for rows,s in zip(logs,summaries):
        if len(rows)!=s['frames']:raise ValueError('Incomplete log')
    cfg=dict(summaries[0]['config'],person_anchor_kind='pose_dual',pose_anchor=dict(ankle_conf=.5,min_visible=2,foot_choice=args.foot_choice),dual_anchor=dict(require_body_transition=True,defer_ankle=args.defer_ankle))
    rows=list(pair_rows(*logs,cfg));args.output.mkdir(parents=True,exist_ok=False)
    (args.output/'tracks.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
    result=replay_rows(rows,cfg)
    result.update(config=cfg,source_sha256=summaries[0]['source_sha256'],development_only=True,full_live_inference=False,
        references={str(p):hashlib.sha256((p/'summary.json').read_bytes()).hexdigest() for p in (args.body,args.pose)})
    (args.output/'replay.json').write_text(json.dumps(result,indent=2))
    print(json.dumps({k:result[k] for k in ('frames','counts','events')}))
if __name__=='__main__':main()
