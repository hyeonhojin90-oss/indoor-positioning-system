"""Complete-source observed crop embeddings, separate from detection/counting."""
import argparse,hashlib,json,time
from pathlib import Path
import cv2,torch
from osnet_features import OSNetFeatures
from feature_cache_proof import snapshot_files,require_unchanged

def main():
 p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 audit_path=a.run/'completion-audit.json'
 initial=snapshot_files([a.run/'summary.json',a.run/'tracks.jsonl',audit_path,
    'cache_osnet_observations.py','osnet_features.py','osnet_preprocessing.py','feature_cache_proof.py',
    *[Path('models/osnet-x025-author-resume4')/n for n in ['source.json','osnet.py','model.pth','LICENSE','README.md']]])
 s=json.loads((a.run/'summary.json').read_text());audit=json.loads(audit_path.read_text())
 if not audit['complete_source'] or not audit['replay_parity']:raise ValueError('Require captured complete source/replay audit')
 src=Path(s['source']);source_hash=hashlib.sha256(src.read_bytes()).hexdigest()
 if source_hash!=s['source_sha256']:raise ValueError('Changed source')
 rows=[json.loads(x) for x in (a.run/'tracks.jsonl').read_text().splitlines()]
 if len(rows)!=s['frames'] or [r['frame'] for r in rows]!=list(range(s['frames'])):raise ValueError('Incomplete trace')
 a.output.mkdir(exist_ok=False);torch.set_num_threads(2);encoder=OSNetFeatures();cap=cv2.VideoCapture(str(src));started=time.perf_counter();n=0;boxes=0
 try:
  with (a.output/'features.jsonl').open('x') as stream:
   for row in rows:
    ok,im=cap.read()
    if not ok:raise ValueError('Source decode ended early')
    values=encoder.extract(im,row['raw_boxes']);stream.write(json.dumps(dict(frame=row['frame'],raw_ids=row['raw_ids'],raw_boxes=row['raw_boxes'],features=values.tolist()))+'\n');n+=1;boxes+=len(values)
    if n%60==0:print('features frame',n,flush=True)
  if cap.read()[0]:raise ValueError('Unprocessed source tail')
 finally:cap.release()
 if source_hash!=hashlib.sha256(src.read_bytes()).hexdigest():raise ValueError('Source changed during extraction')
 require_unchanged(initial)
 report=dict(frames=n,observed_boxes=boxes,source_sha256=source_hash,reference_run=str(a.run),reference_tracks_sha256=hashlib.sha256((a.run/'tracks.jsonl').read_bytes()).hexdigest(),reference_summary_sha256=hashlib.sha256((a.run/'summary.json').read_bytes()).hexdigest(),captured_audit_sha256=hashlib.sha256(audit_path.read_bytes()).hexdigest(),features_sha256=hashlib.sha256((a.output/'features.jsonl').read_bytes()).hexdigest(),model_provenance=encoder.provenance,elapsed_seconds=time.perf_counter()-started,full_observed_crops_processed=True,whole_tracking_validated=False,hardware_validated=False,independent_accuracy_validated=False)
 report['input_snapshot_sha256']=initial;report['inputs_unchanged_during_extraction']=True
 (a.output/'summary.json').write_text(json.dumps(report,indent=2));print(json.dumps(dict(frames=n,boxes=boxes,elapsed_seconds=report['elapsed_seconds'])))
if __name__=='__main__':main()
