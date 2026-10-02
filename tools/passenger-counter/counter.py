"""Pure counting state; coordinates relative to a locked doorway, not screen pixels."""
from dataclasses import dataclass
from statistics import median


def iou(a, b):
    x = max(0, min(a[2], b[2]) - max(a[0], b[0]))
    y = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    intersection = x * y
    area = lambda r: max(0, r[2]-r[0]) * max(0, r[3]-r[1])
    return intersection / max(1e-9, area(a) + area(b) - intersection)


def plausible_door(box, width, height, max_area=.6, min_aspect=0):
    box_width, box_height = box[2]-box[0], box[3]-box[1]
    return (box_width > 0 and box_height > 0 and width > 0 and height > 0
            and box_width*box_height/(width*height) <= max_area
            and box_height/box_width >= min_aspect)


class DoorLock:
    """Freeze stable geometry; invalidate on movement/loss before counting resumes."""
    def __init__(self, stable=3, min_iou=.75, ttl=1.5, aggregation='latest'):
        if aggregation not in ('latest','median'):
            raise ValueError('Unknown door acquisition aggregation')
        self.stable, self.min_iou, self.ttl = stable, min_iou, ttl
        self.aggregation = aggregation
        self.history = []
        self.box = self.candidate = None
        self.hits, self.last_seen, self.generation = 0, -1e9, 0

    def reset(self):
        if self.box is not None or self.candidate is not None:
            self.generation += 1
        self.box = self.candidate = None
        self.hits = 0
        self.history = []
        self.last_seen = -1e9

    def valid_box(self, now):
        """Only expose a current lock to weak detection revalidation."""
        return self.box if 0 <= now-self.last_seen <= self.ttl else None

    def observe(self, box, now):
        if (self.box is not None or self.candidate is not None) and now-self.last_seen > self.ttl:
            self.box=self.candidate=None
            self.hits=0
            self.history=[]
            self.generation+=1
        if self.box is not None and (box is None or iou(self.box, box) < self.min_iou):
            # A positive displaced detection invalidates immediately. A missed
            # detection may be an occlusion, so allow a short explicit grace time.
            if box is not None or now-self.last_seen > self.ttl:
                self.box = self.candidate = None
                self.hits = 0
                self.history = []
                self.generation += 1
        if box is None:
            self.candidate, self.hits = None, 0
            self.history = []
            return self.box
        self.last_seen = now
        if self.box is None:
            compatible = self.candidate is not None and iou(self.candidate, box) >= self.min_iou
            self.hits = self.hits+1 if compatible else 1
            self.history = (self.history if compatible else []) + [tuple(box)]
            self.candidate = box
            if self.hits >= self.stable:
                self.box = (tuple(median(values) for values in zip(*self.history))
                            if self.aggregation == 'median' else tuple(box))
                self.history = []
                self.generation += 1
        return self.box


@dataclass
class TrackState:
    last: float
    candidate: str = ''
    hits: int = 0
    side: str = ''
    outside_kind: str = ''
    side_origin_u: float = 0
    side_max_v: float = float('-inf')


