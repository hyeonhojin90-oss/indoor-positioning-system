"""Guard existing local run inputs without treating stream addresses as files."""
import hashlib
from pathlib import Path
from source_timing import source_kind


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class RuntimeInputEvidence:
    def __init__(self,source,config_path,config):
        self.source=Path(source) if source_kind(source)=='file' else None
        paths=[Path(config_path)]
        if self.source is not None:paths.append(self.source)
        self.model_roles={}
        self.unbound_model_roles=[]
        values={key:config[key] for key in ('person_model','door_model','door_primary_model','bus_model','pose_aux_model') if key in config}
        if config.get('door_acquisition_fallback'):
            values['door_acquisition_fallback.model']=config['door_acquisition_fallback']['model']
        for role,value in values.items():
            try:is_file=Path(value).is_file()
            except OSError:is_file=False
            if is_file:
                path=Path(value);paths.append(path);self.model_roles[role]=path
            else:self.unbound_model_roles.append(role)
        if config.get('appearance_bridge',{}).get('enabled'):
            root=Path(config['appearance_bridge']['model_root'])
            paths.extend([root/'model.onnx',root/'parity.json'])
        self.snapshot={str(path):digest(path) for path in paths}

    def verify(self):
        changed=[]
        for name,expected in self.snapshot.items():
            try:actual=digest(name)
            except OSError:actual=None
            if actual!=expected:changed.append(name)
        if changed:raise ValueError('Runtime local input changed: '+', '.join(changed))
        return dict(local_inputs_unchanged_verified=True,input_sha256_at_start=dict(self.snapshot),
                    source_sha256=self.snapshot[str(self.source)] if self.source is not None else None,
                    source_is_local_file=self.source is not None,
                    local_model_sha256={role:self.snapshot[str(path)] for role,path in self.model_roles.items()},
                    unbound_model_roles=self.unbound_model_roles,
                    check_scope='Existing local source/config/model files before model load and after processing; remote model artifacts and transient restored edits are not proven')
