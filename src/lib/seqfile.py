import logging

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
