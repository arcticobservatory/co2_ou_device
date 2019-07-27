import logging
import machine
import network
import os
import time
import uio
import urequests

import co2unit_errors
import co2unit_id
import configutil
import fileutil
import seqfile
import timeutil

_logger = logging.getLogger("co2unit_comm")
#_logger.setLevel(logging.DEBUG)

wdt = timeutil.DummyWdt()

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
    time_up = total_chrono.read() > cc.total_connect_secs_max
    if time_up:
        _logger.warning("Hit total time limit (%d s)", cc.total_connect_secs_max)
    return time_up

tschrono = machine.Timer.Chrono()
tschrono.start()

class TimedStep(object):
    def __init__(self, desc="", suppress_exception=False):
        self.desc = desc
        self.suppress_exception = suppress_exception

    def __enter__(self):
        wdt.feed()
        tschrono.reset()
        _logger.info("%s ...", self.desc)

    def __exit__(self, exc_type, exc_value, traceback):
        elapsed = tschrono.read_ms()
        wdt.feed()
        if exc_type:
            _logger.warning("%s failed (%d ms). %s: %s", self.desc, elapsed, exc_type.__name__, exc_value)
            if self.suppress_exception:
                return True
        else:
            _logger.info("%s OK (%d ms)", self.desc, elapsed)

def lte_connect():
    total_chrono.start()

    # Set watchdog timer to reboot if LTE init hangs.
    # LTE init can sometimes hang indefinitely.
    # When successful it usually takes around 3-6 seconds.
    wdt.init(10*1000)

    with TimedStep("LTE init"):
        lte = network.LTE()

    with TimedStep("LTE attach"):
        lte.attach()
        while True:
            wdt.feed()
            if lte.isattached(): break
            if tschrono.read_ms() > 150 * 1000: raise TimeoutError("Timeout during LTE attach")
            time.sleep_ms(50)

    with TimedStep("LTE connect"):
        lte.connect()
        while True:
            wdt.feed()
            if lte.isconnected(): break
            if tschrono.read_ms() > 120 * 1000: raise TimeoutError("Timeout during LTE connect")
            time.sleep_ms(50)

    return lte

def lte_deinit(lte):
    if not lte: return

    # LTE disconnect often takes a few seconds
    # Set a more forgiving watchdog timer timeout
    wdt.init(20*1000)

    try:
        if lte.isconnected():
            with TimedStep("LTE disconnect"):
                lte.disconnect()

        if lte.isattached():
            with TimedStep("LTE detach"):
                lte.detach()

    finally:
        with TimedStep("LTE deinit"):
            lte.deinit()

def request(method, host, path, data=None, json=None, headers={}, accept_statuses=[200]):
    url = host + path
    desc = " ".join([method,url])
    with TimedStep(desc):
        resp = urequests.request(method, url, data, json, headers)
        wdt.feed()
        resp.content
        wdt.feed()
        if resp.status_code not in accept_statuses:
            raise Exception("{} {} {}".format(desc, resp.status_code, repr(resp.content)[:100]))
        if _logger.isEnabledFor(logging.INFO):
            _logger.info("%s %s %s", desc, resp.status_code, repr(resp.content)[:100])
        wdt.feed()
        return resp

class PushSequentialState(object):
    def __init__(self, dirname, fname=None, progress=None, totalsize=None):
        self.fname = fname
        self.progress = progress
        self.totalsize = totalsize

        self.dirname = dirname
        # Make sure directory exists before trying to read it
        fileutil.mkdirs(dirname, wdt=wdt)
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


def push_sequential(ou_id, cc, dirname, ss):

    with TimedStep("Determine current sync state"):
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

                if total_time_up(cc): return

                with TimedStep("Reading data %s" % pushstate):
                    with open(pushstate.fpath(), "rb") as f:
                        f.seek(pushstate.progress)
                        readbytes = f.readinto(buf)
                    senddata = mv[:readbytes]
                    _logger.debug("%s read %d bytes", pushstate.fpath(), readbytes)

                if _logger.level <= logging.DEBUG:
                    s = uio.BytesIO(mv)#[:40])
                    _logger.debug("Read data: '%s' ...", s.getvalue())

                path = "/ou/{id}/push-sequential/{fpath}?offset={progress}".format(\
                        id=ou_id.hw_id, fpath=pushstate.fpath(), progress=pushstate.progress)
                resp = request("PUT", cc.sync_dest, path, data=senddata, accept_statuses=[200,416])

                if resp.status_code == 200:
                    pushstate.add_progress(readbytes)

                parsed = resp.json()
                if "ack_file" in parsed:
                    fname, progress, totalize = parsed["ack_file"]
                    if fname != pushstate.fname or progress != pushstate.progress:
                        _logger.info("New progress in server response: %s, %d", fname, progress)
                        pushstate.update_by_fname(fname, progress)

            pushstate.update_to_next_file()

        _logger.info("%s: all synced", dirname)
    finally:
        ss[key] = pushstate.to_list()
        _logger.info("%s: %s", dirname, ss[key])

