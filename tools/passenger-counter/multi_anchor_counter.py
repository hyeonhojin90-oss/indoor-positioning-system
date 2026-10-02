"""Optional leading-ankle boarding evidence with one count per observed passage.

Body and ankle state machines share canonical IDs and door generations. Ankle
evidence can establish boarding; alighting still requires the body passage.
Contradictory same-frame directions stay unclassified. No synthetic foot is used.
"""
from counter import PassageCounter
from exit_evidence_guard import ExitEvidenceGuard

class DualAnchorCounter:
    def __init__(self,settings,anchor_y=1,require_body_transition=False,defer_ankle=False,exit_ankle_guard=False,exit_unknown_requires_inside=False):
        self.body=PassageCounter(**settings);self.ankle=PassageCounter(**settings)
        if type(require_body_transition) is not bool or (require_body_transition and
                (self.body.axis!='y' or self.body.entry!='negative')):
            raise ValueError('Body transition ankle gate requires negative-y entry')
        self.require_body_transition=require_body_transition
        if type(defer_ankle) is not bool:raise ValueError('defer_ankle must be boolean')
        self.defer_ankle=defer_ankle;self.pending={}
        if type(exit_ankle_guard) is not bool:
            raise ValueError('exit_ankle_guard must be boolean')
        if type(exit_unknown_requires_inside) is not bool or (exit_unknown_requires_inside and not exit_ankle_guard):
            raise ValueError('Unknown exit policy requires enabled ankle evidence guard')
        if exit_ankle_guard and self.body.geometry!='doorway':
            raise ValueError('Exit ankle evidence requires doorway geometry')
        self.exit_guard=ExitEvidenceGuard(unknown_requires_inside=exit_unknown_requires_inside,**{k:v for k,v in settings.items() if k in
                ('low','high','confirm','max_gap','transverse_low','transverse_high','transverse_band')}) if exit_ankle_guard else None
        self.anchor_y=anchor_y;self.totals={'in':0,'out':0};self.last={};self.evidence=[]

    def reset_tracks(self):
        self.body.reset_tracks();self.ankle.reset_tracks();self.last.clear();self.pending.clear()
        if self.exit_guard is not None:self.exit_guard.reset()

    def advance(self,now,visible_ids):
        """Prefer a later observed body passage; release measured evidence after loss.

        The original evidence time is retained, and commitment time is explicit.
        Visible people have no timeout that can force an early ankle count.
        """
        visible=set(visible_ids);events=[]
        for tid,(event,last_seen) in list(self.pending.items()):
            if tid in visible:self.pending[tid]=(event,now);continue
            if now-last_seen<=self.body.max_gap:continue
            self.pending.pop(tid)
            if self.last.get(tid,('',))[0]=='in':continue
            self.totals['in']+=1;self.last[tid]=('in',now)
            events.append(dict(event,commit_time_s=round(now,3),anchor_evidence='measured_ankle_deferred'))
        return events

    def update(self,tid,person_box,foot,door,now,frame=None):
        self.last={t:state for t,state in self.last.items() if now-state[1]<=self.body.max_gap}
        previous=self.last.get(tid)
        if previous:self.last[tid]=(previous[0],now)
        x1,y1,x2,y2=person_box
        prior_side=getattr(self.body.tracks.get(tid),'side','')
        prior_kind=getattr(self.body.tracks.get(tid),'outside_kind','')
        body_event=self.body.update(tid,((x1+x2)/2,y1+self.anchor_y*(y2-y1)),door,now)
        eligible=True
        if self.require_body_transition:
            u=(y1+self.anchor_y*(y2-y1)-door[1])/(door[3]-door[1])
            v=((x1+x2)/2-door[0])/(door[2]-door[0])
            left,right=self.body.transverse_low,self.body.transverse_high
            if prior_kind=='lateral' and self.body.lateral_inset is not None:
                left,right=max(left,self.body.lateral_inset),min(right,1-self.body.lateral_inset)
            eligible=prior_side=='high' and self.body.low<=u<=self.body.high and left<=v<=right
        use_foot=foot is not None
        if use_foot and not eligible:
            fu=(foot[1]-door[1])/(door[3]-door[1]);fv=(foot[0]-door[0])/(door[2]-door[0])
            al,ar=(0,1) if self.ankle.geometry=='axis' else (self.ankle.transverse_low,self.ankle.transverse_high)
            prior_ankle=self.ankle.tracks.get(tid)
            if prior_ankle and prior_ankle.side=='high' and prior_ankle.outside_kind=='lateral' and self.ankle.lateral_inset is not None:
                al,ar=max(al,self.ankle.lateral_inset),min(ar,1-self.ankle.lateral_inset)
            # Do not consume an early inside transition before body eligibility.
            # A real foot return remains observable and can cancel pending entry.
            if fu<self.ankle.low and al<=fv<=ar:use_foot=False
        foot_event=self.ankle.update(tid,foot,door,now) if use_foot else None
        exit_proof=self.exit_guard.observe(tid,foot,door,now) if self.exit_guard is not None else None
        if foot_event and frame is not None:foot_event['observation_frame']=frame
        if body_event and foot_event and body_event['direction']!=foot_event['direction']:
            self.evidence.append(dict(time_s=now,track_id=tid,status='conflicting_anchor_directions'))
            return None
        if body_event and body_event['direction']=='out' and exit_proof and not exit_proof['allow_exit']:
            self.evidence.append(dict(body_event,status='exit_ankle_evidence_conflict',
                                     observation_frame=frame,exit_evidence=exit_proof))
            body_event=None
        if self.defer_ankle:
            if body_event or (foot_event and foot_event['direction']=='out'):
                self.pending.pop(tid,None)
            if not body_event and foot_event and foot_event['direction']=='in':
                if not previous or previous[0]!='in':self.pending[tid]=(dict(foot_event),now)
                return None
        event=body_event or (foot_event if foot_event and foot_event['direction']=='in' else None)
        if event is None:return None
        source='body_and_ankle' if body_event and foot_event else ('body' if body_event else 'measured_ankle')
        if previous and previous[0]==event['direction']:
            self.evidence.append(dict(event,status='same_passage_duplicate',anchor_evidence=source))
            return None
        self.last[tid]=(event['direction'],now)
        self.totals[event['direction']]+=1
        return dict(event,anchor_evidence=source,**({'observation_frame':frame} if frame is not None else {}))
