"""Slow reference detector, not claimed as an Orin real-time deployment."""
from pathlib import Path
import cv2
import torch
from PIL import Image


class GroundingDoorDetector:
    def __init__(self, model_id='IDEA-Research/grounding-dino-tiny', prompt='a bus door.',
                 cache_dir='models/hf'):
        from transformers import AutoProcessor, AutoModelForZeroShotObjectDetection
        local=Path(model_id)
        if not local.is_dir():
            root=Path(cache_dir)/('models--'+model_id.replace('/','--'))
            revision=(root/'refs/main').read_text().strip()
            local=root/'snapshots'/revision
        self.processor=AutoProcessor.from_pretrained(str(local),local_files_only=True)
        self.model=AutoModelForZeroShotObjectDetection.from_pretrained(str(local),local_files_only=True).eval()
        self.provenance={'model_id': model_id, 'snapshot_path': str(local),
                         'revision': local.name if local.parent.name == 'snapshots' else None}
        self.prompt=prompt
        self.device='cpu'
        self.stats={'full_calls':0,'crop_calls':0,'edge_candidates_rejected':0}

    def predict(self, frame, device='cpu', conf=.35, search_regions=None, _crop_call=False, **kwargs):
        self.stats['crop_calls' if _crop_call else 'full_calls']+=1
        from ultralytics.engine.results import Results
        target=f'cuda:{device}' if str(device).isdecimal() else str(device)
        if target!=self.device:
            self.model.to(target); self.device=target
        im=Image.fromarray(cv2.cvtColor(frame,cv2.COLOR_BGR2RGB))
        inputs=self.processor(images=im,text=self.prompt,return_tensors='pt').to(target)
        with torch.inference_mode(): out=self.model(**inputs)
        r=self.processor.post_process_grounded_object_detection(out,inputs.input_ids,
                 threshold=conf,text_threshold=.25,target_sizes=[im.size[::-1]])[0]
        rows=[]
        for b,s,label in zip(r['boxes'].cpu().tolist(),r['scores'].cpu().tolist(),r['text_labels']):
            if 'door' in label:rows.append(b+[s,0])
        rows.sort(key=lambda b:b[4],reverse=True)
        for region in search_regions or []:
            x1,y1,x2,y2=region
            h,w=frame.shape[:2]
            if not (0<=x1<x2<=w and 0<=y1<y2<=h and x2-x1>=32 and y2-y1>=32):
                raise ValueError('Invalid automatic search region')
            extra=self.predict(frame[y1:y2,x1:x2],device=device,conf=conf,_crop_call=True)[0]
            for box,score in zip(extra.boxes.xyxy.tolist(),extra.boxes.conf.tolist()):
                # A crop-sized rectangle is often the search window itself,
                # rather than a whole physical door. Do not promote it.
                touching=sum((box[0]<4,box[1]<4,(x2-x1)-box[2]<4,(y2-y1)-box[3]<4))
                if touching>=2:
                    self.stats['edge_candidates_rejected']+=1
                    continue
                rows.append([box[0]+x1,box[1]+y1,box[2]+x1,box[3]+y1,score,0])
        if search_regions:
            from counter import iou
            unique=[]
            for row in sorted(rows,key=lambda b:b[4],reverse=True):
                if not any(iou(row[:4],other[:4])>.65 for other in unique):unique.append(row)
            rows=unique
        return [Results(frame,path='',names={0:'door'},boxes=torch.tensor(rows,dtype=torch.float32).reshape(-1,6))]
