"""Transfer assistant identities only after complete numerical export parity."""
import argparse,json
from pathlib import Path
from evaluate_events import evaluate_windows

def read(p):return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]

def main():
    p=argparse.ArgumentParser();p.add_argument('--reference',type=Path,required=True);p.add_argument('--run',type=Path,required=True)
    p.add_argument('--comparison',choices=['pt-comparison.json','box-derivation-parity.json'],default='pt-comparison.json');a=p.parse_args()
    comparison=json.loads((a.run/a.comparison).read_text())
    assert comparison['passed'] and comparison['mismatched_detection_frames']==0
    audits=comparison['complete_run_audits']
    assert Path(audits[0]['run'])==a.reference and Path(audits[1]['run'])==a.run
    summary=json.loads((a.run/'summary.json').read_text())
    assert comparison['source_sha256']==summary['source_sha256'] and comparison['frames']==summary['frames']
    def event_keys(root):return [(e['frame'],e['track_id'],e['direction'],e['time_s'],e.get('observation_frame'),e.get('commit_time_s'),e.get('anchor_evidence')) for e in read(root/'events.jsonl')]
    assert event_keys(a.reference)==event_keys(a.run)
    reviews=read(a.reference/'identity-review.jsonl')
    for r in reviews:r['review_provenance']=dict(reference=str(a.reference),method='Complete export numerical box/point correspondence, identical ID/direction/observation/commit event; reused assistant identity, not independent human review.')
    with (a.run/'identity-review.jsonl').open('x') as f:
        for r in reviews:f.write(json.dumps(r)+'\n')
    result=evaluate_windows(read(a.run/'events.jsonl'),read(Path('reviews/green-development-windows.jsonl')),0,reviews)
    result.update(assistant_review=True,human_reviewed=False,verified_complete_export_comparison=True)
    with (a.run/'identity-evaluation.json').open('x') as f:json.dump(result,f,indent=2)
    print(result['matched_reviewed_events'])

if __name__=='__main__':main()
