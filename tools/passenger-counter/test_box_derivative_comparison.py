"""Reject architecture-task exceptions unless exact exported weight lineage is proven."""
import hashlib,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from compare_run_exports import compare

class DerivativeComparisonTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.runs=[];self.models=[]
        for i,task in enumerate(['segment','detect']):
            run=self.root/f'run{i}';run.mkdir();modeldir=self.root/f'model{i}';modeldir.mkdir()
            model=modeldir/'model.onnx';model.write_bytes(f'graph{i}'.encode())
            checkpoint=model.with_suffix('.pt');checkpoint.write_bytes(f'weights{i}'.encode())
            h=hashlib.sha256(checkpoint.read_bytes()).hexdigest();self.models.append(h)
            (modeldir/'parity.json').write_text(json.dumps(dict(parity_passed=True,checkpoint_sha256=h,onnx_sha256=hashlib.sha256(model.read_bytes()).hexdigest())))
            (run/'summary.json').write_text(json.dumps(dict(source_sha256='same',person_task_effective=task,config=dict(person_model=str(model),person_task=task),counts={'in':0,'out':0})))
            (run/'tracks.jsonl').write_text(json.dumps(dict(frame=0,ids=[1],boxes=[[0,0,10,20]],door=None,door_generation=0))+'\n')
            self.runs.append(run)
        self.proof=self.root/'proof.json'
        self.proof.write_text(json.dumps(dict(original_source_unchanged=True,all_retained_tensors_exactly_equal=True,box_parity_passed=True,source_model_sha256=self.models[0],derived_model_sha256=self.models[1])))
        self.mock=patch('compare_run_exports.audit',side_effect=lambda p:dict(run=str(p),frames=1,events=[]));self.mock.start();self.addCleanup(self.mock.stop)
    def test_explicit_verified_derivation_passes(self):
        self.assertTrue(compare(*self.runs,self.proof)['passed'])
    def test_task_mismatch_without_derivation_rejected(self):
        with self.assertRaises(ValueError):compare(*self.runs)
    def test_tampered_export_graph_rejected(self):
        (self.root/'model1/model.onnx').write_bytes(b'changed')
        with self.assertRaises(AssertionError):compare(*self.runs,self.proof)
    def test_incomplete_retained_weights_proof_rejected(self):
        p=json.loads(self.proof.read_text());p['all_retained_tensors_exactly_equal']=False;self.proof.write_text(json.dumps(p))
        with self.assertRaises(AssertionError):compare(*self.runs,self.proof)
    def test_changed_door_generation_fails_parity(self):
        p=self.runs[1]/'tracks.jsonl';r=json.loads(p.read_text());r['door_generation']=1;p.write_text(json.dumps(r)+'\n')
        self.assertFalse(compare(*self.runs,self.proof)['passed'])
    def test_derivation_cannot_hide_counting_threshold_changes(self):
        p=self.runs[1]/'summary.json';s=json.loads(p.read_text());s['config']['counting']={'confirm':1};p.write_text(json.dumps(s))
        with self.assertRaises(ValueError):compare(*self.runs,self.proof)
    def test_string_false_is_not_a_verified_boolean(self):
        p=json.loads(self.proof.read_text());p['all_retained_tensors_exactly_equal']='False';self.proof.write_text(json.dumps(p))
        with self.assertRaises(AssertionError):compare(*self.runs,self.proof)
    def test_untampered_native_checkpoint_needs_no_onnx_metadata(self):
        p=self.runs[0]/'summary.json';s=json.loads(p.read_text());s['config']['person_model']=str(self.root/'model0/model.pt');p.write_text(json.dumps(s))
        (self.root/'model0/parity.json').unlink()
        self.assertTrue(compare(*self.runs,self.proof)['passed'])
    def test_native_checkpoint_changed_after_derivation_is_rejected(self):
        (self.root/'model0/model.pt').write_bytes(b'changed weights')
        with self.assertRaises(AssertionError):compare(*self.runs,self.proof)

if __name__=='__main__':unittest.main()
