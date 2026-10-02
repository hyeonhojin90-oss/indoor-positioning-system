"""Reapply requested CPU threads after Ultralytics device initialization."""
def configure_model_threads(model, threads):
    if threads is None:return
    if type(threads) is not int or not 1<=threads<=32:
        raise ValueError('CPU threads must be an integer in 1..32')
    import torch
    from pathlib import Path
    weights=getattr(model,'model',None)
    onnx_path=str(weights) if isinstance(weights,(str,Path)) and str(weights).lower().endswith('.onnx') else None
    def apply(context):
        torch.set_num_threads(threads)
        # PyTorch limits do not control ORT. A CPU-only ONNX predictor needs
        # its own public SessionOptions. Never replace a CUDA/TensorRT session.
        core=getattr(context,'model',None)
        session=getattr(core,'session',None)
        if onnx_path and session is not None and session.get_providers()==['CPUExecutionProvider']:
            if session.get_session_options().intra_op_num_threads!=threads:
                import onnxruntime as ort
                options=ort.SessionOptions()
                options.intra_op_num_threads=threads
                options.inter_op_num_threads=1
                core.session=ort.InferenceSession(onnx_path,options,providers=['CPUExecutionProvider'])
                if not core.dynamic:
                    # Static Ultralytics exports bind CPU output buffers too;
                    # bindings belong to their creating session and must move together.
                    core.io=core.session.io_binding()
                    for name,tensor in zip(core.output_names,core.bindings):
                        core.io.bind_output(name=name,device_type='cpu',device_id=0,
                                            element_type=tensor.numpy().dtype,
                                            shape=tuple(tensor.shape),buffer_ptr=tensor.data_ptr())
    # select_device() resets torch threads. These public callbacks execute
    # after device setup, including separate validation predictor sessions.
    for event in ('on_predict_start','on_pretrain_routine_start','on_train_start',
                  'on_train_epoch_start','on_val_start'):
        model.add_callback(event,apply)
    apply(None)


def backend_runtime_info(model):
    core=getattr(getattr(model,'predictor',None),'model',None)
    session=getattr(core,'session',None)
    if getattr(core,'engine',False):
        return {'onnx_runtime':False,'tensorrt_engine':True,
                'device':str(getattr(core,'device',None)),
                'fp16':getattr(core,'fp16',None),'dynamic':getattr(core,'dynamic',None),
                'execution_context_loaded':getattr(core,'context',None) is not None,
                'operation_execution_profile_verified':False}
    if session is None:return {'onnx_runtime':False}
    options=session.get_session_options()
    return {'onnx_runtime':True,'providers':session.get_providers(),
            'intra_op_num_threads':options.intra_op_num_threads,
            'inter_op_num_threads':options.inter_op_num_threads,
            'note':'0 means runtime-selected thread count, not zero worker threads.'}
