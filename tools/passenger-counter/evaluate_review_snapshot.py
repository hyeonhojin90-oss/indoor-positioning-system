"""Bind a partial recorded-source review to an actually completed file experiment."""
import argparse
import hashlib
import json
import math
from pathlib import Path
from evaluate_events import evaluate_windows


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text(encoding='utf-8-sig').splitlines() if line.strip()]


def evaluate_snapshot(run,review_metadata,identity_review=None):
    run,review_metadata=Path(run),Path(review_metadata)
    metadata=json.loads(review_metadata.read_text(encoding='utf-8'))
    name=metadata.get('windows_file')
    if not isinstance(name,str) or Path(name).name!=name or '/' in name or '\\' in name:
        raise ValueError('Review windows must be a local snapshot filename')
    windows=review_metadata.parent/name
    if digest(windows)!=metadata['windows_sha256']:raise ValueError('Review windows hash mismatch')
    summary_path=run/'summary.json';events_path=run/'events.jsonl';audit_path=run/'completion-audit.json'
    summary=json.loads(summary_path.read_text(encoding='utf-8'))
    receipt_path=run.with_name(run.name+'.process.json')
    receipt=json.loads(receipt_path.read_text(encoding='utf-8'))
    if receipt.get('phase')!='process_finished' or receipt.get('process_returncode')!=0 or receipt.get('full_run_verified') is not True:
        raise ValueError('Completed full-file process receipt required')
    captured=json.loads(audit_path.read_text(encoding='utf-8'))
    events=rows(events_path)
    if not captured.get('complete_source') or not captured.get('replay_parity') or captured.get('implementation_drift_since_start'):
        raise ValueError('Captured whole-source audit unavailable')
    if captured['counts']!=summary['counts'] or captured['frames']!=summary['frames'] or captured['events']!=events:
        raise ValueError('Current events/summary differ from captured completion audit')
    source=Path(summary['source'])
    if summary.get('source_timing',{}).get('source_kind')!='file':raise ValueError('Recorded file time required')
    expected=metadata['source_sha256']
    before=digest(source)
    if expected!=summary['source_sha256'] or before!=expected:
        raise ValueError('Reviewed source and experiment source differ')
    if not metadata.get('all_source_frames_decoded') or metadata['frames']!=summary['frames']:
        raise ValueError('Reviewed source frame coverage differs')
    fps=metadata.get('fps')
    if isinstance(fps,bool) or not isinstance(fps,(int,float)) or not math.isfinite(fps) or fps<=0 or fps!=summary['source_fps']:
        raise ValueError('Review FPS differs from experiment')
    truth=rows(windows)
    if len(truth)!=metadata['events']:raise ValueError('Review event count mismatch')
    passages=set()
    for event in truth:
        start,end=event['start_frame'],event['end_frame']
        if type(start) is not int or type(end) is not int or not 0<=start<=end<summary['frames']:
            raise ValueError('Review interval outside original source')
        if not math.isclose(event['start_s'],start/fps,abs_tol=1e-9,rel_tol=0) or not math.isclose(event['end_s'],end/fps,abs_tol=1e-9,rel_tol=0):
            raise ValueError('Review frame/time mismatch')
        key=(event['person'],event['direction'],start,end)
        if key in passages:raise ValueError('Duplicate reviewed passage')
        passages.add(key)
    result=evaluate_windows(events,truth,0,rows(identity_review) if identity_review else None)
    if digest(source)!=before or digest(windows)!=metadata['windows_sha256']:
        raise ValueError('Source or review changed during evaluation')
    proof_paths=[review_metadata,windows,summary_path,events_path,audit_path,receipt_path]
    if identity_review:proof_paths.append(Path(identity_review))
    result.update(source_sha256=expected,review_metadata=str(review_metadata),
                  review_kind=metadata.get('reviewer_kind'),source_and_window_binding_verified=True,
                  original_time_windows_preserved=True,whole_ground_truth_complete=False,
                  annotation_before_model_inference_verified=False,jetson_validated=False,
                  proof_sha256={str(path):digest(path) for path in proof_paths})
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--run',type=Path,required=True)
    parser.add_argument('--review-metadata',type=Path,required=True)
    parser.add_argument('--identity-review',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():raise ValueError('Exclusive evaluation output required')
    report=evaluate_snapshot(args.run,args.review_metadata,args.identity_review)
    with args.output.open('x',encoding='utf-8') as stream:json.dump(report,stream,indent=2)
    print(json.dumps({key:report[key] for key in ('reviewed_events','matched_reviewed_events','source_and_window_binding_verified','temporal_matching_only')}))
