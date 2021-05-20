Layout of CO2 Observation Unit Data
==================================================

Observation Unit Naming
--------------------------------------------------

CO2 Observation Units have three names/IDs:

- **Unit hardware ID**,
    based on the FiPy's unique hardware ID,
    e.g. **co2unit-30aea42a50bc**

- **Unit nickname**,
    an arbitrary, more human-readable name for the OU
    (in our case based on the order in which they were assembled),
    e.g. **varanger-03**

- **Deployment site**,
    which is a deployment-specific code for the site at which the OU is deployed
    (in our case, set by COAT for their camera boxes)
    e.g. **vj_re_sn_4**

This is admittedly confusing.
The situation is an artifact of the development process.
There were supposed to be only the one hardware ID and the deployment site info.
However, since we did not know ahead of time which OU would be set at each site,
we issued temporary "site codes" based on the order in which we assembled
the OUs, e.g. "varanger-01".
These names stuck in our everyday usage, even after deployment,
and so they became nicknames.

The most confusing part is that,
because the nicknames grew out of supposedly-temporary site codes,
**older code still uses the variable name `site_code` for what
is now the nickname. (Sorry!)**
The data analysis scripts in the server code handle this better,
where the OU hardware ID is the row key of most tables,
and there is a deployment table that maps OU hardware IDs to
where they were deployed during what time periods and what their nicknames were.

Data of an Individual CO2 Observation Unit
--------------------------------------------------

Data is stored on the Observation Unit's SD card as follows:

```
/sd/
|-- data/
|   `-- readings/
|       |-- readings-0000.tsv
|       |-- readings-0001.tsv
|       |-- readings-0002.tsv
|       |-- readings-0003.tsv
|       |-- readings-0004.tsv
|       `-- readings-0005.tsv
|-- errors/
|   `-- errors-0000.txt
`-- updates/
    |-- update-2019-07-28a/
    |   |-- conf-patch/
    |   |   |-- ou-id.json
    |   |   `-- schedule.json
    |   `-- flash/
    |       `-- main.py
    `-- update-2019-08-26b/
        `-- conf-patch/
            `-- ou-comm-config.json
```

This data on the SD card is synced to a directory on the server named
for the FiPy hardware ID.
So `/sd/data/` becomes `remote_data/co2unit-30aea42a50bc/data/`
under the server directory.
Synced directories are:

- `data/` (pushed from OU to server) --- holds actual measurements
- `errors/` (pushed from OU to server) --- holds error logs
- `updates/` (pulled from server to OU)
    --- holds code or config updates to be downloaded and installed

See corresponding sections below for details of formats for
data, errors, and updates.

There are also directories for configuration and runtime information
which are not directly synced to the server:

- `conf/` --- Holds configuration information.
    See the [OU setup document](co2-unit-fipy-setup.md) for details.
- `var/` --- Holds runtime information (e.g. which updates have been installed)

CO2 Data Format
--------------------------------------------------

Each unit writes and uploads data in a CSV (tab-separated) format, in files named like:\
`data/readings/readings-0000.tsv`

The tabular CO2 data looks like this:

```
co2unit-30aea42a50bc	varanger-03	2019-07-31	13:00:10	23.4375	1	680	700	710	710	700	690	700	700	700	700
co2unit-30aea42a50bc	varanger-03	2019-07-31	13:29:50	23.375	0	800	810	810	800	850	850	850	840	840	830
co2unit-30aea42a50bc	varanger-03	2019-07-31	13:30:06	23.375	0	770	780	750	740	740	740	740	740	740	740
co2unit-30aea42a50bc	varanger-03	2019-07-31	14:00:08	23.25	2	690	660	660	660	690	690	680	680	680	680
```

Columns are:

| Col#  | field                                      | example              |
|-------|--------------------------------------------|----------------------|
| 1     | hardware id                                | co2unit-30aea42a50bc |
| 2     | unit nickname                              | varanger-03          |
| 3     | reading date                               | 2019-07-31           |
| 4     | reading time                               | 13:00:10             |
| 5     | temperature (C)                            | 23.4375              |
| 6     | camera flashes observed since last reading | 1                    |
| 7--17 | CO2 readings (ppm) (ten readings)          | 680                  |

Each unit also has an error log in files named like:\\
`errors/errors-0000.txt`

CO2 OU Error Logs
--------------------------------------------------

Each unit writes low-volume operational logs in files named like:\
`errors/errors-0000.txt`

The format is somewhat free-form,
but entries start with a summary line consisting of
dashes, a date, a log level, and a message.
Additional info such as stack traces may follow on subsequent lines.
For example:

