CO2 Observation Unit --- FyPy/Unit setup
==================================================

Ready FiPy, SIM card, and SD card
--------------------------------------------------

### Prepare an SD card

- The SD card needs the modem firmware CATM1-41065, unzipped.
- Also a few config files in `/conf`

### Required: Data Destination URL --> `/sd/conf/ou-comm-config.json`

`sync_dest` is the only truly required config option.
The others will fall back to defaults if not specified.

```json
{
    "sync_dest": [
        "http://129.242.17.212:8080",
        "http://mmu019-1.cs.uit.no:8080"
    ],
    "ntp_host": "ntp.uit.no"
}
```

For additional configuration options, see [Optional Configuration](#optional_config) below.

### Flash FiPy firmware (version 1.18.2.r4)

1. Download firmware tarball from [Pycom's FiPy firmware downloads page](https://software.pycom.io/downloads/FiPy.html)
    - CO2 units use version 1.18.2.r4
2. Get a SIM card for the FiPy and load it into the FiPy's SIM slot
    - Be sure to write down the SIM card's ICC and mobile numbers for future reference
3. Place FiPy in a Pymakr board in reset mode (wire connecting GND and G23).
4. Run the Pycom firmware flash tool...
    - Be sure to not be running any other serial connection to the USB
    - Click "Flash from local file"
    - Choose the downloaded tarball (no need to extract)
    - "Continue"
5. Disconnect the reset wire and press the FiPy's reset button.
    You should get a heartbeat on the FiPy's LED now.
6. Make a serial connection to the FiPy

See Pycom's [Updating Firmware](https://docs.pycom.io/gettingstarted/installation/firmwaretool/) tutorial for more details.

### Label the FiPy with its hardware ID

1. In the MicroPython REPL, get the FiPy's unique ID so you can make a label

    ```python
    import machine
    import ubinascii
    ubinascii.hexlify(machine.unique_id()).decode("ascii")
    ```

2. This will give you a hex number, e.g. `30aea42a5140`

    - So far in our batches of FiPys, only the last five digits have been
      different (`30aea42xxxxx`), but note the whole ID anyway just in case.

3. Make a label. The format so far is `fipy-ID`, e.g. `fipy-30aea42a5140`

    - If using a Dymo LetraTag label maker, use the smallest font setting

### Flash the modem firmware

1. Put the SD card in the SD card reader

2. In the FiPy REPL, run the Sequans updater:

    ```python
    import machine
    import os
    os.mount(machine.SD(), "/sd")
    os.chdir("/sd/CATM1-41065")
    import sqnsupgrade
    sqnsupgrade.run('CATM1-41065.dup', 'updater.elf', debug=True)
    ```

    If the upgrade stalls out and fails, just do a hard reset (power on/off)
    and try again. In my experience the first update always fails.

    See Pycom's [Modem Firmware Update](https://docs.pycom.io/tutorials/lte/firmware/) tutorial for details

3. Write down the IMEI number

### Load the co2_ou code

CO2 Unit code repository: <https://vvgitlab.cs.uit.no/COAT/co2_ou>

1. From your command line, load the code onto the FiPy

    ```bash
    git clone git@vvgitlab.cs.uit.no:COAT/co2_ou.git
    cd co2_ou/

    port=/dev/ttyUSB0

    rm .last_load_marker; \
    ./ampy_load_src $port src/ \
    && tio $port && tio $port
    ```

2. Place the FiPy and SD card into a unit with a power source
3. Turn on the unit and watch the LED during self test
4. After the LED self tests, it will do a round of communication. Make sure the
   ping is registered by the server.

Optional configuration {#optional_config}
--------------------------------------------------

### Optional: OU location/nickname --> `/sd/conf/ou-id.json`

```json
{
    "site_code": "varanger-01"
}
```

It's easiest to let the unit pick this up as an update during its first communication cycle.
To set it up on the server, create a `conf-patch` update directory, like so:

```bash
cd projects/co2_unit_server/remote_data

ou=30aea42a4ee0; \
site=varanger-b01; \
\
idfile=co2unit-$ou/updates/update-2019-08-24/conf-patch/ou-id.json; \
mkdir -p $(dirname $idfile) \
&& echo "{ \"site_code\": \"$site\" }" > $idfile \
&& echo $idfile \
&& cat $idfile
```

### Optional: Adjust schedule --> `/sd/conf/conf/schedule.json`

The default schedule is below. If you want to adjust it, you can.

The default is to measure every 30 minutes and to communicate every day and a
randomized time between 03:02 (after 03:00 reading) and 03:24 (before the 03:30
reading).

```json
{
    "tasks": [
            [6, "minutes", 30, 0],
            [7, "daily_random", 3, 2, 24]
    ]
}
```

The format is `[state, schedule_type, *args]`.

- `state`: 6 is measure, 7 is communicate. See the constants in `co2unit_main.py` for others.
- `schedule_type`:
    - `minutes, x, y`: every `x` minutes, offset by `y`.
        - `[6, 'minutes', 30, 0]` = measure every 30 minutes
        - `[6, 'minutes', 10, 7]` = measure every 10 minutes on the sevens: 07, 17, 27, ...
    - `minutes_random, x, y1, y2`: every `x` minutes, offset by a random value between `y1` and `y2`.
    - `daily, hh, mm`: every day at hh:mm
        - `[7, 'daily', 3, 10]` = communicate every day at 03:10
    - `daily_random, hh, mm1, mm2`: every day at a random time between `hh:mm1` and `hh:mm2`

When scheduling, you should avoid having the random ranges overlap with other
scheduled tasks. They will be re-randomized each time the schedule is
calculated before sleep. If the unit wakes for another task in the middle of
the randomized window, the randomized task will be skipped until the next
window, where it might be skipped again.
