import os

import logging

_logger = logging.getLogger("fileutil")

STAT_SIZE_INDEX = 6

def mkdirs(path):
    pathparts = path.split("/")

    created = []

    for i in range(3, len(pathparts)+1):
        curpath = "/".join(pathparts[0:i])
        try:
            os.mkdir(curpath)
            created += [curpath]
            _logger.info("Created %s", curpath)
        except OSError as e:
            if "file exists" in str(e):
                _logger.debug("Exists  %s", curpath)
            else: raise e

    return created

def rm_recursive(path):
    try:
        # Try as normal file
        os.remove(path)
        _logger.info("Removed file %s", path)
    except OSError:
        # Try as directory
        contents = os.listdir(path)
        for c in contents:
            rm_recursive("{}/{}".format(path,c))
        os.rmdir(path)
        _logger.info("Removed dir  %s", path)
