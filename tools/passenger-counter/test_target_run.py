import copy,unittest
from verify_target_run import assess

class TargetRunTests(unittest.TestCase):
    def setUp(self):
        self.golden=dict(source_sha256='abc',frames=513,counts={'in':6,'out':0},model_sha256={'person_model':'123'},
                         config={'person_model':'models/person.onnx','counting':{'entry':'negative'},'imgsz':416},
                         events=[dict(frame=59,track_id=8,direction='in',time_s=1.967,observation_frame=59,door_generation=1)])
        self.summary=copy.deepcopy(self.golden)
        self.summary.update(device='0',ultralytics='8.3.228',backend_execution={k:dict(providers=['CUDAExecutionProvider','CPUExecutionProvider']) for k in ['people','door']})
        self.env=dict(platform='Linux',machine='aarch64',jetson_detected=True,cuda_available=True,packages={'ultralytics':'8.3.228'})
    def check(self):return assess(self.summary,self.golden,self.env)
    def test_relocated_paths_allowed_but_changed_direction_rejected(self):
        self.summary['config']['person_model']='different/location.onnx'
        self.assertTrue(self.check()['passed'])
        self.summary['config']['counting']['entry']='positive'
        self.assertFalse(self.check()['passed'])
    def test_same_total_with_wrong_person_or_time_fails(self):
        for key,value in [('track_id',9),('observation_frame',40),('time_s',1.3),('door_generation',2)]:
            with self.subTest(key=key):
                self.summary['events']=copy.deepcopy(self.golden['events']);self.summary['events'][0][key]=value
                self.assertFalse(self.check()['passed'])
    def test_silent_cpu_provider_fails(self):
        self.summary['backend_execution']['door']['providers']=['CPUExecutionProvider']
        self.assertFalse(self.check()['passed'])
    def test_windows_environment_and_incomplete_source_fail(self):
        self.env['platform']='Windows';self.summary['frames']=512
        self.assertFalse(self.check()['passed'])
    def test_engine_or_changed_weights_require_new_evidence(self):
        self.summary['model_sha256']['person_model']='different-engine-hash'
        self.assertFalse(self.check()['passed'])
    def test_used_fallback_backend_requires_its_own_cuda_provider(self):
        self.summary['door_acquisition_fallback_calls']=1
        self.assertFalse(self.check()['passed'])
        self.summary['backend_execution']['door_acquisition_fallback']={'providers':['CUDAExecutionProvider']}
        self.assertTrue(self.check()['passed'])
    def test_fallback_path_relocation_keeps_input_size_constraint(self):
        self.golden['config']['door_acquisition_fallback']={'model':'old/fallback.onnx','imgsz':640}
        self.summary['config']['door_acquisition_fallback']={'model':'new/fallback.onnx','imgsz':640}
        self.assertTrue(self.check()['passed'])
        self.summary['config']['door_acquisition_fallback']['imgsz']=416
        self.assertFalse(self.check()['passed'])

if __name__=='__main__':unittest.main()
