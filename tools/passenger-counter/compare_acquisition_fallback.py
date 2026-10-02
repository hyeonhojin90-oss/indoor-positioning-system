"""Prove preserved full traces before reusing a reviewed primary-door result."""
import argparse,copy,json
from pathlib import Path

def read(path):return [json.loads(x) for x in path.read_text().splitlines()]
def compare(before,after):
    a,b=[json.loads((p/'summary.json').read_text()) for p in [before,after]]
    configs=[copy.deepcopy(s['config']) for s in [a,b]]
    for c in configs:c.pop('experiment_note',None)
    extra=configs[1].pop('door_acquisition_fallback',None)
    rows=[read(p/'tracks.jsonl') for p in [before,after]]
    events=[read(p/'events.jsonl') for p in [before,after]]
    audits=[json.loads((p/'completion-audit.json').read_text()) for p in [before,after]]
    checks=dict(source_hash_equal=a['source_sha256']==b['source_sha256'],
                config_equal_except_acquisition_fallback=configs[0]==configs[1] and isinstance(extra,dict),
                full_input_trace_exact=rows[0]==rows[1],events_exact=events[0]==events[1],
                complete_source=all(r['complete_source'] and r['replay_parity'] for r in audits) and len(rows[0])==a['frames']==b['frames']==len(rows[1]),
                existing_models_equal=all(b['model_sha256'].get(k)==v for k,v in a['model_sha256'].items()))
    return dict(passed=all(checks.values()),checks=checks,reference=str(before),candidate=str(after),
                fallback_calls=b.get('door_acquisition_fallback_calls'),independent_accuracy_validated=False,
                note='Full frozen source traces and events only. Does not prove a different scene or target device.')

def main():
    p=argparse.ArgumentParser();p.add_argument('--reference',type=Path,required=True)
    p.add_argument('--candidate',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    r=compare(a.reference,a.candidate)
    with a.output.open('x') as f:json.dump(r,f,indent=2)
    print(json.dumps(r,indent=2))
    if not r['passed']:raise SystemExit(1)

if __name__=='__main__':main()
