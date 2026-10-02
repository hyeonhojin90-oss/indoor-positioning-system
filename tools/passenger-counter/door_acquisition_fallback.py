"""Optional second detector only when acquiring a supported door on a strong bus."""
def fallback_due(chosen,valid_lock,using_fallback,bus_source):
    return chosen is None and valid_lock is None and not using_fallback and bus_source=='strong_detection'

def validate(config):
    if not isinstance(config,dict) or set(config)-{'model','imgsz'}:
        raise ValueError('Door acquisition fallback requires model/imgsz mapping')
    if not isinstance(config.get('model'),str) or not config['model']:
        raise ValueError('Missing fallback model')
    size=config.get('imgsz',640)
    if type(size) is not int or size<32 or size%32:
        raise ValueError('Fallback input must be a positive multiple of32')
    return size
