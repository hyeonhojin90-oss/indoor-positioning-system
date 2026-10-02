"""Experimental short-gap observed ReID+geometry continuity; no synthetic boxes."""
import math
import numpy as np
from counter import iou
from temporal_nested_bridge import temporal_match

def head_aligned(a,b):
 aw,ah=a[2]-a[0],a[3]-a[1];bw,bh=b[2]-b[0],b[3]-b[1]
 if min(aw,ah,bw,bh)<=0:return False
 return .35<=bw/aw<=1.65 and .15<=bh/ah<=1.4 and abs(a[1]-b[1])<=.08*max(ah,bh) and abs((a[0]+a[2]-b[0]-b[2])/2)<=.45*max(aw,bw)

class AppearanceObservationBridge:
 def __init__(self,similarity=.7,margin=.08,confirm=3,max_gap=.75,simultaneous_partial=False):
  if not 0<similarity<1 or not 0<margin<1 or type(confirm) is not int or confirm<2 or not 0<max_gap<=1:raise ValueError('Invalid continuity policy')
  if type(simultaneous_partial) is not bool:raise ValueError('simultaneous_partial must be boolean')
  self.simultaneous_partial=simultaneous_partial
  self.similarity,self.margin,self.confirm,self.max_gap=similarity,margin,confirm,max_gap;self.reset()
 def reset(self):self.gallery={};self.aliases={};self.first_seen={};self.votes={};self.audit=[];self.previous_time=None
 def update(self,pairs,features,now):
  if len(pairs)!=len(features):raise ValueError('Observed features differ from boxes')
  features=np.asarray(features,dtype=np.float32)
  if len(pairs) and (features.ndim!=2 or not np.isfinite(features).all() or np.any(np.abs(np.linalg.norm(features,axis=1)-1)>.001)):raise ValueError('Require finite normalized observed features')
  if self.previous_time is not None and (now<self.previous_time or now-self.previous_time>self.max_gap):self.reset()
  self.previous_time=now
  self.gallery={p:[r for r in rows if 0<=now-r[0]<=self.max_gap] for p,rows in self.gallery.items()};self.gallery={p:r for p,r in self.gallery.items() if r}
  self.aliases={c:p for c,p in self.aliases.items() if p in self.gallery}
  for child,_ in pairs:self.first_seen.setdefault(child,now)
  # A canonical group is retained only while simultaneous boxes are nested.
  groups={}
  for child,b in pairs:groups.setdefault(self.aliases.get(child,child),[]).append((child,b))
  for parent,members in groups.items():
   if len(members)>1:
    largest=max(members,key=lambda v:(v[1][2]-v[1][0])*(v[1][3]-v[1][1]))[1]
    if any(not (b==largest or temporal_match(largest,b)) for _,b in members):
     for c,_ in members:self.aliases.pop(c,None)
  active={self.aliases.get(c,c) for c,_ in pairs};proposals={};scores={}
  for (child,b),feature in zip(pairs,features):
   if child in self.aliases or now-self.first_seen[child]>self.max_gap:continue
   ranked=[]
   for parent,rows in self.gallery.items():
    if parent==child or parent in self.aliases:continue
    if parent in active:
     current=[box for c,box in pairs if self.aliases.get(c,c)==parent]
     if len(current)!=1:continue
     if not temporal_match(b,current[0]):
      # Optional nested current observations require stronger same-frame
      # appearance; old gallery similarity alone cannot establish this merge.
      current_features=[v for (c,_),v in zip(pairs,features) if self.aliases.get(c,c)==parent]
      if not (self.simultaneous_partial and temporal_match(current[0],b)
              and len(current_features)==1 and float(np.dot(feature,current_features[0]))>=.85):continue
    candidates=[float(np.dot(feature,v)) for _,box,v in rows if head_aligned(box,b)]
    if candidates:ranked.append((max(candidates),parent))
   ranked.sort(reverse=True)
   if ranked and ranked[0][0]>=self.similarity and (len(ranked)==1 or ranked[0][0]-ranked[1][0]>=self.margin):
    proposals[child]=ranked[0][1];scores[child]=ranked[0][0]
  votes={}
  for child,parent in proposals.items():
   if list(proposals.values()).count(parent)!=1:continue
   key=(parent,child);votes[key]=self.votes.get(key,0)+1
   if votes[key]>=self.confirm:
    self.aliases[child]=parent;self.gallery.pop(child,None);self.audit.append(dict(time_s=now,parent_id=parent,child_id=child,cosine_similarity=scores[child]))
  self.votes=votes;groups={}
  for (child,b),feature in zip(pairs,features):
   parent=self.aliases.get(child,child);area=(b[2]-b[0])*(b[3]-b[1])
   if parent not in groups or area>groups[parent][0]:groups[parent]=(area,b,feature)
  for p,(_,box,feature) in groups.items():self.gallery.setdefault(p,[]).append((now,tuple(box),feature.copy()))
  live=set(self.gallery)|set(self.aliases)|{c for c,_ in pairs};self.first_seen={k:v for k,v in self.first_seen.items() if k in live}
  return [(p,v[1]) for p,v in groups.items()]
