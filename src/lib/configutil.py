import json
import logging

_logger = logging.getLogger("configutil")
#_logger.setLevel(logging.DEBUG)

class Namespace(object):
    """ Converts a dictionary to an object with attribute access """
    def __init__(self, **kwargs):
        for k,v in kwargs.items():
            setattr(self, k, v)
    def __str__(self):
        return "Namespace(**%s)" % str(self.__dict__)

def read_config_json(filename, defaults={}):
    """ Reads a JSON config file, adds defaults, and converts to a Namespace object """
    config = defaults.copy()
    try:
        with open(filename) as f:
            from_file = json.load(f)
            _logger.debug("%s: %s", filename, from_file)
            config.update(from_file)
    except OSError as e:
        if "ENOENT" in str(e):
            _logger.info("%s missing. Proceeding with defaults", filename)
        else:
            raise e

    config = Namespace(**config)
    _logger.info("%s: %s", filename, config)
    return config

def save_config_json(filename, data):
    with open(filename, "wt") as f:
        f.write(json.dumps(data.__dict__))