class PassageCounter:
    def __init__(self, axis='y', entry='negative', low=.4, high=.6,
                 confirm=2, max_gap=.75, outside_margin=0, geometry='axis',
                 transverse_low=.1, transverse_high=.9, transverse_band=.1,
                 lateral_inset=None, transverse_margin=0, transverse_exit=None,
                 min_entry_displacement=0,entry_approach_v_min=None):
        if axis not in ('x', 'y') or entry not in ('positive', 'negative'):
            raise ValueError('Invalid axis/entry')
        if not -1 <= low < high <= 2 or confirm < 1 or max_gap <= 0 or not 0 <= outside_margin <= 1:
            raise ValueError('Invalid thresholds')
        if geometry not in ('axis','doorway') or not 0 <= transverse_low < transverse_high <= 1 or not 0 <= transverse_band <= 1:
            raise ValueError('Invalid doorway geometry')
        if geometry=='doorway' and (axis!='y' or entry!='negative'):
            raise ValueError('Doorway geometry requires y axis and negative entry')
        if lateral_inset is not None and (geometry!='doorway' or not 0 <= lateral_inset < .5):
            raise ValueError('Invalid lateral inset')
        if not 0<=transverse_margin<=1 or (geometry!='axis' and transverse_margin):
            raise ValueError('Transverse margin is an axis-only value in 0..1')
        self.transverse_margin=transverse_margin
        if transverse_exit is not None and (geometry!='axis' or axis!='x' or entry!='positive'
                                             or not 0<=transverse_exit<=1+transverse_margin):
            raise ValueError('Transverse exit requires positive x axis and covered vertical range')
        self.transverse_exit=transverse_exit
        if not 0<=min_entry_displacement<=1:
            raise ValueError('Invalid entry displacement')
        self.min_entry_displacement=min_entry_displacement
        if entry_approach_v_min is not None and (axis!='x' or entry!='positive'
                or transverse_exit is None or not 0<=entry_approach_v_min<=1+transverse_margin):
            raise ValueError('Entry floor approach requires configured positive-x side view')
        self.entry_approach_v_min=entry_approach_v_min
        self.lateral_inset = lateral_inset
        self.geometry = geometry
        self.transverse_low,self.transverse_high = transverse_low,transverse_high
        self.transverse_band = transverse_band
        self.axis, self.entry = axis, entry
        self.low, self.high, self.confirm, self.max_gap = low, high, confirm, max_gap
        self.outside_margin = outside_margin
        self.tracks = {}
        self.totals = {'in': 0, 'out': 0}

    def reset_tracks(self):
        self.tracks.clear()

    def update(self, track_id, point, box, now):
        self.tracks = {k:v for k,v in self.tracks.items() if now-v.last <= self.max_gap}
        x, y = point
        x1, y1, x2, y2 = box
        if x2 <= x1 or y2 <= y1:
            self.tracks.pop(track_id, None)
            return None
        u = (x-x1)/(x2-x1) if self.axis == 'x' else (y-y1)/(y2-y1)
        v = (y-y1)/(y2-y1) if self.axis == 'x' else (x-x1)/(x2-x1)
        transverse = (y1 <= y <= y2) if self.axis == 'x' else (x1 <= x <= x2)
        if self.geometry=='axis' and self.transverse_margin:
            transverse = -self.transverse_margin <= v <= 1+self.transverse_margin
        if self.geometry=='doorway':
            transverse = -self.outside_margin <= v <= 1+self.outside_margin
        if not transverse or not (min(0,self.low)-self.outside_margin <= u <= max(1,self.high)+self.outside_margin):
            self.tracks.pop(track_id, None)
            return None
        side = 'low' if u < self.low else 'high' if u > self.high else ''
        if self.transverse_exit is not None:
            # Side-view entry goes horizontally into the portal; alighting may
            # move down from the step before crossing the horizontal boundary.
            side = 'low' if u<self.low or v>self.transverse_exit else ('high' if u>self.high else '')
        s = self.tracks.setdefault(track_id, TrackState(now))
        if self.geometry=='doorway':
            left,right = self.transverse_low,self.transverse_high
            # A lateral approach needs horizontal penetration too: a clipped
            # foot box alone must not turn a waiting person into an entrant.
            if s.side=='high' and s.outside_kind=='lateral' and self.lateral_inset is not None:
                left,right = max(left,self.lateral_inset),min(right,1-self.lateral_inset)
            inside = u < self.low and left <= v <= right
            outside = u > self.high or v < -self.transverse_band or v > 1+self.transverse_band
            side = 'low' if inside else 'high' if outside else ''
        s.last = now
        if not side:
            s.candidate, s.hits = '', 0
            return None
        s.hits = s.hits+1 if side == s.candidate else 1
        s.candidate = side
        if s.hits < self.confirm:
            return None
        if s.side == side:
            s.side_max_v=max(s.side_max_v,v)
            return None
        old, s.side = s.side, side
        origin=s.side_origin_u
        approach_v=s.side_max_v
        s.side_origin_u=u
        s.side_max_v=v
        if side=='high':
            s.outside_kind = 'bottom' if u > self.high else 'lateral'
        if not old:
            return None
        positive = old == 'low' and side == 'high'
        direction = 'in' if positive == (self.entry == 'positive') else 'out'
        if direction=='in' and self.entry_approach_v_min is not None and approach_v<self.entry_approach_v_min:
            return None
        if direction=='in' and self.min_entry_displacement:
            motion=(u-origin)*(1 if self.entry=='positive' else -1)
            if motion<self.min_entry_displacement:
                # A body-box foot can jump above the side-view exit edge while
                # its horizontal position stays still. Observe the new side,
                # but do not invent entry motion from that vertical jump.
                return None
        self.totals[direction] += 1
        return {'time_s': round(now, 3), 'track_id': track_id, 'direction': direction}
