"""Optional observed door following within explicit short-gap geometry bounds."""
from counter import DoorLock,iou

def motion_compatible(a,b,dt,max_gap=.3):
 if a is None or b is None or not 0<dt<=max_gap:return False
 aw,ah=a[2]-a[0],a[3]-a[1];bw,bh=b[2]-b[0],b[3]-b[1]
 if min(aw,ah,bw,bh)<=0:return False
 return (.75<=bw/aw<=1.33 and .8<=bh/ah<=1.25 and iou(a,b)>=.4
         and abs((a[0]+a[2]-b[0]-b[2])/2)/aw<=.5
         and abs((a[1]+a[3]-b[1]-b[3])/2)/ah<=.15)

class MovingDoorLock(DoorLock):
 def __init__(self,**settings):
  super().__init__(**settings)
  if self.ttl>.3:raise ValueError('Observed moving-door experiment requires explicit ttl<=.3')
  self.follow_audit=[]
 def observe(self,box,now):
  if self.box is not None and box is not None and motion_compatible(self.box,box,now-self.last_seen,self.ttl):
   prior=self.box;self.box=tuple(box);self.candidate=tuple(box);self.last_seen=now
   self.follow_audit.append(dict(time_s=now,previous=list(prior),observed=list(box),generation=self.generation))
   return self.box
  return super().observe(box,now)
