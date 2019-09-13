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
import pycom_util
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
        "signal_quality": None,
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

def lte_connect(hw):
    total_chrono.start()

    lte = None
    signal_quality = None

    with TimedStep("LTE init"):
        lte = network.LTE()

    with TimedStep("LTE attach"):
        lte.attach()
        try:
            while True:
                wdt.feed()
                if lte.isattached(): break
                if tschrono.read_ms() > 150 * 1000: raise TimeoutError("Timeout during LTE attach")
                time.sleep_ms(50)
        finally:
            try:
                signal_quality = pycom_util.lte_signal_quality(lte)
                _logger.info("LTE attached: %s. Signal quality %s", lte.isattached(), signal_quality)
                co2unit_errors.info(hw, "Comm cycle. LTE attached: {}. Signal quality {}".format(lte.isattached(), signal_quality))
            except:
                _logger.exception("While trying to measure and log signal strength")

    with TimedStep("LTE connect"):
        lte.connect()
        while True:
            wdt.feed()
            if lte.isconnected(): break
            if tschrono.read_ms() > 120 * 1000: raise TimeoutError("Timeout during LTE connect (%s)")
            time.sleep_ms(50)

    return lte, signal_quality

def lte_deinit(lte):
    if not lte: return

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
    if data:
        desc += " ({} bytes payload)".format(len(data))
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


def push_sequential(sync_dest, ou_id, cc, dirname, ss):

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
                resp = request("PUT", sync_dest, path, data=senddata, accept_statuses=[200,416])

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

def fetch_dir_list(sync_dest, ou_id, cc, dpath, recursive=False):
    path = "/ou/{id}/{dpath}?recursive={recursive}".format(\
            id=ou_id.hw_id, dpath=dpath, recursive=recursive)
    resp = request("GET", sync_dest, path, accept_statuses=[200,404])
    if resp.status_code == 200:
        dirlist = resp.json()
        return dirlist
    else:
        return None

def pull_last_dir(sync_dest, ou_id, cc, dpath, ss):
    # Find most recent update
    _logger.info("Fetching available directories in %s ...", dpath)
    dirlist = fetch_dir_list(sync_dest, ou_id, cc, dpath)
    if not dirlist:
        _logger.info("Remote %s is missing or empty", dpath)
        return False

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
    fetch_paths = fetch_dir_list(sync_dest, ou_id, cc, rpath, recursive=True)

    # Fetch each file
    _logger.info("Fetching files to %s", tmp_dir)
    for fpath in fetch_paths:
        tmp_path = "/".join([tmp_dir,fpath])
        if fileutil.isfile(tmp_path): break

        path = "/ou/{id}/{rpath}/{fpath}".format(id=ou_id.hw_id, rpath=rpath, fpath=fpath)
        wdt.feed()
        resp = request("GET", sync_dest, path)
        fileutil.mkdirs(fileutil.dirname(tmp_path), wdt=wdt)
        content = resp.content
        wdt.feed()
        with open(tmp_path, "w") as f:
            # TODO: make sure to write all
            f.write(content)
            wdt.feed()

    # When finished, move whole directory in place
    _logger.info("Moving %s into place", rpath)
    fileutil.mkdirs(dpath, wdt=wdt)
    os.rename(tmp_dir, rpath)
    wdt.feed()

    return True

def transmit_data(sync_dest, ou_id, cc, cs):
    path = "/ou/{id}/alive?site_code={sc}".format(id=ou_id.hw_id, sc=ou_id.site_code)

    try:
        path += "&rssi_raw={rssi_raw}&rssi_dbm={rssi_dbm}&ber_raw={ber_raw}".format(**cs.signal_quality)
    except:
        pass

    request("POST", sync_dest, path)

    got_updates = False

    for dirname, dirtype in cc.sync_dirs:
        if not dirname in cs.sync_states:
            cs.sync_states[dirname] = {}
        ss = cs.sync_states[dirname]

        if dirtype == "push_sequential":
            push_sequential(sync_dest, ou_id, cc, dirname, ss)
        elif dirtype == "pull_last_dir":
            updated = pull_last_dir(sync_dest, ou_id, cc, dirname, ss)
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
        raise Exception

    try:
        # Check connect backoff state and skip this round if need be
        tried, backoff = cs.connect_backoff
        """
        if tried < backoff:
            _logger.info("Skipping comm due to backoff: %s/%s", tried, backoff)
            co2unit_errors.warning(hw, "Skipping comm due to backoff: %s/%s" % (tried,backoff))
            cs.connect_backoff = [tried+1, backoff]
            return None, False
        """

        with TimedStep("Give LTE a moment to boot"):
            # LTE init seems to be successful more often if we give it time first
            time.sleep_ms(1000)

        with TimedStep("LTE init and connect"):
            try:
                # Attempt to connect
                lte, signal_quality = lte_connect(hw)
                # If connection successful, reset backoff
                cs.connect_backoff = [0, 0]
                cs.signal_quality = signal_quality
            except:
                # If connection fails, increase backoff
                backoff = min(backoff + 1, cc.connect_backoff_max)
                cs.connect_backoff = [1, backoff]
                raise

        with TimedStep("Set time from NTP", suppress_exception=True):
            ts = timeutil.fetch_ntp_time()
            hw.set_both_rtcs(ts)

        if isinstance(cc.sync_dest, str):
            sync_dests = [cc.sync_dest]
        else:
            sync_dests = cc.sync_dest

        for sync_dest in sync_dests:
            try:
                with TimedStep("Transmit data to {}".format(sync_dest)):
                    got_updates = transmit_data(sync_dest, ou_id, cc, cs)
            except Exception as e:
                co2unit_errors.record_error(hw, e, "Error transmitting to {}".format(sync_dest))

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