def fetch_dir_list(ou_id, cc, dpath, recursive=False):
    path = "/ou/{id}/{dpath}?recursive={recursive}".format(\
            id=ou_id.hw_id, dpath=dpath, recursive=recursive)
    resp = request("GET", cc.sync_dest, path)
    dirlist = resp.json()
    return dirlist

def pull_last_dir(ou_id, cc, dpath, ss):
    # Find most recent update
    _logger.info("Fetching available directories in %s ...", dpath)
    dirlist = fetch_dir_list(ou_id, cc, dpath)
    most_recent = seqfile.last_file_in_sequence(dirlist)
    _logger.info("Latest in %s: %s", dpath, most_recent)

    if not most_recent:
        _logger.info("Nothing to fetch")
        return False

    # Get list of files in update
    rpath = "{dpath}/{most_recent}".format(dpath=dpath, most_recent=most_recent)
    if fileutil.isdir(rpath):
        _logger.info("Already have %s, skipping", rpath)
        return False

    _logger.info("Getting list of files in %s ...", rpath)
    tmp_dir = "tmp/" + rpath
    fetch_paths = fetch_dir_list(ou_id, cc, rpath, recursive=True)

    # Fetch each file
    _logger.info("Fetching files to %s", tmp_dir)
    for fpath in fetch_paths:
        tmp_path = "/".join([tmp_dir,fpath])
        if fileutil.isfile(tmp_path): break

        path = "/ou/{id}/{rpath}/{fpath}".format(id=ou_id.hw_id, rpath=rpath, fpath=fpath)
        resp = request("GET", cc.sync_dest, path)
        fileutil.mkdirs(fileutil.dirname(tmp_path), wdt=wdt)
        with open(tmp_path, "w") as f:
            # TODO: make sure to write all
            f.write(resp.content)
            wdt.feed()

    # When finished, move whole directory in place
    _logger.info("Moving %s into place", rpath)
    fileutil.mkdirs(dpath, wdt=wdt)
    os.rename(tmp_dir, rpath)
    wdt.feed()

    return True

def transmit_data(ou_id, cc, cs):
    path = "/ou/{id}/alive".format(id=ou_id.hw_id)
    request("POST", cc.sync_dest, path)

    got_updates = False

    for dirname, dirtype in cc.sync_dirs:
        if not dirname in cs.sync_states:
            cs.sync_states[dirname] = {}
        ss = cs.sync_states[dirname]

        if dirtype == "push_sequential":
            push_sequential(ou_id, cc, dirname, ss)
        elif dirtype == "pull_last_dir":
            updated = pull_last_dir(ou_id, cc, dirname, ss)
            got_updates = got_updates or updated
        else: _logger.warning("Unknown sync type for %s: %s", sdir, stype)
        _logger.info("ss[%s]: %s", dirname, ss)

    return got_updates

def comm_sequence(hw):
    """ Transmits data

    - SD card must be mounted before calling
    """
    _logger.info("Starting communication sequence...")

    hw.sync_to_most_reliable_rtc(reset_ok=True)
    hw.mount_sd_card()

    lte = None
    got_updates = False

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

        with TimedStep("Give LTE a moment to boot"):
            # LTE init seems to be successful more often if we give it time first
            time.sleep_ms(1000)

        with TimedStep("LTE init and connect"):
            try:
                # Attempt to connect
                lte = lte_connect()
                # If connection successful, reset backoff
                cs.connect_backoff = [0, 0]
            except:
                # If connection fails, increase backoff
                backoff = min(backoff + 1, cc.connect_backoff_max)
                cs.connect_backoff = [1, backoff]
                raise

        with TimedStep("Set time from NTP", suppress_exception=True):
            ts = timeutil.fetch_ntp_time()
            hw.set_both_rtcs(ts)

        with TimedStep("Transmit data"):
            got_updates = transmit_data(ou_id, cc, cs)

    finally:
        with TimedStep("Save comm state", suppress_exception=True):
            fileutil.mkdirs(STATE_DIR, wdt=wdt)
            configutil.save_config_json(COMM_STATE_PATH, cs)
            _logger.info("State saved to %s: %s", COMM_STATE_PATH, cs)

        with TimedStep("LTE disconnect and deinit"):
            lte_deinit(lte)

    return lte, got_updates

def reset_state():
    os.remove(COMM_STATE_PATH)
