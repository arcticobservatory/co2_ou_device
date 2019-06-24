from machine import Timer
import explorir
import logging
import time

_logger = logging.getLogger("co2unit_measure")
_logger.setLevel(logging.DEBUG)

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

    co2_readings = [0] * 10
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
            _logger.debug("CO2 reading #%d: %6d ppm at %4d ms", co2_i, co2_readings[co2_i], co2_ms)
            co2_i += 1                              #   += will propagate
        except Exception as e:
            _logger.error("Unexpected error during CO2 sensor reading #%d. %s: %s", co2_i, type(e).__name__, e)

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
