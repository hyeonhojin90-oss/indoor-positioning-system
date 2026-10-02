"""Capture the actual original failure and isolated fixed stream-drill evidence."""
import hashlib
import json
from pathlib import Path


def read(path):return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]


def main():
    original=Path('runs/stream-input-original-resume4-drill');fixed=Path('runs/stream-input-fix-candidate-resume4-drill')
    receipts=[root.with_name(root.name+'.drill-process.json') for root in (original,fixed)]
    before,after=[json.loads(path.read_text(encoding='utf-8')) for path in receipts]
    audit=json.loads((fixed/'observed-trace-audit.json').read_text())
    summary=json.loads((fixed/'summary.json').read_text())
    assert before['process_returncode']==1 and after['process_returncode']==0
    assert before['original_source_sha256']==after['original_source_sha256']
    assert before['original_source_unchanged'] and after['original_source_unchanged']
    assert not (original/'summary.json').exists() and summary['source_sha256'] is None
    assert audit['observed_trace_verified'] and summary['runtime_input_evidence']['local_inputs_unchanged_verified']
    a,b=read(original/'tracks.jsonl'),read(fixed/'tracks.jsonl')
    assert len(a)==len(b)==8
    fields=['raw_ids','raw_boxes','ids','boxes','points','raw_keypoints']
    differences=[i for i,(x,y) in enumerate(zip(a,b)) if any(x.get(k)!=y.get(k) for k in fields)]
    paths=receipts+[original.with_name(original.name+'.drill.log'),fixed/'summary.json',fixed/'observed-trace-audit.json',
                    original/'tracks.jsonl',fixed/'tracks.jsonl',Path('runs/stream-input-fix-candidate-resume4-runtime/run.py')]
    report=dict(original_failed_at_stream_path_hash=True,fixed_observed_trace_verified=True,
                frames=8,actual_camera_accessed=False,actual_network_stream_connected=False,
                fixed_local_inputs_unchanged_verified=True,local_source_unchanged=True,
                compared_person_fields=fields,person_fields_equal=not differences,mismatched_frames=differences,
                original_summary_saved=False,fixed_summary_saved=True,full_run_verified=False,
                source_clock_times_expected_to_differ=True,root_runtime_fix_applied=False,
                proof_sha256={str(path):hashlib.sha256(path.read_bytes()).hexdigest() for path in paths})
    path=Path('runs/stream-input-fix-proof-resume4.json')
    with path.open('x',encoding='utf-8') as stream:json.dump(report,stream,indent=2)
    print(json.dumps({key:report[key] for key in ('frames','original_failed_at_stream_path_hash','fixed_observed_trace_verified','person_fields_equal','root_runtime_fix_applied')}))


if __name__=='__main__':main()
