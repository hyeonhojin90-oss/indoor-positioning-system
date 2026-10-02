"""Index completed experiments with actual source/model hashes and fixed review limits."""
import hashlib,json
from pathlib import Path
from audit_completed_run import audit

groups={
    'box_derivative':[n+'-segment-trained-box' for n in ['green','green-right80','green-left80','green-reverse','stationary','people-negative']],
    'medium_person':[n+'-medium-person-exit-guard' for n in ['green','green-right80','green-left80']],
    'photo_enriched':['green-photo-enriched-confidence','green-photo-enriched-unweighted','green-left80-photo-enriched-confidence','green-right80-photo-enriched-confidence'],
    'baseline_confidence':['green-baseline-confidence'],
}
hash_cache={};rows=[]
for group,names in groups.items():
    for name in names:
        root=Path('runs')/(name+'-20261001-r2-full')
        summary=json.loads((root/'summary.json').read_text())
        snapshot=json.loads((root/'completion-audit.json').read_text())
        assert snapshot['complete_source'] and snapshot['replay_parity'] and not snapshot['implementation_drift_since_start']
        current=audit(root)
        assert current['complete_source'] and current['replay_parity']
        for key,expected in summary['model_sha256'].items():
            path=Path(summary['config'][key])
            if path not in hash_cache:hash_cache[path]=hashlib.sha256(path.read_bytes()).hexdigest()
            assert hash_cache[path]==expected,f'Model changed: {path}'
        review=root/'identity-evaluation.json';matched=None;reviewed=None
        if review.exists():
            r=json.loads(review.read_text());matched=r['matched_reviewed_events'];reviewed=r['reviewed_events']
        parity=root/'box-derivation-parity.json';parity_pass=None
        if parity.exists():
            p=json.loads(parity.read_text());assert p['source_sha256']==summary['source_sha256'] and p['frames']==summary['frames'];parity_pass=p['passed']
            assert parity_pass
        rows.append(dict(group=group,run=str(root),frames=summary['frames'],counts=summary['counts'],
                         matched_fixed_person_time_windows=matched,reviewed_windows=reviewed,
                         source_sha256=summary['source_sha256'],saved_completion_drift=[],
                         current_implementation_drift=current['implementation_drift_since_start'],
                         model_hashes_verified=True,complete_source=True,replay_parity=True,
                         box_derivation_full_parity=parity_pass,independent_accuracy_validated=False,jetson_validated=False))
output=Path('runs/verified-resume2-experiment-index-r2.json')
with output.open('x') as f:json.dump(dict(experiments=rows,default_candidate_unchanged=True,
    human_reviewed=False,note='Fixed partial assistant-reviewed windows; no overall precision/100% accuracy claim. All compared scene shifts/reverse/stationary sources remain development derivatives.'),f,indent=2)
for r in rows:print(r['run'],r['counts'],r['matched_fixed_person_time_windows'],r['reviewed_windows'])
