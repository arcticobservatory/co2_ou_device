import logging
import machine
import network
import os
import time
import ubinascii
import uio
import urequests
import usocket

import co2unit_errors
import co2unit_id
import configutil
import fileutil
import seqfile
import timeutil

_logger = logging.getLogger("co2unit_comm")
#_logger.setLevel(logging.DEBUG)

COMM_CONF_PATH = "conf/ou-comm-config.json"
COMM_CONF_DEFAULTS = {
        "sync_dest": None,  # Expects URL like 'http://my_api_server.com:8080'
        "sync_dirs": [
            ["data/readings", "push_sequential"],
            ["errors", "push_sequential"],
            ["updates", "pull_last_dir"],
            ],
        "ntp_max_drift_secs": 4,
        "send_chunk_size": 4*1024,
        "total_connect_secs_max": 60*5,
        "connect_backoff_max": 7,
        }

STATE_DIR = "var"
COMM_STATE_PATH = STATE_DIR + "/ou-comm-state.json"
COMM_STATE_DEFAULTS = {
        "sync_states": {},
        "connect_backoff": [0, 0],
        }

total_chrono = machine.Timer.Chrono()

def total_time_up(cc):
    return total_chrono.read() > cc.total_connect_secs_max

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
    total_chrono.start()

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
        return self.dirindex == len(self.dirlist)


def push_sequential(ou_id, cc, dirname, ss, wdt):
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
            while not pushstate.file_complete():

                if total_time_up(cc):
                    _logger.warning("Time up before finished sending. Quitting for now.")
                    return

                with TimedStep(chrono, "Reading data %s" % pushstate):
                    with open(pushstate.fpath(), "rb") as f:
                        f.seek(pushstate.progress)
                        readbytes = f.readinto(buf)
                    senddata = mv[:readbytes]
                    _logger.debug("%s read %d bytes", pushstate.fpath(), readbytes)
                    wdt.feed()

                if _logger.level <= logging.DEBUG:
                    s = uio.BytesIO(mv)#[:40])
                    _logger.debug("Read data: '%s' ...", s.getvalue())
                    wdt.feed()

                url = "{}/ou/{}/push-sequential/{}?offset={}".format(\
                        cc.sync_dest, ou_id.hw_id, pushstate.fpath(), pushstate.progress)

                with TimedStep(chrono, "Sending data: %s (%d bytes)" % (url, readbytes)):
                    resp = urequests.put(url, data=senddata)
                    _logger.info("Response (%s): %s", resp.status_code, repr(resp.content)[0:100])
                    wdt.feed()

                    if resp.status_code == 200:
                        pushstate.add_progress(readbytes)

                    parsed = resp.json()
                    if "ack_file" in parsed:
                        fname, progress, totalize = parsed["ack_file"]
                        _logger.info("New progress in server response: %s, %d", fname, progress)
                        pushstate.update_by_fname(fname, progress)
                    wdt.feed()

                    if resp.status_code != 200:
                        raise Exception("Error sending data: %s --- %s %s" % (url, resp.status_code, repr(resp.content)[0:300]))

            # TODO: quit after a timeout
            pushstate.update_to_next_file()
            wdt.feed()

        _logger.info("%s: all synced", dirname)
    finally:
        ss[key] = pushstate.to_list()
        _logger.info("%s: %s", dirname, ss[key])

def fetch_dir_list(ou_id, cc, dirname, recursive=False):
    chrono = machine.Timer.Chrono()
    chrono.start()

    url = "{}/ou/{}/{}?recursive={}".format(cc.sync_dest, ou_id.hw_id, dirname, recursive)
    with TimedStep(chrono, "fetching dir list: %s" % (url)):
        resp = urequests.get(url)
        _logger.info("response (%s): %s", resp.status_code, repr(resp.content)[0:100])

        if resp.status_code != 200:
            raise exception("error: %s --- %s %s" % (url, resp.status_code, repr(resp.content)[0:300]))

        dirlist = resp.json()
        return dirlist

def pull_last_dir(ou_id, cc, dirname, ss, wdt):
    chrono = machine.Timer.Chrono()
    chrono.start()

    wdt.feed()

    # Get dir list
    dirlist = fetch_dir_list(ou_id, cc, dirname)
    most_recent = seqfile.last_file_in_sequence(dirlist)
    _logger.info("Latest in %s: %s", dirname, dirlist)
    wdt.feed()

    # Pull into temp zone
    remote_dir = "/".join([dirname, most_recent])
    dirlist = fetch_dir_list(ou_id, cc, dirname, recursive=True)
    wdt.feed()

    # If finished, move into updates

def transmit_data(ou_id, cc, cs, wdt):
    chrono = machine.Timer.Chrono()
    chrono.start()

    url = "{}/ou/{}/alive".format(cc.sync_dest, ou_id.hw_id)
    with TimedStep(chrono, "Sending alive ping: %s" % url):
        resp = urequests.post(url)
        _logger.info("Response (%s): %s", resp.status_code, resp.text)

    for dirname, dirtype in cc.sync_dirs:
        if not dirname in cs.sync_states:
            cs.sync_states[dirname] = {}
        ss = cs.sync_states[dirname]

        if dirtype == "push_sequential": push_sequential(ou_id, cc, dirname, ss, wdt)
        elif dirtype == "pull_last_dir": pull_last_dir(ou_id, cc, dirname, ss, wdt)
        else: _logger.warning("Unknown sync type for %s: %s", sdir, stype)
        _logger.info("ss[%s]: %s", dirname, ss)

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

    ou_id = configutil.read_config_json(co2unit_id.OU_ID_PATH, co2unit_id.OU_ID_DEFAULTS)
    cc = configutil.read_config_json(COMM_CONF_PATH, COMM_CONF_DEFAULTS)
    cs = configutil.read_config_json(COMM_STATE_PATH, COMM_STATE_DEFAULTS)

    if not cc.sync_dest:
        _logger.error("No sync destination")
        return

    try:
        # Check connect backoff state and skip this round if need be
        tried, backoff = cs.connect_backoff
        if tried < backoff:
            _logger.info("Skipping comm due to backoff: %s/%s", tried, backoff)
            co2unit_errors.warning(hw, "Skipping comm due to backoff: %s/%s" % (tried,backoff))
            cs.connect_backoff = [tried+1, backoff]
            return

        with TimedStep(chrono, "Give LTE a moment to boot"):
            # LTE init seems to be successful more often if we give it time first
            time.sleep_ms(1000)
            wdt.feed()

        with TimedStep(chrono, "LTE init and connect"):
            try:
                # Attempt to connect
                lte = lte_connect(wdt)
                # If connection successful, reset backoff
                cs.connect_backoff = [0, 0]
                wdt.feed()
            except:
                # If connection fails, increase backoff
                backoff = min(backoff + 1, cc.connect_backoff_max)
                cs.connect_backoff = [1, backoff]
                raise

        with TimedStep(chrono, "Set time from NTP", suppress_exception=True):
            ts = timeutil.fetch_ntp_time()
            hw.set_both_rtcs(ts)
            wdt.feed()

        with TimedStep(chrono, "Transmit data"):
            transmit_data(ou_id, cc, cs, wdt)
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
