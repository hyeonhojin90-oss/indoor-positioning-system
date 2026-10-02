import unittest
from types import SimpleNamespace
from runtime_threads import backend_runtime_info

class EngineBackendInfoTests(unittest.TestCase):
    def test_uninitialized_model_does_not_claim_engine_loaded(self):
        self.assertEqual(backend_runtime_info(SimpleNamespace()),{'onnx_runtime':False})
    def test_engine_context_and_gpu_device_are_reported_separately(self):
        core=SimpleNamespace(engine=True,context=object(),device='cuda:0',fp16=True,dynamic=True)
        info=backend_runtime_info(SimpleNamespace(predictor=SimpleNamespace(model=core)))
        self.assertTrue(info['execution_context_loaded']);self.assertEqual(info['device'],'cuda:0')
        self.assertFalse(info['operation_execution_profile_verified'])
        core.context=None;core.device='cpu'
        info=backend_runtime_info(SimpleNamespace(predictor=SimpleNamespace(model=core)))
        self.assertFalse(info['execution_context_loaded']);self.assertEqual(info['device'],'cpu')

if __name__=='__main__':unittest.main()
