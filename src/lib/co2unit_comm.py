import logging
import machine
import network
import os
import time
import ubinascii
import uio
import urequests
import usocket

import configutil
import fileutil
import timeutil

_logger = logging.getLogger("co2unit_comm")
#_logger.setLevel(logging.DEBUG)

UNIQUE_ID = ubinascii.hexlify(machine.unique_id()).decode("ascii")
UNIQUE_ID = "co2unit-%s" % UNIQUE_ID

COMM_CONF_PATH = "conf/ou-comm-config.json"
COMM_CONF_DEFAULTS = {
        "ou_id": UNIQUE_ID,
        "sync_dest": None,  # Expects URL like 'http://my_api_server.com:8080'
        "sync_dirs": [
            ["data/readings", "push_sequential"],
            ["errors", "push_sequential"],
            ],
        "ntp_max_drift_secs": 4,
        "send_chunk_size": 4*1024,
        }

STATE_DIR = "var"
COMM_STATE_PATH = STATE_DIR + "/ou-comm-state.json"
COMM_STATE_DEFAULTS = {
        "sync_states": {}
        }

class TimedStep(object):
    def __init__(self, chrono, desc="", suppress_exception=False):
        self.chrono = chrono
        self.desc = desc
        self.suppress_exception = suppress_exception

    def __enter__(self):
        self.chrono.reset()
        _logger.info("%s ...", self.desc)

    def __exit__(self, exc_type, exc_value, traceback):
        elapsed = self.chrono.read_ms()
        if exc_type:
            _logger.warning("%s failed (%d ms). %s: %s", self.desc, elapsed, exc_type.__name__, exc_value)
            if self.suppress_exception:
                return True
        else:
            _logger.info("%s OK (%d ms)", self.desc, elapsed)

def lte_connect(wdt):
    chrono = machine.Timer.Chrono()
    chrono.start()

    # Set watchdog timer to reboot if LTE init hangs.
    # LTE init can sometimes hang indefinitely.
    # When successful it usually takes around 3-6 seconds.
    wdt.init(10*1000)

    with TimedStep(chrono, "LTE init"):
        lte = network.LTE()
        wdt.feed()

    with TimedStep(chrono, "LTE attach"):
        lte.attach()
        while True:
            wdt.feed()
            if lte.isattached(): break
            if chrono.read_ms() > 150 * 1000: raise TimeoutError("Timeout during LTE attach")
            time.sleep_ms(50)

    with TimedStep(chrono, "LTE connect"):
        lte.connect()
        while True:
            wdt.feed()
            if lte.isconnected(): break
            if chrono.read_ms() > 120 * 1000: raise TimeoutError("Timeout during LTE connect")
            time.sleep_ms(50)

    return lte

def lte_deinit(lte, wdt):
    if not lte: return

    chrono = machine.Timer.Chrono()
    chrono.start()

    # LTE disconnect often takes a few seconds
    # Set a more forgiving watchdog timer timeout
    wdt.init(20*1000)

    try:
        if lte.isconnected():
            with TimedStep(chrono, "LTE disconnect"):
                lte.disconnect()

        wdt.feed()

        if lte.isattached():
            with TimedStep(chrono, "LTE detach"):
                lte.detach()

        wdt.feed()

    finally:
        with TimedStep(chrono, "LTE deinit"):
            lte.deinit()

        wdt.feed()

class PushSequentialState(object):
    def __init__(self, dirname, fname=None, progress=None, totalsize=None):
        self.fname = fname
        self.progress = progress
        self.totalsize = totalsize

        self.dirname = dirname
        # Make sure directory exists before trying to read it
        fileutil.mkdirs(dirname)
        self.dirlist = os.listdir(dirname)
        self.dirlist.sort()
        if not self.dirlist:
            _logger.info("%s: dir is empty. Nothing to push", dirname)

        self.dirindex = None
        self.update_by_fname(fname, progress)

    def to_list(self):
        return [self.fname, self.progress, self.totalsize]

    def __str__(self):
        return str(self.to_list())

    def fpath(self):
        return "/".join([self.dirname, self.fname])

    def update_by_fname(self, fname, progress=None):
        if not fname:
            self.update_by_dirindex(0)
        elif fname not in self.dirlist:
            _logger.warning("%s not in %s, starting at beggining of dir", fname, self.dirname)
            self.update_by_dirindex(0)
        else:
            self.fname = fname
            self.progress = progress
            self.update_by_dirindex(self.dirlist.index(fname))

    def update_by_dirindex(self, dirindex):
        self.dirindex = dirindex
        if self.dirindex < len(self.dirlist):
            fname = self.dirlist[dirindex]
            if fname != self.fname:
                self.fname = fname
                self.progress = 0
            self.totalsize = os.stat(self.fpath())[6]

    def update_to_next_file(self):
        self.update_by_dirindex(self.dirindex + 1)

    def add_progress(self, p_add):
        self.progress += p_add

    def file_complete(self):
        assert self.progress <= self.totalsize, "progress greater than totalsize: {}".format(self)
        return self.progress == self.totalsize

    def dir_complete(self):
        assert self.dirindex <= len(self.dirlist), "dirindex out of bounds"
        return self.dirindex == len(self.dirlist)


