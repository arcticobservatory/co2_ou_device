import fileutil
import json
import logging
import os
import seqfile

_logger = logging.getLogger("co2unit_update")
#_logger.setLevel(logging.DEBUG)

UPDATES_DIR = "updates"
UPDATES_MATCH = ("update-", '')
# Note: this filename must not match the UPDATES_MATCH pattern or else it will
# be mistaken for an update
# TODO: Move to var/
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
    _logger.debug("Update state: %s", state)
    state = Namespace(**state)
    newest_update = seqfile.last_file_in_sequence(contents, UPDATES_MATCH)

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

def update_sequence(hw):
    _logger.info("Starting check for updates...")
    hw.sync_to_most_reliable_rtc(reset_ok=True)
    hw.mount_sd_card()

    updates_dir = "/".join([hw.SDCARD_MOUNT_POINT, UPDATES_DIR])
    os.chdir(updates_dir)
    state, new_update = check_for_updates()
    if new_update:
        return install_update(state, new_update)
    else:
        return False

def reset_update_for_test(updates_dir, update_subdir):
    """
    Dumps current state to update directory so update will be idempotent, and resets updates status

    Example:

    import co2unit_update
    co2unit_update.reset_update_for_test("/sd/updates", "update-2019-06-13")
    """
    os.chdir(updates_dir)
    _logger.info("Clearing update subdirectory %s", update_subdir)
    fileutil.rm_recursive(update_subdir)
    _logger.info("Copying current code to %s", update_subdir)
    fileutil.copy_recursive("/flash", update_subdir+"/flash")
    try:
        _logger.info("Clearing update state file %s", UPDATE_STATE_FILENAME)
        os.remove(UPDATE_STATE_FILENAME)
    except Exception as e:
        _logger.warning("Error removing state file. %s:%s", type(e).__name__, e)
        pass
