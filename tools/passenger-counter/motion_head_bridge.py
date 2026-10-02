"""Experimental short-gap identity bridge using measured head-region optical flow."""
from dataclasses import dataclass

import cv2
import numpy as np


def head_region(box):
    x1, y1, x2, y2 = box
    w, h = x2-x1, y2-y1
    return np.array([x1+.15*w, y1, x2-.15*w, y1+min(.55*w, .5*h)], dtype=np.float32)


@dataclass
class HeadState:
    region: np.ndarray
    points: np.ndarray
    last_seen: float


class MotionHeadBridge:
    def __init__(self, max_gap=.75, confirm=2, min_points=6):
        if not 0 < max_gap <= 2 or type(confirm) is not int or confirm < 2 or min_points < 4:
            raise ValueError('Invalid head-flow settings')
        self.max_gap, self.confirm, self.min_points = max_gap, confirm, min_points
        self.reset()

    def reset(self):
        self.gray = None
        self.states = {}
        self.aliases = {}
        self.first_seen = {}
        self.votes = {}
        self.audit = []

    def _seed(self, gray, region):
        h, w = gray.shape
        x1, y1, x2, y2 = np.round(region).astype(int)
        x1, y1, x2, y2 = max(0,x1), max(0,y1), min(w,x2), min(h,y2)
        mask = np.zeros_like(gray)
        if x2 > x1 and y2 > y1:
            mask[y1:y2,x1:x2] = 255
        p = cv2.goodFeaturesToTrack(gray, maxCorners=32, qualityLevel=.02, minDistance=3, mask=mask)
        return p if p is not None else np.empty((0,1,2), dtype=np.float32)

    def _flow(self, gray, state):
        if len(state.points) < self.min_points:
            state.points = np.empty((0,1,2), dtype=np.float32)
            return
        nxt, ok, _ = cv2.calcOpticalFlowPyrLK(self.gray, gray, state.points, None, winSize=(15,15), maxLevel=2)
        if nxt is None:
            state.points = np.empty((0,1,2), dtype=np.float32)
            return
        back, valid, _ = cv2.calcOpticalFlowPyrLK(gray, self.gray, nxt, None, winSize=(15,15), maxLevel=2)
        if back is None:
            state.points = np.empty((0,1,2), dtype=np.float32)
            return
        error = np.linalg.norm(back-state.points, axis=2).ravel()
        keep = (ok.ravel()>0) & (valid.ravel()>0) & np.isfinite(error) & (error <= 1)
        if keep.sum() < self.min_points:
            state.points = np.empty((0,1,2), dtype=np.float32)
            return
        motion = np.median(nxt[keep]-state.points[keep], axis=0).ravel()
        residual = np.linalg.norm((nxt-state.points).reshape(-1,2)-motion, axis=1)
        keep &= residual <= 3
        state.region += np.tile(motion, 2)
        state.points = nxt[keep]

    def _compatible(self, state, box):
        if len(state.points) < self.min_points:
            return False
        a, b = state.region, head_region(box)
        aw, bw = a[2]-a[0], b[2]-b[0]
        if min(aw,bw) <= 0 or not .65 <= bw/aw <= 1.5:
            return False
        intersection = np.maximum(0, np.minimum(a[2:],b[2:])-np.maximum(a[:2],b[:2])).prod()
        smaller = min(np.maximum(0,a[2:]-a[:2]).prod(), np.maximum(0,b[2:]-b[:2]).prod())
        points = state.points.reshape(-1,2)
        inside = ((points >= b[:2]) & (points <= b[2:])).all(axis=1).mean()
        return smaller > 0 and intersection/smaller >= .7 and inside >= .8

    def update(self, frame, pairs, now):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        self.states = {i:s for i,s in self.states.items() if now-s.last_seen <= self.max_gap}
        self.aliases = {i:c for i,c in self.aliases.items() if c in self.states}
        # Previously linked IDs may reappear simultaneously. Their measured
        # detections no longer prove one person; revoke aliases instead of crash
        # or assigning the same canonical ID to two current boxes.
        groups={}
        for i,_ in pairs:groups.setdefault(self.aliases.get(i,i),[]).append(i)
        for canonical,members in groups.items():
            if len(members)>1:
                for child in members:
                    if child in self.aliases:
                        self.aliases.pop(child)
                        self.audit.append(dict(time_s=now,parent_id=canonical,child_id=child,
                                               action='revoked',reason='simultaneous_current_detections'))
        live={i for i,_ in pairs}|set(self.aliases)|set(self.states)
        self.first_seen={i:t for i,t in self.first_seen.items() if i in live}
        active = {self.aliases.get(i,i) for i,_ in pairs}
        if self.gray is not None:
            for state in self.states.values():
                self._flow(gray, state)
        candidates = []
        for i, box in pairs:
            self.first_seen.setdefault(i,now)
            if i in self.aliases or now-self.first_seen[i] > .15:
                continue
            parents = [j for j,s in self.states.items() if j not in active and self._compatible(s,box)]
            if len(parents) == 1:
                candidates.append((parents[0],i))
        votes = {}
        for parent, child in candidates:
            if sum(p==parent for p,_ in candidates) != 1:
                continue
            key = (parent,child)
            votes[key] = self.votes.get(key,0)+1
            if votes[key] >= self.confirm:
                self.aliases[child] = parent
                self.states.pop(child,None)
                self.audit.append(dict(time_s=now,parent_id=parent,child_id=child,
                                       tracked_head_points=len(self.states[parent].points)))
        self.votes = votes
        output = []
        for i, box in pairs:
            canonical = self.aliases.get(i,i)
            if canonical in self.states:
                s = self.states[canonical]
                s.last_seen = now
                if len(s.points) < self.min_points:
                    s.region = head_region(box)
                    s.points = self._seed(gray,s.region)
            else:
                region = head_region(box)
                self.states[canonical] = HeadState(region,self._seed(gray,region),now)
            output.append((canonical,box))
        self.gray = gray
        # Ambiguous simultaneous canonical duplicates are not allowed.
        if len({i for i,_ in output}) != len(output):
            raise RuntimeError('Head-flow bridge produced simultaneous aliases')
        return output
