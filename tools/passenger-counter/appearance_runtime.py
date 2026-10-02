"""Optional observed-only appearance continuity; disabled unless explicitly configured."""
from pathlib import Path
import time


def validate(config):
    allowed={'enabled','model_root','similarity','margin','confirm','max_gap','simultaneous_partial'}
    if not isinstance(config,dict) or set(config)-allowed:
        raise ValueError('Invalid observed appearance options')
    if type(config.get('enabled',False)) is not bool:
        raise ValueError('Appearance enabled must be boolean')
    if not config.get('enabled',False):
        return None
    root=config.get('model_root')
    if not isinstance(root,str) or not root:
        raise ValueError('Verified ONNX appearance root required')
    from appearance_observation_bridge import AppearanceObservationBridge
    options={k:v for k,v in config.items() if k not in ('enabled','model_root')}
    AppearanceObservationBridge(**options)
    return root,options


class ObservedAppearanceRuntime:
    def __init__(self,features,options=None):
        from appearance_observation_bridge import AppearanceObservationBridge
        self.features=features
        self.bridge=AppearanceObservationBridge(**(options or {}))
        self.generation=None
        self.links=[]
        self.calls=self.observed_boxes=0
        self.elapsed_seconds=0.

    def update(self,frame,pairs,now,door,generation,frame_index):
        if door is None or generation!=self.generation:
            self.bridge.reset()
        self.generation=generation
        if door is None:
            return pairs
        start=time.perf_counter()
        features=self.features.extract(frame,[box for _,box in pairs])
        self.calls+=int(bool(pairs));self.observed_boxes+=len(pairs)
        before=len(self.bridge.audit)
        result=self.bridge.update(pairs,features,now)
        self.links.extend(dict(e,frame=frame_index,door_generation=generation)
                          for e in self.bridge.audit[before:])
        self.elapsed_seconds+=time.perf_counter()-start
        return result

    def describe(self):
        self.features.verify_artifacts_unchanged()
        return dict(observed_only=True,predicted_boxes_used=False,links=self.links,
            feature_calls=self.calls,observed_crops=self.observed_boxes,
            elapsed_seconds=self.elapsed_seconds,
            providers=self.features.session.get_providers(),
            jetson_validated=False,independent_accuracy_validated=False)


def create(config):
    validated=validate(config)
    if validated is None:
        return None
    root,options=validated
    from osnet_onnx_features import ONNXOSNetFeatures
    return ObservedAppearanceRuntime(ONNXOSNetFeatures(Path(root)),options)