```
----- (2019, 10, 25, 3, 11, 24, 4, 298) WARN  Skipping comm due to backoff: 4/5
----- (2019, 10, 25, 3, 11, 24, 4, 298) EXC   Uncaught exception at top level
Traceback (most recent call last):
  File "main.py", line 77, in <module>
  File "/flash/lib/co2unit_main.py", line 231, in run
TypeError: 'NoneType' object is not iterable
```

Old versions print the date as a Python tuple (as above).
Newer versions print the date in an ISO-like style (as below),
and include attach information along with errors and warnings.

```
----- 2019-09-16 10:55:57 INFO  Self-test. LTE attached: True. Signal quality {'rssi_dbm': -97, 'rssi_raw': 8, 'ber_raw': 99}
----- 2019-09-16 10:57:25 INFO  Self-test. LTE attached: True. Signal quality {'rssi_dbm': -97, 'rssi_raw': 8, 'ber_raw': 99}
```

When writing database import scripts, take care to handle both versions.

CO2 OU Code and Config Updates
--------------------------------------------------

Updates are copied from the server to the OU's SD card
and are then installed from the SD card into the active code or config
of the OU.

```
<server>/remote_data/co2unit-30aea42a5268/
<device>/sd/
`-- updates/
    |-- update-2019-07-28a/
    |   |-- conf-patch/
    |   |   |-- ou-id.json
    |   |   `-- schedule.json
    |   `-- flash/
    |       |-- lib/
    |       |   `-- fileutils.mpy
    |       `-- main.py
    `-- update-2019-08-26b/
        `-- conf-patch/
            `-- ou-comm-config.json
```

- Each subdirectory that starts with `update-`
    contains an update to be downloaded and installed together.

- Only the latest (by name descending) will be downloaded and installed.

    - The prefix `update-` is required but the rest of the name is arbitrary.
    - It does not have to be a date, but a date is a natural way to do it.

- Within that `update-X` subdirectory:

    - `flash/` should contain Python source files (or compiled `.mpy` files)
        that are to be copied into the unit's flash filesystem.

        The tree should correspond directly to the device's
        `/flash/` filesystem, e.g.:

        ```
        <update-dir>/flash/main.py
        =   <device>/flash/main.py

        <update-dir>/flash/lib/fileutil.mpy
        =   <device>/flash/lib/fileutil.mpy
        ```

    - `conf-patch/` contains JSON files that will be merged into the unit's `conf/` directory

### To Create an Update to be Downloaded (on Server)

1. Create an update subdirectory and a `flash/` subdirectory within that, e.g.:

    ```
    mkdir -p co2unit-30aea42a5268/updates/update-2020-01-14a/flash
    ```

2. Copy source or bytecode (`*.mpy`) files
    that need to be included in the update.
    The `flash/` subdirectory of the update should correspond directly to
    the `/flash/` filesystem on the device,
    which means it should copy files from the `src/` directory of this repo
    or the `target/bytecode/` directory of compiled files.

    `src/main.py`\
    → place in `co2unit-30aea42a5268/updates/update-2020-01-14a/flash/main.py`\
    → is downloaded to device `/sd/updates/update-2020-01-14a/flash/main.py`\
    → is installed to device flash `/flash/main.py`

    `target/bytecode/lib/fileutil.mpy`\
    → place in `co2unit-30aea42a5268/updates/update-2020-01-14a/flash/lib/fileutil.mpy`\
    → is downloaded to device `/sd/updates/update-2020-01-14a/flash/lib/fileutil.mpy`\
    → is installed to device flash `/flash/lib/fileutil.mpy`

3. Wait for next successful sync

    After the sync, if the update was installed, it will trigger another communication cycle.
    So you should see an extra ping (or double-ping) from the unit.

The script [`create_code_update_dir`](../create_code_update_dir)
helps automate creating this directory.
Given a target update directory,
a from-version, and a to-version,
the script checks which files have changed between versions and copies
them to the target directory.

**NOTE**: This script was written when we were loading the source `.py` files
directly onto the FiPy without precompiling them to bytecode,
and so it only gathers the updated source files.
It needs to be updated to add the compilation step.

### To Update Config, e.g. Give the OU a New Nickname

1. Create an update subdirectory and a `conf-patch/` subdirectory within that,
    e.g.:

    ```
    mkdir -p co2unit-30aea42a5268/updates/update-2020-01-14a/conf-patch
    ```

2. Create a JSON file corresponding to the config file you want to update,
    with the keys you want to change
    (note that `site_code` is now the _nickname_):

    A patch ou-id.json:

    ```json
    {
        "site_code": "varanger-01"
    }
    ```

    A patch ou-comm-config.json:

    ```json

    {
        "sync_dest": [
            "http://129.242.17.212:8080",
            "http://mmu019-1.cs.uit.no:8080"
        ],
        "ntp_host": "ntp.uit.no"
    }
    ```
