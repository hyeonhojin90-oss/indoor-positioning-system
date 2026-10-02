"""Optional doorway OUT evidence guard; missing ankles remain unknown."""
import math

class ExitEvidenceGuard:
    def __init__(self,low,high,confirm=2,max_gap=.75,transverse_low=.1,
                 transverse_high=.9,transverse_band=.1,unknown_requires_inside=False):
        if type(unknown_requires_inside) is not bool:raise ValueError('unknown_requires_inside must be boolean')
        self.unknown_requires_inside=unknown_requires_inside
        if not (low<high and type(confirm) is int and confirm>=1 and max_gap>0
                and 0<=transverse_low<transverse_high<=1 and 0<=transverse_band<=1):
            raise ValueError('Invalid exit evidence settings')
        self.low,self.high,self.confirm,self.max_gap=low,high,confirm,max_gap
        self.left,self.right,self.band=transverse_low,transverse_high,transverse_band
        self.reset()

    def reset(self):
        self.states={}

    def observe(self,tid,foot,door,now):
        self.states={k:s for k,s in self.states.items() if now-s['last']<=self.max_gap}
        state=self.states.setdefault(tid,dict(last=now,hits=0,inside=False))
        state['last']=now
        if foot is None:
            state['hits']=0
            allow=state['inside'] if self.unknown_requires_inside else True
            return dict(allow_exit=allow,reason='unknown_ankles' if allow else 'unknown_ankles_without_inside_proof',prior_inside=state['inside'])
        if len(foot)!=2 or not all(math.isfinite(v) for v in foot):
            raise ValueError('Invalid measured foot')
        if door[2]<=door[0] or door[3]<=door[1]:raise ValueError('Invalid doorway')
        u=(foot[1]-door[1])/(door[3]-door[1]);v=(foot[0]-door[0])/(door[2]-door[0])
        prior=state['inside']
        outside=u>self.high or v< -self.band or v>1+self.band
        inside=u<self.low and self.left<=v<=self.right
        state['hits']=state['hits']+1 if inside else 0
        if state['hits']>=self.confirm:state['inside']=True
        allow=outside or prior
        return dict(allow_exit=allow,reason='observed_outside' if outside else
                    ('prior_measured_inside' if prior else 'unproven_inside_and_foot_not_outside'),
                    prior_inside=prior,foot_u=u,foot_v=v)
