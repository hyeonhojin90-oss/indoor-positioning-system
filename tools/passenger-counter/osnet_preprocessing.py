"""Actual observed BGR crops to the author's RGB 256x128 input contract."""
import cv2
import numpy as np
import torch
from PIL import Image
from torchvision import transforms


def transform():
    return transforms.Compose([transforms.Resize((256, 128)), transforms.ToTensor(),
                               transforms.Normalize([.485, .456, .406], [.229, .224, .225])])


def observed_crops(frame, boxes, preprocessing=None):
    if frame.ndim != 3 or frame.shape[2] != 3 or frame.dtype != np.uint8:
        raise ValueError('Require actual uint8 BGR image')
    height, width = frame.shape[:2]
    preprocessing = preprocessing or transform()
    images = []
    for box in boxes:
        if len(box) != 4 or not np.isfinite(box).all():
            raise ValueError('Invalid observed crop')
        x1, y1, x2, y2 = [round(float(v)) for v in box]
        x1, y1, x2, y2 = max(0, x1), max(0, y1), min(width, x2), min(height, y2)
        if x2 - x1 < 4 or y2 - y1 < 4:
            raise ValueError('Observed crop too small or outside image')
        crop = cv2.cvtColor(frame[y1:y2, x1:x2], cv2.COLOR_BGR2RGB)
        images.append(preprocessing(Image.fromarray(crop)))
    return torch.stack(images) if images else torch.empty((0, 3, 256, 128))
