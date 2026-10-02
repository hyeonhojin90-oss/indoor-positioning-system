"""Compare complete PT/export runs under identical counting/preprocessing settings."""
import argparse
import json
import math
import hashlib
from pathlib import Path
from audit_completed_run import audit
from export_verified_onnx import compare_detections

def same_points(a,b):
    if 'points' not in a and 'points' not in b:return True
    if a['ids']!=b['ids'] or len(a.get('points',[]))!=len(b.get('points',[])):return False
    for x,y in zip(a['points'],b['points']):
        if x is None or y is None:
            if x!=y:return False
        elif len(x)!=2 or len(y)!=2 or not all(math.isfinite(v) for v in x+y) or max(abs(i-j) for i,j in zip(x,y))>1:
            return False
    return True


def compare(reference, exported, box_derivation_provenance=None):
    summaries=[json.loads((run/'summary.json').read_text()) for run in (reference,exported)]
    if box_derivation_provenance is not None:
        proof=json.loads(box_derivation_provenance.read_text())
        assert proof['all_retained_tensors_exactly_equal'] is True and proof['box_parity_passed'] is True
        assert proof['original_source_unchanged'] is True
        assert [s.get('person_task_effective') for s in summaries]==['segment','detect']
        expected=[proof['source_model_sha256'],proof['derived_model_sha256']]
        for s,h in zip(summaries,expected):
            checkpoint=Path(s['config']['person_model']).with_suffix('.pt')
            assert hashlib.sha256(checkpoint.read_bytes()).hexdigest()==h,'Export checkpoint lineage differs'
            model_path=Path(s['config']['person_model'])
            if model_path.suffix=='.onnx':
                export_proof=json.loads((checkpoint.parent/'parity.json').read_text())
                assert export_proof['parity_passed'] and export_proof['checkpoint_sha256']==h
                assert hashlib.sha256(model_path.read_bytes()).hexdigest()==export_proof['onnx_sha256']
            else:assert model_path.suffix=='.pt','Only verified PT/ONNX lineage supported'
    audits=[audit(run) for run in (reference,exported)]
    if summaries[0]['source_sha256']!=summaries[1]['source_sha256']:
        raise ValueError('Different source footage')
    def settings(summary):
        cfg={k:v for k,v in summary['config'].items()
             if k not in ('person_model','door_model','bus_model','pose_aux_model','experiment_note','profile_pipeline')}
        cfg.setdefault('person_rect',True);cfg.setdefault('door_rect',True)
        cfg['person_task']=summary.get('person_task_effective',cfg.get('person_task'))
        if box_derivation_provenance is not None:cfg['person_task']='verified_segment_trained_boxes'
        cfg['separate_bus_model_enabled']=bool(summary['config'].get('bus_model'))
        return cfg
    if settings(summaries[0])!=settings(summaries[1]):
        raise ValueError('Counting or preprocessing settings differ')
    rows=[[json.loads(line) for line in (run/'tracks.jsonl').read_text().splitlines()]
          for run in (reference,exported)]
    if len(rows[0])!=len(rows[1]):raise ValueError('Different complete trace lengths')
    errors=[];positive=0
    boxes=lambda values:[{'box':box,'score':1.,'class_id':0} for box in values]
    for a,b in zip(*rows):
        raw=compare_detections(boxes(a.get('raw_boxes',a['boxes'])),boxes(b.get('raw_boxes',b['boxes'])))
        canonical=compare_detections(boxes(a['boxes']),boxes(b['boxes']))
        door=compare_detections(boxes([a['door']] if a['door'] else []),
                                boxes([b['door']] if b['door'] else []))
        positive+=raw['matched']
        points_match=same_points(a,b)
        if a['frame']!=b['frame'] or a.get('door_generation')!=b.get('door_generation') or not raw['passed'] or not canonical['passed'] or not door['passed'] or not points_match:
            errors.append({'frame':a['frame'],'raw':raw,'canonical':canonical,'door':door,'observed_points_match':points_match})
    keys=lambda events:[(e['frame'],e['track_id'],e['direction'],e['time_s'],e.get('observation_frame'),e.get('commit_time_s'),e.get('anchor_evidence')) for e in events]
    event_parity=keys(audits[0]['events'])==keys(audits[1]['events'])
    return {'frames':audits[0]['frames'],'source_sha256':summaries[0]['source_sha256'],
            'counts_reference':summaries[0]['counts'],'counts_exported':summaries[1]['counts'],
            'exact_event_frame_id_direction_parity':event_parity,
            'event_observation_and_commit_time_parity':event_parity,
            'mismatched_detection_frames':len(errors),'first_mismatches':errors[:10],
            'positive_person_matches':positive,
            'box_derivation_provenance':str(box_derivation_provenance) if box_derivation_provenance else None,
            'passed':not errors and event_parity and positive>0,
            'complete_run_audits':audits,'jetson_validated':False,
            'independent_accuracy_validated':False,
            'note':'Numerical boxes, complete traces and counting parity; shared CPU timing is not a controlled benchmark.'}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--reference',type=Path,required=True)
    p.add_argument('--exported',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--box-derivation-provenance',type=Path)
    a=p.parse_args();result=compare(a.reference,a.exported,a.box_derivation_provenance)
    with a.output.open('x',encoding='utf-8') as stream:json.dump(result,stream,indent=2)
    print(json.dumps({k:result[k] for k in ('passed','frames','mismatched_detection_frames',
                                          'exact_event_frame_id_direction_parity')},indent=2))
    if not result['passed']:raise SystemExit('Complete exported run differs from reference')
