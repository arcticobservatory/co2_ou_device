import os

import logging

_logger = logging.getLogger("fileutil")
#_logger.setLevel(logging.DEBUG)

def mkdirs(path):
    pathparts = path.split("/")

    created = []

    for i in range(0, len(pathparts)+1):
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

def copy_file(src_path, dest_path, block_size=512):
    buf = bytearray(block_size)
    mv = memoryview(buf)
    with open(src_path, "rb") as src:
        with open(dest_path, "wb") as dest:
            while True:
                bytes_read = src.readinto(buf)
                _logger.debug("Read  %4d bytes from %s", bytes_read, src_path)
                if not bytes_read:
                    break
                bytes_written = 0
                while bytes_written != bytes_read:
                    bytes_written += dest.write(mv[bytes_written:bytes_read])
                    _logger.debug("Wrote %4d bytes to   %s", bytes_written, dest_path)
    _logger.info("Copied %s -> %s", src_path, dest_path)

def copy_recursive(src_path, dest_path, block_size=512):
    try:
        contents = os.listdir(src_path)
    except:
        contents = None

    if contents==None:
        copy_file(src_path, dest_path, block_size)

    else:
        mkdirs(dest_path)
        for child in contents:
            src_child = "%s/%s" % (src_path, child)
            dest_child = "%s/%s" % (dest_path, child)
            copy_recursive(src_child, dest_child, block_size)

STAT_SIZE_INDEX = const(6)

def file_size(filepath):
    return os.stat(filepath)[STAT_SIZE_INDEX]
