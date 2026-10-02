"""Optional conservative nested-box continuity; reject ambiguous overlaps."""


def nested_head_match(parent,child):
    pw,ph=parent[2]-parent[0],parent[3]-parent[1]
    cw,ch=child[2]-child[0],child[3]-child[1]
    if min(pw,ph,cw,ch)<=0 or not .6<=cw/pw<=1.1 or not .15<=ch/ph<=.7:
        return False
    intersection=max(0,min(parent[2],child[2])-max(parent[0],child[0]))*max(0,min(parent[3],child[3])-max(parent[1],child[1]))
    return (intersection/(cw*ch)>=.9 and abs(parent[1]-child[1])/ph<=.06
            and abs((parent[0]+parent[2]-child[0]-child[2])/2)/pw<=.15)


class NestedTrackBridge:
    def __init__(self,confirm=3,max_gap=.75,bottom_approach_high=None):
        if type(confirm) is not int or confirm<2 or max_gap<=0:
            raise ValueError('Invalid bridge settings')
        self.confirm,self.max_gap=confirm,max_gap
        if bottom_approach_high is not None and not 0<bottom_approach_high<=2:
            raise ValueError('Invalid approach threshold')
        self.bottom_approach_high=bottom_approach_high
        self.reset()

    def reset(self):
        self.votes={};self.aliases={};self.last={};self.audit=[];self.approached=set();self.last_update=None

    def update(self,pairs,now,door=None):
        if self.last_update is not None and now-self.last_update>self.max_gap:
            self.votes.clear()
        self.last_update=now
        active={tid:box for tid,box in pairs}
        if self.bottom_approach_high is not None:
            if door is None or door[3]<=door[1]:
                self.reset();return pairs
            self.approached={p for p in self.approached if now-self.last.get(p,-1e9)<=self.max_gap}
            for tid,box in pairs:
                if (door[0]<=(box[0]+box[2])/2<=door[2]
                        and (box[3]-door[1])/(door[3]-door[1])>self.bottom_approach_high):
                    self.approached.add(tid)
        # Aliases expire as a group and are never carried across a door reset.
        self.aliases={c:p for c,p in self.aliases.items() if now-self.last.get(p,-1e9)<=self.max_gap}
        current={}
        for child,box in pairs:
            if child in self.aliases:
                continue
            parents=[p for p,b in pairs if p!=child and p not in self.aliases
                     and (self.bottom_approach_high is None or p in self.approached)
                     and nested_head_match(b,box)]
            if len(parents)!=1:
                continue
            parent=parents[0];key=(parent,child)
            count=self.votes.get(key,0)+1;current[key]=count
            if count>=self.confirm:
                # One parent cannot absorb several competing partial detections.
                siblings=[c for (p,c) in current if p==parent]
                possible=[c for c,b in pairs if c!=parent and nested_head_match(active[parent],b)]
                if len(possible)==1 and len(siblings)==1:
                    self.aliases[child]=parent
                    self.audit.append({'time_s':now,'parent_id':parent,'child_id':child})
        self.votes=current
        groups={}
        for tid,box in pairs:
            canonical=self.aliases.get(tid,tid)
            self.last[canonical]=now
            area=(box[2]-box[0])*(box[3]-box[1])
            if canonical not in groups or area>groups[canonical][0]:
                groups[canonical]=(area,box)
        self.last={p:t for p,t in self.last.items() if now-t<=self.max_gap}
        return [(p,v[1]) for p,v in groups.items()]
