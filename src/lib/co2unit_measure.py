from machine import Timer
import explorir
import fileutil
import logging
import os
import time

_logger = logging.getLogger("co2unit_measure")
#_logger.setLevel(logging.DEBUG)

READING_FILE_SIZE_CUTOFF = const(100 * 1000)

def read_sensors(hw):
    rtime = time.gmtime()
    chrono = Timer.Chrono()
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
        etemp = hw.etemp()
        etemp.start_conversion()
    except Exception as e:
        _logger.error("Unexpected error starting etemp reading. %s: %s", type(e).__name__, e)

    # Give CO2 sensor time to boot up after power-on
    time.sleep_ms(200)

    # Init communication with CO2 sensor
    try:
        _logger.debug("Init CO2 sensor...")
        co2 = hw.co2()
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
    except Exception as e:
        _logger.error("Unexpected error waiting for etemp reading. %s: %s", type(e).__name__, e)

    # Do more reads of CO2 sensor
    for _ in range(co2_i, len(co2_readings)):
        time.sleep_ms(500)
        try_read_co2_sensor()
    # co2_ms did not propagate like the others, so get it again
    co2_ms = chrono.read_ms()

    try:
        flash_reading = hw.flash_pin()
    except Exception as e:
        _logger.error("Unexpected error checking flash pin. %s: %s", type(e).__name__, e)

    reading = {
            "rtime":    rtime,
            "co2":      co2_readings,
            "co2_ms":   co2_ms,
            "etemp":    etemp_reading,
            "etemp_ms": etemp_ms,
            }
    return reading

def reading_to_tsv_row(reading):
    (YY, MM, DD, hh, mm, ss, _, _) = reading["rtime"]
    co2s = reading["co2"]
    co2s = [str(co2) for co2 in co2s]
    co2s = "\t".join(co2s)
    row_data = {
            "date": "{:04}-{:02}-{:02}".format(YY,MM,DD),
            "time": "{:02}:{:02}:{:02}".format(hh,mm,ss),
            "etemp": reading["etemp"],
            "co2s": co2s,
            }
    row = "{date}\t{time}\t{etemp}\t{co2s}".format(**row_data)
    return row

def choose_readings_file(reading_data_dir):
    _logger.debug("Ensuring observation dir exists %s", reading_data_dir)
    created_dirs = fileutil.mkdirs(reading_data_dir)
    if _logger.isEnabledFor(logging.DEBUG):
        _logger.debug("ls %s: %s", reading_data_dir, os.listdir(reading_data_dir))

    # Store data in sequential files, in case RTC gets messed up.
    # Then we might be able to guess the times by the sequence of wrong times.

    os.chdir(reading_data_dir)

    readings_match = ("readings-", ".tsv")
    readings_file = fileutil.last_file_in_sequence(readings_match)

    if not readings_file:
        readings_file = fileutil.make_sequence_filename(0, readings_match)
        _logger.info(" %20s : no readings found. Starting fresh", readings_file)

    else:
        stat = os.stat(readings_file)
        file_size = stat[fileutil.STAT_SIZE_INDEX]

        if file_size < READING_FILE_SIZE_CUTOFF:
            _logger.debug("%20s : using current readings file...", readings_file)
        else:
            _logger.info(" %20s : file over size threshold", readings_file)
            index = fileutil.extract_sequence_number(readings_file, readings_match)
            readings_file = fileutil.make_sequence_filename(index+1, readings_match)
            _logger.info(" %20s : beginning new file", readings_file)

    return readings_file

def store_reading(reading, reading_data_dir):
    row = reading_to_tsv_row(reading)
    _logger.debug("Data row: %s", row)
    _logger.debug("Data row: %s bytes", len(row) + 1)

    readings_file = choose_readings_file(reading_data_dir)
    _logger.debug("Writing data to %s/%s ...", reading_data_dir, readings_file)
    with open(readings_file, "at") as f:
        f.write(row)
        f.write("\n")
    _logger.info("Wrote row to %s/%s: %s\t", reading_data_dir, readings_file, row)
    return (readings_file, row)
