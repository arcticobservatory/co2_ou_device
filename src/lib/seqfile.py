import logging
import os

_logger = logging.getLogger("seqfile")
#_logger.setLevel(logging.DEBUG)

def last_file_in_sequence(files, match=('','')):
    prefix, suffix = match

    files.sort()

    for i in reversed(range(0, len(files))):
        last_file = files[i]

        if not last_file.startswith(prefix) or not last_file.endswith(suffix):
            _logger.debug("%20s : Skipping non-matching file", last_file)
            continue

        return last_file
    return None

def make_sequence_filename(index, match=('','')):
    prefix, suffix = match
    try:
        # format as integer with leading zeros if possible
        return "%s%04d%s" % (prefix, index, suffix)
    except:
        # otherwise just use as a string
        return "%s%s%s" % (prefix, index, suffix)

def extract_sequence_number(filename, match=('','')):
    prefix, suffix = match
    if not filename.startswith(prefix) or not filename.endswith(suffix):
        raise Exception("Filename %s does not match pattern %s0000%s" % (filename, prefix, suffix))

    index = filename[len(prefix): -len(suffix)]
    try:
        return int(index)   # convert to integer if possible
    except ValueError as e:
        return index        # otherwise return string as is

def next_sequence_filename(filename, match=('','')):
    index = extract_sequence_number(filename, match)
    if not isinstance(index, int):
        raise Exception("Filename %s sequence part is not an integer: %s, match=%s" % (filename, index, match))
    return make_sequence_filename(index+1, match)

ST_SIZE_INDEX = 6

def choose_append_file(dir=".", match=('',''), size_limit=100*1024):
    files = os.listdir(dir)
    _logger.debug("%s", files)
    target = last_file_in_sequence(files, match)

    if not target:
        target = make_sequence_filename(0, match)
        _logger.info("%s : no target file found. Starting fresh", target)

    else:
        tpath = "/".join([dir, target])
        size = os.stat(tpath)[ST_SIZE_INDEX]

        if size < size_limit:
            _logger.info("%s : using current target file", target)
        else:
            prev = target
            target = next_sequence_filename(prev, match)
            _logger.info("%s : beginning new file. %s was over size threshold (%d / %d bytes)", target, prev, size, size_limit)

    return target
