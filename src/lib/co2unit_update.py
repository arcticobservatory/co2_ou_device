import json
import logging
import os

import configutil
import fileutil
import seqfile
import timeutil

_logger = logging.getLogger("co2unit_update")
#_logger.setLevel(logging.DEBUG)

wdt = timeutil.DummyWdt()

UPDATES_DIR = "updates"
UPDATES_MATCH = ("update-", '')
UPDATE_STATE_PATH = "var/updates-state.json"

UPDATE_STATE_DEFAULTS = {
        "installed": None,
        }

class Namespace(object):
    def __init__(self, **kwargs):
        for k,v in kwargs.items():
            setattr(self, k, v)

def check_for_updates(updates_dir):
    """
    Look for new updates and current update status, from current dir

    Each update should be a subdirectory starting with 'update-',
    e.g. 'update-2019-06-26'.

    Update names should sort so that the newest update is last.
    """

    _logger.info("Checking for updates in %s", os.getcwd())

    upstate = configutil.read_config_json(UPDATE_STATE_PATH, UPDATE_STATE_DEFAULTS)

    if not fileutil.isdir(updates_dir):
        _logger.info("Updates dir does not exist")
        return (upstate, None)

    contents = os.listdir(updates_dir)
    update_name = seqfile.last_file_in_sequence(contents, UPDATES_MATCH)

    if update_name == None:
        _logger.info("No updates found")
        return (upstate, None)

    update_path = "/".join([updates_dir, update_name])

    if update_path == upstate.installed:
        _logger.info("%s is already installed", update_path)
        return (upstate, None)

    else:
        _logger.info("Found %s", update_path)
        return (upstate, update_path)

def patch_configs(patches_path):
    _logger.info("Patching config files...")
    contents = os.listdir(patches_path)

    for pname in contents:
        ppath = "/".join([patches_path, pname])
        target = "conf/" + pname
        fileutil.mkdirs("conf", wdt=wdt)
        with open(target) as f:
            targ_dict = json.load(f)
            wdt.feed()
        with open(ppath) as f:
            patch_dict = json.load(f)
            wdt.feed()
        targ_dict.update(patch_dict)
        with open(target, "w") as f:
            f.write(json.dumps(targ_dict))
            wdt.feed()
        _logger.info("New %s: %s", target, targ_dict)

def install_update(upstate, subpath):

    try:
        _logger.info("Installing update from %s", subpath)

        contents = os.listdir(subpath)

        if "flash" in contents:
            _logger.info("Copying new source into flash filesystem...")
            fileutil.copy_recursive(subpath+"/flash", "/flash", wdt=wdt)

        if "conf_patch" in contents:
            patch_configs(subpath + "/conf_patch")

        upstate.installed = subpath
        _logger.info("Finished installing update from %s", subpath)
        return True

    finally:
        configutil.save_config_json(UPDATE_STATE_PATH, upstate)

def update_sequence(hw):
    _logger.info("Starting check for updates...")
    hw.sync_to_most_reliable_rtc(reset_ok=True)
    hw.mount_sd_card()

    os.chdir(hw.SDCARD_MOUNT_POINT)
    upstate, new_update = check_for_updates(UPDATES_DIR)
    if new_update:
        return install_update(upstate, new_update)
    else:
        return False

def reset_update_for_test(subpath):
    """
    Dumps current state to update directory so update will be idempotent, and resets updates status

    Example:

        hw.power_peripherals(True)
        hw.mount_sd_card()
        import co2unit_update
        co2unit_update.wdt = wdt
        co2unit_update.reset_update_for_test("/sd/updates/update-2019-07-26")
        import os
        os.remove("/sd/var/updates-state.json")
    """
    import machine
    _logger.info("Clearing update subdirectory %s", subpath)
    fileutil.rm_recursive(subpath, wdt=wdt)
    _logger.info("Copying current code to %s", subpath)
    fileutil.copy_recursive("/flash", subpath+"/flash", wdt=wdt)
    rand_site_code = "rand_site_%04x" % (machine.rng() % (16**4))
    _logger.info("Adding a randomized conf_patch: %s", rand_site_code)
    fileutil.mkdirs(subpath + "/conf_patch")
    with open(subpath + "/conf_patch/ou-id.json", "w") as f:
        patch = { "site_code": rand_site_code }
        f.write(json.dumps(patch))
