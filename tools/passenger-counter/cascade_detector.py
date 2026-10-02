"""Grounding acquisition, then conservative lightweight door revalidation."""
from counter import iou, plausible_door


class CascadeDoorDetector:
    def __init__(self, primary, reference, primary_conf=.2, min_iou=.75,
                 refresh_calls=3, max_area=.6, min_aspect=0, associated_conf=None):
        if (not 0 < primary_conf <= 1 or not 0 < min_iou <= 1 or refresh_calls < 1
                or not 0 < max_area <= 1 or min_aspect < 0):
            raise ValueError('Invalid cascade thresholds')
        if associated_conf is not None and not 0 < associated_conf <= 1:
            raise ValueError('Invalid associated_conf')
        self.associated_conf = associated_conf
        self.primary, self.reference = primary, reference
        self.primary_conf, self.min_iou = primary_conf, min_iou
        self.refresh_calls, self.max_area, self.min_aspect = refresh_calls, max_area, min_aspect
        self.box, self.since_reference = None, 0
        self.stats = {'primary_calls': 0, 'reference_calls': 0, 'primary_accepted': 0}
        self.last_backend = None
        self.provenance = {'reference': reference.provenance}

    def reset(self):
        self.box = None
        self.since_reference = 0
        self.last_backend = None

    def predict(self, frame, device='cpu', conf=.35, imgsz=640, locked_box=None,
                candidate_filter=None, candidate_selector=None, **kwargs):
        # Never initialize a door from the less reliable public model alone.
        if self.box is not None and self.since_reference < self.refresh_calls:
            self.stats['primary_calls'] += 1
            result = self.primary.predict(frame, device=device, imgsz=imgsz,
                                          conf=self.primary_conf, classes=[0], verbose=False)[0]
            h, w = frame.shape[:2]
            boxes = result.boxes.xyxy.cpu().tolist()
            accepted = [j for j, b in enumerate(boxes)
                        if plausible_door(b,w,h,self.max_area,self.min_aspect)
                        and (candidate_filter is None or candidate_filter(b))
                        and iou(self.box, b) >= self.min_iou]
            if accepted:
                best = max(accepted, key=lambda j: iou(self.box, boxes[j]))
                # Keep association tied to the last reference box to prevent drift.
                self.since_reference += 1
                self.stats['primary_accepted'] += 1
                self.last_backend = 'primary'
                return [result[[best]]]
        self.stats['reference_calls'] += 1
        # A weaker reference detection can confirm an existing runtime lock,
        # but cannot acquire a new door or move the lock to another object.
        associated = locked_box is not None and self.associated_conf is not None
        threshold = min(conf,self.associated_conf) if associated else conf
        result = self.reference.predict(frame, device=device, conf=threshold,**kwargs)[0]
        h, w = frame.shape[:2]
        boxes = result.boxes.xyxy.cpu().tolist()
        scores = result.boxes.conf.cpu().tolist()
        accepted = [j for j, b in enumerate(boxes)
                    if plausible_door(b,w,h,self.max_area,self.min_aspect)
                    and (candidate_filter is None or candidate_filter(b))
                    and (scores[j] >= conf or (associated and scores[j] >= threshold
                                              and iou(locked_box,b) >= self.min_iou))]
        best = (max(accepted, key=lambda j: iou(self.box, boxes[j]))
                if accepted and self.box is not None else (accepted[0] if accepted else None))
        if candidate_selector is not None:
            selected=candidate_selector([boxes[j] for j in accepted])
            best=accepted[selected] if selected is not None else None
        self.box = boxes[best] if best is not None else None
        self.since_reference = 0
        self.last_backend = 'reference'
        return [result[[best]] if best is not None else result[[]]]
