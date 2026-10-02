"""Suppress expensive door detection until a bus is visible at the stop."""
from counter import iou


class BusPresenceGate:
    def __init__(self, min_conf=.35, min_area=.08, grace_s=.75,
                 max_door_bus_width_ratio=1,associated_conf=None,
                 associated_iou=.5,max_associated_span_s=3):
        if (not 0 < min_conf <= 1 or not 0 < min_area <= 1 or grace_s < 0
                or not 0 < max_door_bus_width_ratio <= 1):
            raise ValueError('Invalid bus gate settings')
        if associated_conf is not None and (not 0<associated_conf<min_conf
                or not 0<associated_iou<=1 or max_associated_span_s<=0):
            raise ValueError('Invalid associated bus settings')
        self.associated_conf,self.associated_iou=associated_conf,associated_iou
        self.max_associated_span_s=max_associated_span_s
        self.last_strong=float('-inf');self.strong_boxes=[];self.observation_kind='absent'
        self.min_conf, self.min_area, self.grace_s = min_conf, min_area, grace_s
        self.max_door_bus_width_ratio = max_door_bus_width_ratio
        self.last_seen = float('-inf')
        self.boxes = []

    def observe(self, boxes, classes, confidences, width, height, now,continuity_valid=False):
        if width <= 0 or height <= 0:
            raise ValueError('Invalid frame dimensions')
        detected = [box for box, cls, conf in zip(boxes, classes, confidences)
            if int(cls) == 5 and conf >= self.min_conf
            and max(0, box[2]-box[0])*max(0, box[3]-box[1])/(width*height) >= self.min_area
        ]
        if detected:
            self.last_strong=now;self.strong_boxes=detected
            self.observation_kind='strong_detection'
        elif (self.associated_conf is not None
              and 0<=now-self.last_strong<=self.max_associated_span_s
              and (0<=now-self.last_seen<=self.grace_s or continuity_valid)):
            detected=[box for box,cls,conf in zip(boxes,classes,confidences)
                if int(cls)==5 and conf>=self.associated_conf
                and max(0,box[2]-box[0])*max(0,box[3]-box[1])/(width*height)>=self.min_area
                and any(iou(box,anchor)>=self.associated_iou for anchor in self.strong_boxes)]
            self.observation_kind='associated_detection' if detected else 'grace'
        else:self.observation_kind='grace'
        if detected:
            self.last_seen = now
            self.boxes = detected
        visible = now-self.last_seen <= self.grace_s
        if not visible:
            self.boxes = []
            self.observation_kind='absent'
        return visible

    def accept_door(self, door):
        """Reject bus-front-sized boxes and doors not associated with a visible bus."""
        cx, cy = (door[0]+door[2])/2, (door[1]+door[3])/2
        width = door[2]-door[0]
        return any(bus[0] <= cx <= bus[2] and bus[1] <= cy <= bus[3]
                   and width <= (bus[2]-bus[0])*self.max_door_bus_width_ratio
                   for bus in self.boxes)
