import unittest
from unittest.mock import patch, Mock
from runtime_threads import configure_model_threads


class Model:
    def __init__(self):self.callbacks={}
    def add_callback(self,event,fn):self.callbacks[event]=fn


class ThreadTests(unittest.TestCase):
    def test_cpu_option_does_not_replace_cuda_onnx_session(self):
        model=Model();model.model='model.onnx'
        context=Mock();context.model.session.get_providers.return_value=['CUDAExecutionProvider','CPUExecutionProvider']
        session=context.model.session
        with patch('torch.set_num_threads'):
            configure_model_threads(model,2)
            model.callbacks['on_predict_start'](context)
        self.assertIs(context.model.session,session)
        session.get_session_options.assert_not_called()

    def test_callbacks_reassert_after_device_reset(self):
        model=Model()
        with patch('torch.set_num_threads') as setter:
            configure_model_threads(model,2)
            setter.reset_mock()
            model.callbacks['on_predict_start'](None)
            model.callbacks['on_val_start'](None)
            self.assertEqual(setter.call_count,2)
            setter.assert_called_with(2)
    def test_default_unchanged_and_invalid_rejected(self):
        model=Model();configure_model_threads(model,None)
        self.assertEqual(model.callbacks,{})
        for invalid in (True,0,33,1.5):
            with self.assertRaises(ValueError):configure_model_threads(model,invalid)
