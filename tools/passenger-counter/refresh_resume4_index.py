"""Refresh owned recovery metadata from captured evidence; never rerun audits."""
from datetime import datetime, timezone
import hashlib
import json
import argparse
from pathlib import Path


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--test-count',type=int,required=True);args=parser.parse_args()
    if args.test_count < 1:raise ValueError('Use the actually completed whole test count')
    entries = []
    for receipt in sorted(Path('runs').glob('*resume4*.process.json')):
        process = json.loads(receipt.read_text(encoding='utf-8'))
        run = receipt.with_name(receipt.name[:-len('.process.json')])
        entry = dict(run=str(run), process_receipt=str(receipt), phase=process['phase'],
                     process_returncode=process['process_returncode'],
                     full_run_verified=process['full_run_verified'],
                     observed_trace_verified=process.get('observed_trace_verified',False),
                     audit_scope=process.get('audit_scope'),
                     last_reported_frame=process.get('last_reported_frame'),
                     adopted=False, hardware_validated=False)
        summary_path = run / 'summary.json'
        if summary_path.exists():
            summary = json.loads(summary_path.read_text(encoding='utf-8'))
            entry.update(frames=summary['frames'], counts=summary['counts'],
                         source=summary['source'], source_sha256=summary['source_sha256'],
                         active_door_frames=summary['active_door_frames'],
                         summary_sha256=hashlib.sha256(summary_path.read_bytes()).hexdigest())
            evaluation = run / 'reviewed-evaluation-resume4.json'
            if evaluation.exists():
                evaluated = json.loads(evaluation.read_text(encoding='utf-8'))
                entry.update(reviewed_events=evaluated['reviewed_events'],
                             matched_reviewed_events=evaluated['matched_reviewed_events'],
                             whole_ground_truth_complete=False)
            audit = run / 'completion-audit.json'
            if audit.exists():
                captured = json.loads(audit.read_text(encoding='utf-8'))
                entry.update(captured_audit=str(audit),
                             captured_audit_sha256=hashlib.sha256(audit.read_bytes()).hexdigest(),
                             complete_source=captured['complete_source'], replay_parity=captured['replay_parity'])
        entries.append(entry)
    report = dict(updated_at=datetime.now(timezone.utc).isoformat(), live_runs=entries,
                  offline_feature_evidence=[
                      'runs/green-left80-osnet-bound-cache-resume4/summary.json',
                      'runs/osnet-observed-dynamic-onnx-resume4-r2/parity.json',
                      'runs/green-left80-osnet-onnx-immutable-cache-resume4/summary.json',
                      'runs/osnet-complete-feature-replay-parity-resume4.json',
                      'runs/green-left80-osnet-simultaneous-resume4-replay/reviewed-evaluation.json',
                      'runs/osnet-frozen-to-live-parity-resume4.json'],
                  default_preservation='runs/green-default-appearance-isolation-preservation-resume4.json',
                  latest_test_count=args.test_count, target_hardware_validated=False, project_goal_completed=False,
                  usage_stop_policy='Stop only after fresh account 5-hour remaining <=5%; index does not infer usage')
    Path('runs/resume4-current-experiment-index.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(dict(runs=len(entries), completed=sum(x['full_run_verified'] for x in entries),
                         pending=[x['run'] for x in entries if x['phase'] not in ('process_finished','process_failed')],
                         failed=[x['run'] for x in entries if x['process_returncode'] not in (None,0)])))


if __name__ == '__main__':
    main()
