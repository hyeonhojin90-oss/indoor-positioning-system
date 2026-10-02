"""Pinned author OSNet feature adapter; optional diagnostic, no tracker side effects."""
import hashlib,importlib.util,json
from pathlib import Path
import numpy as np
import cv2
import torch
from osnet_preprocessing import observed_crops,transform

class OSNetFeatures:
    def __init__(self,root='models/osnet-x025-author-resume4',device='cpu'):
        root=Path(root);proof=json.loads((root/'source.json').read_text())
        if not proof.get('download_complete'):raise ValueError('Incomplete author assets')
        for row in proof['files']:
            p=root/row['path']
            if p.stat().st_size!=row['bytes'] or hashlib.sha256(p.read_bytes()).hexdigest()!=row['sha256']:raise ValueError('Changed author assets')
        spec=importlib.util.spec_from_file_location('pinned_author_osnet',root/'osnet.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        state=torch.load(root/'model.pth',map_location='cpu',weights_only=True)
        self.model=module.osnet_x0_25(num_classes=state['classifier.weight'].shape[0],pretrained=False)
        self.model.load_state_dict(state,strict=True);self.model.eval().to(device);self.device=device
        self.transform=transform()
        self.provenance=proof
    def prepare(self,frame,boxes):
        """Shared actual-crop preprocessing for native and exported inference."""
        return observed_crops(frame,boxes,self.transform)
    def extract(self,frame,boxes):
        inputs=self.prepare(frame,boxes)
        if not len(inputs):return np.empty((0,512),np.float32)
        with torch.inference_mode():
            out=self.model(inputs.to(self.device));out=torch.nn.functional.normalize(out,dim=1)
        if not bool(torch.isfinite(out).all()):raise ValueError('Nonfinite appearance descriptor')
        return out.cpu().numpy()
