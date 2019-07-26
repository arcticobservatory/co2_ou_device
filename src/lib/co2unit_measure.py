import logging
import machine
import os
import time

import co2unit_id
import configutil
import explorir
import fileutil

_logger = logging.getLogger("co2unit_measure")
#_logger.setLevel(logging.DEBUG)

def read_sensors(hw, flash_count=0):
    wdt = machine.WDT(timeout=10*1000)

    rtime = time.gmtime()
    chrono = machine.Timer.Chrono()
    chrono.start()

    # Notes
    #
    # Temperature: Reading temperature is asynchronous. You call a method to
    # start it, and then read it later. Spec says 750 ms max.
    #
    # CO2: The sensor needs a little time to boot after power-off before it
    # will start responding to UART commands. In tests, about 165 ms seems to
    # work. But even after that, it will return wild readings at first. Need to
    # take a few readings until they settle.
    #
    # Experience shows that it's the first two that are way off, either 0 (min)
    # or 200010 (the max)

    etemp_reading = None
    etemp_ms = None

    co2_readings = [None] * 10
    co2_i = 0
    co2_ms = None

    # Start temperature readings
    try:
        _logger.debug("Starting external temp read. Can take up to 750ms.")
        etemp = hw.etemp
        etemp.start_conversion()
    except Exception as e:
        _logger.error("Unexpected error starting etemp reading. %s: %s", type(e).__name__, e)

    # Give CO2 sensor time to boot up after power-on
    time.sleep_ms(200)

    # Init communication with CO2 sensor
    try:
        _logger.debug("Init CO2 sensor...")
        co2 = hw.co2
        co2.set_mode(explorir.EXPLORIR_MODE_POLLING);
    except Exception as e:
        _logger.error("Unexpected error initializing CO2 sensor. %s: %s", type(e).__name__, e)

    def try_read_co2_sensor():
        try:
            co2_readings[co2_i] = co2.read_co2()    # [] = will propagate
            co2_ms = chrono.read_ms()               #    = will NOT propagate
            _logger.info("CO2 reading #%d: %6d ppm at %4d ms", co2_i, co2_readings[co2_i], co2_ms)
        except Exception as e:
            _logger.error("Unexpected error during CO2 sensor reading #%d. %s: %s", co2_i, type(e).__name__, e)
        finally:
            co2_i += 1                              #   += will propagate

    # Do throwaway reads of CO2 while waiting for temperature
    try_read_co2_sensor()
    time.sleep_ms(500)
    wdt.feed()
    try_read_co2_sensor()

    # Read temperature
    try:
        _logger.debug("Waiting for external temp read...")
        while not etemp_reading:
            etemp_reading = etemp.read_temp_async()
            etemp_ms = chrono.read_ms()
            _logger.info("etemp reading : %6.3f C   at %4d ms", etemp_reading, etemp_ms)
            if not etemp_reading and etemp_ms > 1000:
                _logger.error("Timeout reading external temp sensor after %d ms", etemp_ms)
                break
            time.sleep_ms(5)
            wdt.feed()
    except Exception as e:
        _logger.error("Unexpected error waiting for etemp reading. %s: %s", type(e).__name__, e)

    # Do more reads of CO2 sensor
    for _ in range(co2_i, len(co2_readings)):
        time.sleep_ms(500)
        wdt.feed()
        try_read_co2_sensor()
    # co2_ms did not propagate like the others, so get it again
    co2_ms = chrono.read_ms()

    reading = {
            "rtime":    rtime,
            "co2":      co2_readings,
            "co2_ms":   co2_ms,
            "etemp":    etemp_reading,
            "etemp_ms": etemp_ms,
            "flash_count": flash_count,
            }
    return reading

def make_row(ou_id, reading):
    (YY, MM, DD, hh, mm, ss, _, _) = reading["rtime"]
    dateval = "{:04}-{:02}-{:02}".format(YY,MM,DD)
    timeval = "{:02}:{:02}:{:02}".format(hh,mm,ss)
    co2s = reading["co2"]
    etemp = reading["etemp"]
    flash_count = reading["flash_count"]
    row_arr = [
            ou_id.hw_id,
            ou_id.site_code,
            dateval,
            timeval,
            etemp,
            flash_count
            ] + co2s
    return row_arr

READING_FILE_MATCH = ("readings-", ".tsv")
READING_FILE_SIZE_CUTOFF = const(100 * 1024)

def store_reading(ou_id, reading_data_dir, reading):
    row = make_row(ou_id, reading)
    row = "\t".join([str(i) for i in row])

    _logger.debug("Data row: %s", row)
    _logger.debug("Data row: %s bytes", len(row) + 1)

    # Store data in sequential files, in case RTC gets messed up.
    # Then we might be able to guess the times by the sequence of wrong times.

    target = fileutil.prep_append_file(
            dir=reading_data_dir,
            match=READING_FILE_MATCH, size_limit=READING_FILE_SIZE_CUTOFF)

    _logger.debug("Writing data to %s ...", target)
    with open(target, "at") as f:
        f.write(row)
        f.write("\n")
    _logger.info("Wrote row to %s: %s\t", target, row)
    return (target, row)

def measure_sequence(hw, flash_count=0):
    _logger.info("Starting measurement sequence...")
    reading = read_sensors(hw, flash_count=flash_count)
    _logger.info("Reading: %s", reading)

    ou_id = configutil.read_config_json(co2unit_id.OU_ID_PATH, co2unit_id.OU_ID_DEFAULTS)

    reading_data_dir = hw.SDCARD_MOUNT_POINT + "/data/readings"
    return store_reading(ou_id, reading_data_dir, reading)
