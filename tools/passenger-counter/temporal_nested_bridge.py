"""Experimental short-gap full-to-partial continuity; no appearance or predicted boxes."""
from track_bridge import nested_head_match

def temporal_match(parent,child):
    pw,ph=parent[2]-parent[0],parent[3]-parent[1];cw,ch=child[2]-child[0],child[3]-child[1]
    if min(pw,ph,cw,ch)<=0 or not .3<=cw/pw<=1.1 or not .15<=ch/ph<=.7:return False
    intersection=max(0,min(parent[2],child[2])-max(parent[0],child[0]))*max(0,min(parent[3],child[3])-max(parent[1],child[1]))
    return intersection/(cw*ch)>=.9 and abs(parent[1]-child[1])/ph<=.06 and abs((parent[0]+parent[2]-child[0]-child[2])/2)/pw<=.25

class TemporalNestedBridge:
    def __init__(self,confirm=3,max_gap=.75):
        if confirm<2 or max_gap<=0:raise ValueError('Require multiple contiguous short-gap observations')
        self.confirm,self.max_gap=confirm,max_gap;self.reset()
    def reset(self):self.last={};self.first_seen={};self.aliases={};self.votes={};self.audit=[];self.previous_time=None
    def update(self,pairs,now):
        active=dict(pairs)
        if self.previous_time is not None and now-self.previous_time>self.max_gap:self.reset()
        self.previous_time=now
        self.last={k:v for k,v in self.last.items() if now-v[0]<=self.max_gap}
        self.aliases={c:p for c,p in self.aliases.items() if p in self.last}
        self.first_seen={k:v for k,v in self.first_seen.items() if k in self.last or k in self.aliases}
        for child,_ in pairs:self.first_seen.setdefault(child,now)
        for child,parent in list(self.aliases.items()):
            if child in active and parent in active and not (nested_head_match(active[parent],active[child]) or temporal_match(active[parent],active[child])):
                del self.aliases[child]
        proposals={}
        for child,box in pairs:
            if child in self.aliases or now-self.first_seen[child]>self.max_gap:continue
            candidates=[parent for parent,(time,prior) in self.last.items()
                if parent not in active and parent not in self.aliases and temporal_match(prior,box)]
            if len(candidates)==1:proposals[child]=candidates[0]
        current={}
        for child,parent in proposals.items():
            if list(proposals.values()).count(parent)!=1:continue
            key=(parent,child);current[key]=self.votes.get(key,0)+1
            if current[key]>=self.confirm:
                self.aliases[child]=parent;self.last.pop(child,None);self.audit.append(dict(time_s=now,parent_id=parent,child_id=child))
        self.votes=current;groups={}
        for child,box in pairs:
            canonical=self.aliases.get(child,child);area=(box[2]-box[0])*(box[3]-box[1])
            if canonical not in groups or area>groups[canonical][0]:groups[canonical]=(area,box)
        # Keep a full last observation for matching until it expires; partial aliases
        # refresh continuity but never synthesize a missing full-body measurement.
        for canonical,(_,box) in groups.items():self.last[canonical]=(now,box)
        return [(canonical,value[1]) for canonical,value in groups.items()]
