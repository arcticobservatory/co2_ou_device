import logging
import os

import seqfile

_logger = logging.getLogger("fileutil")
#_logger.setLevel(logging.DEBUG)

def isfile(fpath):
    try:
        with open(fpath, "r"):
            return True
    except:
        return False

def isdir(dpath):
    try:
        os.listdir(dpath)
        return True
    except:
        return False

def dirname(path):
    pos = path.rfind("/")
    if pos == -1: pos = 0
    return path[:pos]

def mkdirs(path, wdt=None):
    if not path: return
    pathparts = path.split("/")

    created = []

    for i in range(0, len(pathparts)+1):
        curpath = "/".join(pathparts[0:i])
        try:
            os.mkdir(curpath)
            if wdt: wdt.feed()
            created += [curpath]
            _logger.info("Created %s", curpath)
        except OSError as e:
            if "file exists" in str(e):
                _logger.debug("Exists  %s", curpath)
            else: raise e

    return created

def rm_recursive(path, wdt=None):
    try:
        # Try as normal file
        os.remove(path)
        _logger.info("Removed file %s", path)
        return
    except OSError:
        pass

    try:
        # Try as directory
        contents = os.listdir(path)
        for c in contents:
            if wdt: wdt.feed()
            rm_recursive("{}/{}".format(path,c), wdt)
            if wdt: wdt.feed()
        os.rmdir(path)
        _logger.info("Removed dir  %s", path)
        return
    except OSError as e:
        if "No such file" in str(e):
            _logger.warning("Does not exist %s", path)

def copy_file(src_path, dest_path, block_size=512, wdt=None):
    buf = bytearray(block_size)
    mv = memoryview(buf)
    with open(src_path, "rb") as src:
        with open(dest_path, "wb") as dest:
            while True:
                bytes_read = src.readinto(buf)
                if wdt: wdt.feed()
                _logger.debug("Read  %4d bytes from %s", bytes_read, src_path)
                if not bytes_read:
                    break
                bytes_written = 0
                while bytes_written != bytes_read:
                    bytes_written += dest.write(mv[bytes_written:bytes_read])
                    if wdt: wdt.feed()
                    _logger.debug("Wrote %4d bytes to   %s", bytes_written, dest_path)
    _logger.info("Copied %s -> %s", src_path, dest_path)

def copy_recursive(src_path, dest_path, block_size=512, wdt=None):
    if wdt: wdt.feed()
    try:
        contents = os.listdir(src_path)
    except:
        contents = None

    if contents==None:
        copy_file(src_path, dest_path, block_size, wdt=wdt)
        if wdt: wdt.feed()

    else:
        mkdirs(dest_path, wdt=wdt)
        for child in contents:
            if wdt: wdt.feed()
            src_child = "%s/%s" % (src_path, child)
            dest_child = "%s/%s" % (dest_path, child)
            copy_recursive(src_child, dest_child, block_size, wdt=wdt)

STAT_SIZE_INDEX = const(6)

def file_size(filepath):
    return os.stat(filepath)[STAT_SIZE_INDEX]

def prep_append_file(dir=".", match=('',''), size_limit=100*1024):
    mkdirs(dir)
    target = seqfile.choose_append_file(dir, match, size_limit)
    tpath = "/".join([dir, target])
    return tpath
