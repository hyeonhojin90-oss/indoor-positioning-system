"""Guard-only full regression; exact events and measured input traces must agree."""
import argparse,json
from pathlib import Path

def main():
    p=argparse.ArgumentParser();p.add_argument('--parent',type=Path,required=True);p.add_argument('--candidate',type=Path,required=True)
    p.add_argument('--change',choices=['exit_guard','confidence_selection'],default='exit_guard');a=p.parse_args()
    def load(root,name):return json.loads((root/name).read_text(encoding='utf-8'))
    old,new=[load(r,'summary.json') for r in (a.parent,a.candidate)]
    audit=load(a.candidate,'completion-audit.json')
    assert audit['complete_source'] and audit['replay_parity'] and not audit['implementation_drift_since_start']
    assert old['source_sha256']==new['source_sha256'] and old['frames']==new['frames']
    def normalized(s):
        c=json.loads(json.dumps(s['config']));c.pop('experiment_note',None)
        if a.change=='exit_guard':c.get('dual_anchor',{}).pop('exit_ankle_guard',None)
        else:c.pop('door_selection_confidence',None)
        return c
    assert normalized(old)==normalized(new),'Only the explicitly named experimental option may differ'
    def rows(root):return [json.loads(x) for x in (root/'tracks.jsonl').read_text().splitlines()]
    before,after=rows(a.parent),rows(a.candidate)
    mismatches=[]
    keys=['frame','ids','boxes','points','door','door_generation']
    for x,y in zip(before,after):
        if any(x.get(k)!=y.get(k) for k in keys):mismatches.append(x['frame'])
    assert len(before)==len(after)==new['frames']
    def events(root):return [json.loads(x) for x in (root/'events.jsonl').read_text().splitlines()]
    same=events(a.parent)==events(a.candidate)
    report=dict(parent=str(a.parent),candidate=str(a.candidate),source_sha256=new['source_sha256'],
        frames=new['frames'],input_trace_mismatch_frames=mismatches,exact_event_parity=same,
        counts_parent=old['counts'],counts_candidate=new['counts'],passed=not mismatches and same,
        independent_alighting_accuracy_validated=False,jetson_validated=False)
    report['allowed_option_change']=a.change
    output='guard-only-regression.json' if a.change=='exit_guard' else 'confidence-only-regression.json'
    with (a.candidate/output).open('x') as f:json.dump(report,f,indent=2)
    print(json.dumps(report))
    if not report['passed']:raise SystemExit('Guard changed regression events or inputs')

if __name__=='__main__':main()
