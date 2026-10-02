"""Frozen-event diagnostic only; runtime counter state is not modified."""
import argparse
import hashlib
import json
from pathlib import Path
from exit_evidence_guard import ExitEvidenceGuard
from replay_counter import replay_rows

def main():
    p=argparse.ArgumentParser();p.add_argument('--runs',nargs='+',required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    report=[]
    for filename in a.runs:
        root=Path(filename);s=json.loads((root/'summary.json').read_text())
        assert s['config'].get('person_anchor_kind')=='pose_dual'
        assert hashlib.sha256(Path(s['source']).read_bytes()).hexdigest()==s['source_sha256']
        rows=[json.loads(x) for x in (root/'tracks.jsonl').read_text().splitlines()]
        before=replay_rows(rows,s['config']);assert before['counts']==s['counts']
        c=s['config']['counting']
        guard=ExitEvidenceGuard(**{k:v for k,v in c.items() if k in
                  ('low','high','confirm','max_gap','transverse_low','transverse_high','transverse_band')})
        evidence={};generation=None
        for row in rows:
            if row['door'] is None or generation!=row['door_generation']:guard.reset()
            generation=row['door_generation']
            if row['door'] is None:continue
            for tid,foot in zip(row['ids'],row['points']):
                evidence[(row['frame'],tid)]=guard.observe(tid,foot,row['door'],row['time_s'])
        events=[json.loads(x) for x in (root/'events.jsonl').read_text().splitlines()]
        kept=[];rejected=[]
        for e in events:
            proof=evidence.get((e['observation_frame'],e['track_id']))
            if e['direction']=='out' and proof and not proof['allow_exit']:
                rejected.append(dict(event=e,evidence=proof))
            else:kept.append(e)
        counts={direction:sum(e['direction']==direction for e in kept) for direction in ['in','out']}
        report.append(dict(run=filename,baseline=s['counts'],filtered_counts=counts,
                           rejected=rejected,events=kept))
        print(filename,s['counts'],counts,'rejected',[(r['event']['frame'],r['event']['track_id']) for r in rejected])
    with a.output.open('x') as f:
        json.dump(dict(runs=report,frozen_event_diagnostic_only=True,
                       counter_feedback_unchanged=True,requires_full_runtime_comparison=True,
                       independent_accuracy_validated=False),f,indent=2)

if __name__=='__main__':main()
