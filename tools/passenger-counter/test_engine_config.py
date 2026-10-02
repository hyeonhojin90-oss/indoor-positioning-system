import copy,hashlib,tempfile,unittest
from pathlib import Path
from prepare_engine_config import validate_export,runtime_roles

class EngineConfigTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.engine=Path(self.tmp.name)/'model.engine';self.engine.write_bytes(b'fixture only, no actual device engine')
        self.config=dict(person_model='person.onnx',door_model='door.onnx',imgsz=416,person_imgsz=640)
        self.checkpoint={'sha256':'actual-source-checkpoint'}
        self.report=dict(target_environment=dict(platform='Linux',machine='aarch64',jetson_detected=True,cuda_available=True,tensorrt_import_version='10',packages={'ultralytics':'8.3.228'}),
            engine_build_completed=True,dynamic=True,half=True,batch=1,source_model_sha256=self.checkpoint['sha256'],imgsz=640,task='detect',engine_sha256=hashlib.sha256(self.engine.read_bytes()).hexdigest())
    def test_changed_lineage_size_or_task_rejected(self):
        for key,value in [('source_model_sha256','wrong'),('imgsz',416),('task','pose'),('dynamic',False),('half',False)]:
            report=copy.deepcopy(self.report);report[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):validate_export(self.config,'person_model',self.checkpoint,report,self.engine)
    def test_missing_or_changed_engine_rejected(self):
        self.engine.write_bytes(b'changed')
        with self.assertRaises(ValueError):validate_export(self.config,'person_model',self.checkpoint,self.report,self.engine)
    def test_wrong_host_cannot_supply_target_export(self):
        self.report['target_environment']['platform']='Windows'
        with self.assertRaises(ValueError):validate_export(self.config,'person_model',self.checkpoint,self.report,self.engine)
    def test_fallback_and_pose_are_required_active_roles(self):
        self.config.update(pose_aux_model='pose.onnx',door_acquisition_fallback={'model':'backup.onnx','imgsz':640})
        self.assertEqual(set(runtime_roles(self.config)),{'person_model','door_model','pose_aux_model','door_acquisition_fallback.model'})

if __name__=='__main__':unittest.main()
