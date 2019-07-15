import logging
import machine
import network
import os
import time
import ubinascii
import urequests
import usocket

import fileutil
import timeutil

_logger = logging.getLogger("co2unit_comm")

SD_ROOT = "/sd"

UNIQUE_ID = ubinascii.hexlify(machine.unique_id()).decode("ascii")
UNIQUE_ID = "co2unit-%s" % UNIQUE_ID

COMM_CONF_PATH = "ou-comm-config.json"
COMM_CONF_DEFAULTS = {
        "ou_id": UNIQUE_ID,
        "sync_dest": None,  # Expects URL like 'http://my_api_server.com:8080'
        "sync_dirs": [
            ["data/readings", "push_sequential"]
            ],
        "ntp_max_drift_secs": 4,
        }


COMM_STATE_PATH = "ou-comm-state.json"
COMM_STATE_DEFAULTS = {
        "sync_states": {}
        }

def ntp_set_time(hw, chrono, max_drift_secs=4):
    chrono.reset()
    ts = timeutil.fetch_ntp_time()
    idrift = ts - time.mktime(time.gmtime())
    if abs(idrift) < max_drift_secs:
        _logger.info("Drift from NTP: %s s; within threshold (%d s)", idrift, max_drift_secs)
    else:
        ntp_tuple = time.gmtime(ts)
        irtc = machine.RTC()
        irtc.init(ntp_tuple)
        hw.ertc().save_time()
        _logger.info("RTC set from NTP %s; drift was %d s", ntp_tuple, idrift)
    _logger.info("Got time with NTP (%d ms)", chrono.read_ms())

def push_sequential_update_sizes(dirname, pushstate):
    dirlist = os.listdir(dirname)

    for key in ["sent_file", "ack_file"]:
        try:
            fname, progress, totalsize = pushstate[key]
        except:
            fname, progress, totalsize = [None, None, None]

        if fname and fname in dirlist:
            totalsize = fileutile.file_size("{}/{}".format(dirname, fname))

        pushstate[key] = [fname, progress, totalsize]
        _logger.info("push_sequential dir %s: %09s: %20s bytes %09s of %09s", dirname, key, fname, progress, totalsize)


def transmit_data(hw, wdt=None):
    """ Transmits data

    - SD card must be mounted before calling
    """
    _logger.info("Checking data")

    chrono = machine.Timer.Chrono()
    chrono.start()

    lte = None
    sock = None

    os.chdir(SD_ROOT)

    comm_conf = fileutil.read_config_json(COMM_CONF_PATH, COMM_CONF_DEFAULTS)
    _logger.info("comm_conf : %s", comm_conf)

    comm_state = fileutil.read_config_json(COMM_STATE_PATH, COMM_STATE_DEFAULTS)
    _logger.info("comm_state: %s", comm_state)

    try:
        _logger.info("Giving LTE time to boot before initializing it...")
        time.sleep_ms(1000)

        # LTE init can sometimes hang indefinitely
        # When successful it usually takes around 3-6 seconds
        wdt.init(10*1000)

        _logger.info("Init LTE...")
        chrono.reset()
        lte = network.LTE()
        _logger.info("LTE init ok (%d ms)", chrono.read_ms())

        wdt.feed()

        #_logger.info("Doing an LTE reset for paranioa")
        #chrono.reset()
        #lte.reset()
        #_logger.info("LTE reset ok (%d ms)", chrono.read_ms())

        _logger.info("LTE attaching... (up to 2 minutes)")
        chrono.reset()
        lte.attach()
        while True:
            wdt.feed()
            if lte.isattached(): break
            if chrono.read_ms() > 150 * 1000: raise TimeoutError()
        _logger.info("LTE attach ok (%d ms). Connecting...", chrono.read_ms())

        chrono.reset()
        lte.connect()
        while True:
            wdt.feed()
            if lte.isconnected():
                break
            elif chrono.read_ms() > 120 * 1000:
                raise TimeoutError("LTE did not attach after %d ms" % chrono.read_ms())
        _logger.info("LTE connect ok (%d ms)", chrono.read_ms())

        try:
            ntp_set_time(hw, chrono, comm_conf.ntp_max_drift_secs)
        except Exception as e:
            _logger.warning("Unable to set time with NTP. %s: %s", type(e).__name__, e)

        wdt.feed()

        sync_dest = comm_conf.sync_dest
        ou_id = comm_conf.ou_id

        url = "{}/ou/{}/alive".format(sync_dest, ou_id)
        _logger.info("urequests POST %s", url)
        resp = urequests.post(url, data="")
        _logger.info("Response (%s): %s", resp.status_code, resp.text)

        for dirname, dirtype in comm_conf.sync_dirs:
            if dirtype == "push_sequential":

                if not dirname in comm_state.sync_states:
                    comm_state.sync_states[dirname] = {}

                pushstate = comm_state.sync_states[dirname]
                push_sequential_update_sizes(dirname, pushstate)

            else:
                _logger.warning("Unknown sync type for %s: %s", sdir, stype)

        wdt.feed()

        try:
            fileutil.save_config_json(COMM_STATE_PATH, comm_state)
            _logger.info("State saved: %s", comm_state)
        except:
            _logger.warning("Unable to save state: %s", comm_state)

        wdt.feed()

    finally:
        if sock:
            try:
                sock.close()
            except Exception as e:
                _logger.info("Could not close socket. %s: %s", type(e).__name__, e)

        if lte:
            try:
                if lte.isconnected():
                    chrono.reset()
                    lte.disconnect()
                    _logger.info("LTE disconnected (%d ms)", chrono.read_ms())

                wdt.feed()

                if lte.isattached():
                    chrono.reset()
                    lte.dettach()
                    _logger.info("LTE detached (%d ms)", chrono.read_ms())

                wdt.feed()
            finally:
                chrono.reset()
                lte.deinit()
                _logger.info("LTE deinit-ed (%d ms)", chrono.read_ms())

                wdt.feed()

    return lte
