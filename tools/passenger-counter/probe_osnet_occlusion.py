"""Frozen-frame diagnostic of person features; track IDs never become runtime truth."""
import argparse,hashlib,json,time
from pathlib import Path
import cv2,numpy as np,torch
from osnet_features import OSNetFeatures

def main():
 p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--frames',type=int,nargs='+',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 s=json.loads((a.run/'summary.json').read_text());source=Path(s['source']);source_hash=hashlib.sha256(source.read_bytes()).hexdigest()
 if source_hash!=s['source_sha256']:raise ValueError('Changed source')
 wanted=set(a.frames);rows=[json.loads(x) for x in (a.run/'tracks.jsonl').read_text().splitlines()];torch.set_num_threads(2);encoder=OSNetFeatures();cap=cv2.VideoCapture(str(source));observations=[];features=[];started=time.perf_counter()
 try:
  for fid in a.frames:
   row=rows[fid];cap.set(cv2.CAP_PROP_POS_FRAMES,fid);ok,im=cap.read()
   if not ok:raise ValueError('Missing source frame')
   vectors=encoder.extract(im,row['raw_boxes'])
   for tid,b,v in zip(row['raw_ids'],row['raw_boxes'],vectors):observations.append(dict(frame=fid,track_id=tid,box=b));features.append(v.tolist())
 finally:cap.release()
 f=np.array(features,dtype=np.float32);report=dict(source_sha256=source_hash,observations=observations,features=features,cosine_similarity=(f@f.T).tolist(),elapsed_seconds=time.perf_counter()-started,model_provenance=encoder.provenance,frozen_frame_diagnostic=True,whole_tracking_validated=False,independent_accuracy_validated=False,hardware_validated=False)
 with a.output.open('x') as stream:json.dump(report,stream,indent=2)
 print(json.dumps(dict(observations=len(observations),elapsed_seconds=report['elapsed_seconds'])))
if __name__=='__main__':main()
