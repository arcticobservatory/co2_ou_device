import logging
_logger = logging.getLogger("co2unit_update")
_logger.setLevel(logging.DEBUG)

import os
import fileutil
import json

UPDATES_MATCH = ("update-", '')
# Note: this filename must not match the UPDATES_MATCH pattern or else it will
# be mistaken for an update
UPDATE_STATE_FILENAME = "updates-state.json"

UPDATE_STATE_DEFAULTS = {
        "installed": None,
        }

class Namespace(object):
    def __init__(self, **kwargs):
        for k,v in kwargs.items():
            setattr(self, k, v)

def check_for_updates():
    """
    Look for new updates and current update status, from current dir

    Each update should be a subdirectory starting with 'update-',
    e.g. 'update-2019-06-26'.

    Update names should sort so that the newest update is last.
    """

    _logger.info("Checking for updates in %s", os.getcwd())

    contents = os.listdir()

    state = UPDATE_STATE_DEFAULTS.copy()

    if UPDATE_STATE_FILENAME in contents:
        try:
            with open(UPDATE_STATE_FILENAME) as f:
                 from_file = json.load(f)
                 _logger.debug("read %s: %s", UPDATE_STATE_FILENAME, from_file)
                 state.update(from_file)
        except ValueError as e:
            _logger.warning("Currupt %s. Proceeding with defaults", UPDATE_STATE_FILENAME)
    _logger.info("Update state: %s", state)
    state = Namespace(**state)
    newest_update = fileutil.last_file_in_sequence(contents, UPDATES_MATCH)

    if newest_update == None:
        _logger.info("No updates found")
        return (state, None)

    elif newest_update == state.installed:
        _logger.info("%s is already installed", newest_update)
        return (state, None)
    else:
        _logger.info("Found %s", newest_update)
        return (state, newest_update)

def install_update(state, update_subdir):

    updates_parent_dir = os.getcwd()

    try:
        _logger.info("Installing update from %s", update_subdir)

        contents = os.listdir(update_subdir)

        if "flash" in contents:
            _logger.info("Copying flash contents into filesystem")
            fileutil.copy_recursive(update_subdir+"/flash", "/flash")

        state.installed = update_subdir
        _logger.info("Finished installing update from %s", update_subdir)
        return True

    finally:
        serialized = json.dumps(state.__dict__)
        _logger.debug("Saving state %s: %s", UPDATE_STATE_FILENAME, serialized)
        os.chdir(updates_parent_dir)
        with open(UPDATE_STATE_FILENAME, "wt") as f:
            f.write(serialized)
        _logger.info(" State saved  %s: %s", UPDATE_STATE_FILENAME, serialized)

def check_and_install_updates(updates_dir):
    os.chdir(updates_dir)
    state, new_update = check_for_updates()
    if new_update:
        return install_update(state, new_update)
    else:
        return False
