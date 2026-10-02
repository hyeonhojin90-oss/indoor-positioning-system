"""Reject incomplete traces and verify counting replay for an entire source."""
import argparse
import hashlib
import json
from pathlib import Path
import cv2
from replay_counter import replay_rows


def audit(run, config=None):
    summary=json.loads((run/'summary.json').read_text(encoding='utf-8-sig'))
    source=Path(summary['source'])
    digest=hashlib.sha256(source.read_bytes()).hexdigest()
    if digest!=summary['source_sha256']:raise ValueError('Source hash mismatch')
    cap=cv2.VideoCapture(str(source))
    try:
        if not cap.isOpened():raise ValueError('Cannot open source')
        source_frames=int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    finally:cap.release()
    rows=[json.loads(x) for x in (run/'tracks.jsonl').read_text().splitlines()]
    if len(rows)!=source_frames or summary['frames']!=source_frames:
        raise ValueError('Run does not cover the entire source')
    if any(r['frame']!=i for i,r in enumerate(rows)):raise ValueError('Frame sequence mismatch')
    if any(len(r['ids'])!=len(r['boxes']) for r in rows):raise ValueError('ID/box lengths differ')
    if any('door_generation' not in r for r in rows):raise ValueError('Missing exact lock generations')
    cfg=summary.get('config') or config
    if cfg is None:raise ValueError('A saved counting config is required')
    events=summary.get('events')
    if events is None:events=[json.loads(x) for x in (run/'events.jsonl').read_text().splitlines()]
    replay=replay_rows(rows,cfg)
    observation_checked=any('observation_frame' in e for e in events)
    anchor_checked=any('anchor_evidence' in e for e in events)
    keys=lambda items:[(e['frame'],e['track_id'],e['direction'],e['time_s'],e.get('commit_time_s'),
                        e.get('observation_frame') if observation_checked else None,
                        e.get('anchor_evidence') if anchor_checked else None) for e in items]
    if replay['counts']!=summary['counts'] or keys(replay['events'])!=keys(events):
        raise ValueError('Runtime and replay disagree')
    hashes=summary.get('implementation_sha256',summary.get('implementation_hashes',{}))
    drift=[name for name,digest in hashes.items() if hashlib.sha256(Path(name).read_bytes()).hexdigest()!=digest]
    return {'run':str(run),'frames':source_frames,'counts':summary['counts'],
            'events':events,'source_hash_verified':True,'complete_source':True,
            'replay_parity':True,'implementation_drift_since_start':drift,
            'event_observation_frame_checked':observation_checked,'event_anchor_evidence_checked':anchor_checked,
            'implementation_hashes_available':bool(hashes),
            'frozen_door_experiment':summary.get('frozen_door_experiment',False),
            'independent_accuracy_validated':False,'jetson_validated':False}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True)
    p.add_argument('--config',type=Path);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();cfg=json.loads(a.config.read_text(encoding='utf-8-sig')) if a.config else None
    result=audit(a.run,cfg)
    with a.output.open('x',encoding='utf-8') as stream:json.dump(result,stream,indent=2)
    print(json.dumps(result,indent=2))
