"""Synthetic verifier fixtures; never claim these are actual TensorRT execution."""
import copy,unittest
from verify_engine_run import assess

class EngineRunTests(unittest.TestCase):
    def setUp(self):
        self.env=dict(platform='Linux',machine='aarch64',jetson_detected=True,cuda_available=True,tensorrt_import_version='10',packages={'ultralytics':'8.3.228'})
        self.original=dict(person_model='models/person.onnx',door_model='models/door.onnx',imgsz=416,person_imgsz=640,counting={'entry':'negative'})
        self.golden=dict(config=self.original,source_sha256='source',frames=513,counts={'in':1,'out':0},events=[dict(frame=59,track_id=8,direction='in',time_s=1.967,observation_frame=59,door_generation=1)],model_sha256={'person_model':'onnx-person','door_model':'onnx-door'})
        self.summary=copy.deepcopy(self.golden);self.summary.update(device='0',ultralytics='8.3.228')
        self.summary['config'].update(person_model='person.engine',door_model='door.engine')
        self.summary['model_sha256']={'person_model':'engine-person','door_model':'engine-door'}
        backend=dict(tensorrt_engine=True,execution_context_loaded=True,device='cuda:0',dynamic=True,fp16=True)
        self.summary['backend_execution']={r:copy.deepcopy(backend) for r in ['people','door']}
        self.manifest=dict(models={},export_checkpoints={});self.provenance=dict(roles={});self.parities={}
        for role,label,size,conf in [('person_model','person',640,.1),('door_model','door',416,.25)]:
            path=self.original[role];self.manifest['models'][path]={'sha256':'onnx-'+label};self.manifest['export_checkpoints'][path]={'sha256':'pt-'+label}
            self.provenance['roles'][role]=dict(original_onnx=path,checkpoint_sha256='pt-'+label,engine_sha256='engine-'+label)
            observation=dict(box=[0,0,100,400],score=.7,class_id=0)
            self.parities[role]=dict(passed=True,target_environment=copy.deepcopy(self.env),hashes=dict(reference='pt-'+label,candidate='engine-'+label,source='source'),
                imgsz=size,rect=True,device='0',task='detect',conf=conf,classes=[0],backend={'candidate':copy.deepcopy(backend)},
                rows=[dict(frame=59,reference=[observation],candidate=[copy.deepcopy(observation)])])
    def check(self):return assess(self.summary,self.golden,self.env,self.original,self.manifest,self.provenance,self.parities)
    def test_all_required_evidence_is_distinct_from_field_proof(self):
        result=self.check();self.assertTrue(result['passed']);self.assertFalse(result['field_validated']);self.assertFalse(result['sustained_performance_validated'])
    def test_same_totals_wrong_identity_or_early_event_rejected(self):
        for key,value in [('track_id',9),('observation_frame',40),('door_generation',2)]:
            self.summary['events']=copy.deepcopy(self.golden['events']);self.summary['events'][0][key]=value
            self.assertFalse(self.check()['passed'])
    def test_missing_context_cpu_or_wrong_source_parity_rejected(self):
        for field,value in [('execution_context_loaded',False),('device','cpu'),('fp16',False),('dynamic',False)]:
            old=self.summary['backend_execution']['door'][field];self.summary['backend_execution']['door'][field]=value
            self.assertFalse(self.check()['passed']);self.summary['backend_execution']['door'][field]=old
        self.parities['door_model']['hashes']['source']='other-source';self.assertFalse(self.check()['passed'])
    def test_empty_only_or_false_positive_parity_flag_recomputed(self):
        parity=self.parities['door_model'];original=copy.deepcopy(parity['rows'])
        parity['rows']=[dict(frame=59,reference=[],candidate=[])];self.assertFalse(self.check()['passed'])
        parity['rows']=original;parity['rows'][0]['candidate'][0]['box']=[300,0,400,400];self.assertFalse(self.check()['passed'])
    def test_checkpoint_engine_size_conf_and_class_constraints(self):
        for key,value in [('imgsz',640),('conf',.1),('classes',[5]),('task','pose'),('rect',False)]:
            old=self.parities['door_model'][key];self.parities['door_model'][key]=value
            self.assertFalse(self.check()['passed']);self.parities['door_model'][key]=old
        self.provenance['roles']['door_model']['checkpoint_sha256']='other-training';self.assertFalse(self.check()['passed'])
    def test_windows_or_duplicate_frames_cannot_validate(self):
        self.env['platform']='Windows';self.assertFalse(self.check()['passed']);self.env['platform']='Linux'
        self.parities['door_model']['rows']*=2;self.assertFalse(self.check()['passed'])
    def test_used_fallback_requires_own_engine_and_parity(self):
        role='door_acquisition_fallback.model';self.original['door_acquisition_fallback']=dict(model='models/backup.onnx',imgsz=640)
        self.summary['config']['door_acquisition_fallback']=dict(model='backup.engine',imgsz=640)
        self.summary['model_sha256'][role]='engine-backup';self.golden['model_sha256'][role]='onnx-backup'
        self.manifest['models']['models/backup.onnx']={'sha256':'onnx-backup'};self.manifest['export_checkpoints']['models/backup.onnx']={'sha256':'pt-backup'}
        self.provenance['roles'][role]=dict(original_onnx='models/backup.onnx',checkpoint_sha256='pt-backup',engine_sha256='engine-backup')
        self.assertTrue(self.check()['passed']);self.assertEqual(self.check()['unused_roles'],[role])
        self.summary['door_acquisition_fallback_calls']=1;self.assertFalse(self.check()['passed'])

if __name__=='__main__':unittest.main()
