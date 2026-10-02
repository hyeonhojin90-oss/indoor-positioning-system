"""Experimental continuity using recent stable observed bodies, never predicted feet."""
from statistics import median
from counter import iou
from temporal_nested_bridge import temporal_match

class StableObservationBridge:
    def __init__(self,confirm=3,max_gap=.75):
        if type(confirm) is not int or confirm<2 or not 0<max_gap<=1:raise ValueError('Require contiguous repeated short-gap observations')
        self.confirm,self.max_gap=confirm,max_gap;self.reset()
    def reset(self):self.history={};self.aliases={};self.votes={};self.audit=[];self.previous_time=None
    def template(self,canonical,now):
        rows=[(t,b) for t,b in self.history.get(canonical,[]) if 0<=now-t<=self.max_gap]
        if len(rows)<3:return None
        tallest=max(b[3]-b[1] for _,b in rows)
        stable=[b for _,b in rows if b[3]-b[1]>=.85*tallest]
        if len(stable)<3:return None
        return tuple(median(v) for v in zip(*stable))
    def update(self,pairs,now):
        if self.previous_time is not None and (now<self.previous_time or now-self.previous_time>self.max_gap):self.reset()
        self.previous_time=now
        self.history={p:[(t,b) for t,b in rows if 0<=now-t<=self.max_gap] for p,rows in self.history.items()}
        self.history={p:r for p,r in self.history.items() if r}
        self.aliases={c:p for c,p in self.aliases.items() if p in self.history}
        active=dict(pairs);groups={}
        for child,b in pairs:groups.setdefault(self.aliases.get(child,child),[]).append((child,b))
        # Reappearing simultaneously separated observations cannot be one person.
        for canonical,members in groups.items():
            if len(members)>1:
                largest=max(members,key=lambda v:(v[1][2]-v[1][0])*(v[1][3]-v[1][1]))[1]
                if any(not (b==largest or temporal_match(largest,b)) for _,b in members):
                    for c,_ in members:
                        if c in self.aliases:del self.aliases[c]
        canonical_active={self.aliases.get(c,c) for c,_ in pairs};proposals={};reasons={}
        for child,box in pairs:
            if child in self.aliases:continue
            parents=[]
            for parent in self.history:
                if parent==child or parent in self.aliases:continue
                template=self.template(parent,now)
                if template is None:continue
                if parent not in canonical_active and temporal_match(template,box):parents.append(parent);reasons[(parent,child)]='recent_stable_body_to_partial'
                elif parent in canonical_active:
                    observations=[b for c,b in pairs if self.aliases.get(c,c)==parent]
                    if len(observations)==1 and temporal_match(box,observations[0]) and iou(template,box)>.4:
                        parents.append(parent);reasons[(parent,child)]='full_body_returns_over_current_partial'
            if len(parents)==1:proposals[child]=parents[0]
        votes={}
        for child,parent in proposals.items():
            if list(proposals.values()).count(parent)!=1:continue
            key=parent,child;votes[key]=self.votes.get(key,0)+1
            if votes[key]>=self.confirm:
                self.aliases[child]=parent
                self.history.pop(child,None)
                self.audit.append(dict(time_s=now,parent_id=parent,child_id=child,reason=reasons[key]))
        self.votes=votes;groups={}
        for child,b in pairs:
            parent=self.aliases.get(child,child);area=(b[2]-b[0])*(b[3]-b[1])
            if parent not in groups or area>groups[parent][0]:groups[parent]=(area,b)
        for p,(_,b) in groups.items():self.history.setdefault(p,[]).append((now,tuple(b)))
        return [(p,v[1]) for p,v in groups.items()]
