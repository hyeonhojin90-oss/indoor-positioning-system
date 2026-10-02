import hashlib,json
from pathlib import Path
from unittest.mock import patch
from experimental_ankle_body_band import ApproachBandAnkleCounter
from replay_counter import replay_rows

def main():
    names=['green-person-seg-exit-guard-onnx-box-render','green-right80-person-seg-exit-guard-onnx-box-render',
        'green-left80-person-seg-exit-guard-onnx-box-render','green-photo-enriched-confidence',
        'green-right80-photo-enriched-confidence','green-left80-photo-enriched-confidence']
    report=[]
    for name in names:
        root=Path('runs')/(name+'-20261001-r2-full');s=json.loads((root/'summary.json').read_text())
        rows=[json.loads(x) for x in (root/'tracks.jsonl').read_text().splitlines()]
        assert len(rows)==s['frames'] and hashlib.sha256(Path(s['source']).read_bytes()).hexdigest()==s['source_sha256']
        baseline=replay_rows(rows,s['config'])
        events=[json.loads(x) for x in (root/'events.jsonl').read_text().splitlines()]
        keys=lambda items:[tuple(e.get(k) for k in ('frame','track_id','direction','time_s','observation_frame','commit_time_s','anchor_evidence')) for e in items]
        assert baseline['counts']==s['counts'] and keys(baseline['events'])==keys(events)
        with patch('replay_counter.DualAnchorCounter',ApproachBandAnkleCounter):candidate=replay_rows(rows,s['config'])
        report.append(dict(run=str(root),baseline=baseline,candidate=candidate,source_sha256=s['source_sha256']))
        print(name,baseline['counts'],candidate['counts'],[(e['frame'],e['track_id'],e['direction']) for e in candidate['events']])
    result=dict(runs=report,runtime_changed=False,additional_pose_inference_not_performed=True,
        full_runtime_accuracy_validated=False,jetson_validated=False,
        hypothesis='Prior body outside plus measured feet: allow body within existing pose approach band [0,1.2], retaining lateral inset and deferred ankle commitment.')
    with Path('runs/approach-ankle-band-frozen-replay-r2.json').open('x') as f:json.dump(result,f,indent=2)

if __name__=='__main__':main()