def push_sequential(cc, dirname, ss, wdt):
    chrono = machine.Timer.Chrono()
    chrono.start()

    wdt.feed()

    key = "ack_file"
    if key in ss:
        pushstate = PushSequentialState(dirname, *ss[key])
    else:
        pushstate = PushSequentialState(dirname)

    try:
        buf = bytearray(cc.send_chunk_size)
        mv = memoryview(buf)

        while not pushstate.dir_complete():

            with open(pushstate.fpath(), "rb") as f:

                while not pushstate.file_complete():
                    _logger.info("Sending from %s", pushstate)
                    with TimedStep(chrono, "Reading data"):
                        f.seek(pushstate.progress)
                        readbytes = f.readinto(buf)
                        senddata = mv[:readbytes]
                        wdt.feed()

                    if _logger.level <= logging.DEBUG:
                        s = uio.BytesIO(mv)#[:40])
                        _logger.debug("Read data: '%s' ...", s.getvalue())
                        wdt.feed()

                    url = "{}/ou/{}/push-sequential/{}?offset={}".format(\
                            cc.sync_dest, cc.ou_id, pushstate.fpath(), pushstate.progress)

                    with TimedStep(chrono, "Sending data: %s (%d bytes)" % (url, readbytes)):
                        resp = urequests.put(url, data=senddata)
                        if resp.status_code != 200:
                            raise Exception("Error sending data: %s --- %s %s" % (url, resp.status_code, resp.content))
                        _logger.info("Response (%s): %s", resp.status_code, repr(resp.content))
                        pushstate.add_progress(readbytes)
                        wdt.feed()

                        parsed = resp.json()
                        if "ack_file" in parsed:
                            fname, progress, totalize = parsed["ack_file"]
                            _logger.info("New progress in server response: %s, %d", fname, progress)

            # TODO: quit after a timeout
            pushstate.update_to_next_file()
            wdt.feed()

        _logger.info("%s: all synced", dirname)
    finally:
        ss[key] = pushstate.to_list()
        _logger.info("%s: %s", dirname, ss[key])

def transmit_data(cc, cs, wdt):
    chrono = machine.Timer.Chrono()
    chrono.start()

    with TimedStep(chrono, "Sending alive ping"):
        url = "{}/ou/{}/alive".format(cc.sync_dest, cc.ou_id)
        _logger.info("urequests POST %s", url)
        resp = urequests.post(url)
        _logger.info("Response (%s): %s", resp.status_code, resp.text)

    for dirname, dirtype in cc.sync_dirs:
        if not dirname in cs.sync_states:
            cs.sync_states[dirname] = {}
        ss = cs.sync_states[dirname]

        if dirtype == "push_sequential":
            push_sequential(cc, dirname, ss, wdt)
        else:
            _logger.warning("Unknown sync type for %s: %s", sdir, stype)
        _logger.info("ss: %s", ss)

def comm_sequence(hw):
    """ Transmits data

    - SD card must be mounted before calling
    """
    _logger.info("Starting communication sequence...")

    wdt = machine.WDT(timeout=10*1000)

    chrono = machine.Timer.Chrono()
    chrono.start()

    lte = None

    os.chdir(hw.SDCARD_MOUNT_POINT)

    cc = configutil.read_config_json(COMM_CONF_PATH, COMM_CONF_DEFAULTS)
    _logger.info("comm_conf : %s", cc)

    cs = configutil.read_config_json(COMM_STATE_PATH, COMM_STATE_DEFAULTS)
    _logger.info("comm_state: %s", cs)

    if not cc.sync_dest:
        _logger.error("No sync destination")
        return

    try:
        # LTE init seems to be successful more often if we give it time first
        _logger.info("Giving LTE time to boot before initializing it...")
        time.sleep_ms(1000)
        wdt.feed()

        with TimedStep(chrono, "LTE init and connect"):
            lte = lte_connect(wdt)
            wdt.feed()

        with TimedStep(chrono, "Set time from NTP", suppress_exception=True):
            ts = timeutil.fetch_ntp_time()
            hw.set_both_rtcs(ts)
            wdt.feed()

        with TimedStep(chrono, "Transmit data"):
            transmit_data(cc, cs, wdt)
            wdt.feed()

    finally:
        with TimedStep(chrono, "Save comm state", suppress_exception=True):
            fileutil.mkdirs(STATE_DIR)
            configutil.save_config_json(COMM_STATE_PATH, cs)
            _logger.info("State saved to %s: %s", COMM_STATE_PATH, cs)
            wdt.feed()

        with TimedStep(chrono, "LTE disconnect and deinit"):
            lte_deinit(lte, wdt)
            wdt.feed()

    return lte

def reset_state():
    os.remove(COMM_STATE_PATH)
