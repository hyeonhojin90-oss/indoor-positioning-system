"""Save concrete completed/pending experiment evidence for interruption recovery."""
import json,hashlib,datetime
from pathlib import Path
NAMES=['green-left80-measured-rtdetr-profiled-resume3-full','green-left80-measured-rtdetr-nms-profiled-resume3-full','green-default-after-rtdetr-nms-resume3-full','green-left80-measured-long-buffer-resume3-full','door-generic-small-transfer-resume3','pink-generic-door-transfer-resume3-full']
def collect():
 rows=[]
 for name in NAMES:
  root=Path('runs')/name;p=root.with_name(root.name+'.process.json');state=json.loads(p.read_text()) if p.exists() else {}
  summary=root/'summary.json';s=json.loads(summary.read_text()) if summary.exists() else {}
  audit=root/'completion-audit.json';a=json.loads(audit.read_text()) if audit.exists() else {}
  evaluation=root/'reviewed-evaluation.json';e=json.loads(evaluation.read_text()) if evaluation.exists() else {}
  rows.append(dict(name=name,phase=state.get('phase'),actual_exit=state.get('process_returncode',state.get('actual_returncode')),full_run_verified=state.get('full_run_verified',False),last_reported_frame=state.get('last_reported_frame'),finished_at=state.get('finished_at'),frames=s.get('frames'),counts=s.get('counts'),source_sha256=s.get('source_sha256'),summary_sha256=hashlib.sha256(summary.read_bytes()).hexdigest() if summary.exists() else None,captured_completion_audit_sha256=hashlib.sha256(audit.read_bytes()).hexdigest() if audit.exists() else None,captured_implementation_drift=a.get('implementation_drift_since_start'),reviewed_matches=e.get('matched_reviewed_events'),reviewed_events=e.get('reviewed_events'),test_metrics_saved=state.get('test_metrics_saved',False),adopted=False))
 return dict(updated_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),experiments=rows,hardware_validated=False,independent_accuracy_validated=False,note='Captured completed audits refer to code at that execution. Pending phase is not completion, PID liveness, or a resumable tracker state. Partial logs are preserved; new runs require exclusive output folders.')
if __name__=='__main__':
 report=collect();Path('runs/resume3-current-experiment-index.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
