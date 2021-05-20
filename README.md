CO2 Observation Unit for FiPy --- MicroPython Code
==================================================

This is MicroPython code for a CO2 sensor, or "Observation Unit",
developed at UiT The Arctic University of Norway
as part of the Distributed Arctic Observatory project.
These Observation Units are described in the paper:

Murphy et al.
"Experiences Building and Deploying
 Wireless Sensor Nodes for the Arctic Tundra,"
in The 21st IEEE/ACM International Symposium on
   Cluster, Cloud and Internet Computing (CCGrid 2021).
Melbourne Australia, May 2021.

The CO2 Observation Units are based on a FiPy microcontroller.
They push data via LTE CAT-M1 to a server in the lab.

This repository contains the MicroPython code that runs on the observation
unit itself, plus documentation for building setting up the devices.

Repositories and Documentation Associated with this Project
------------------------------------------------------------

- [co2_ou_device](https://github.com/arcticobservatory/co2_ou_device) repo
    --- Code and documentation for the observation unit itself

    - [Parts List](https://github.com/arcticobservatory/co2_ou_device/blob/master/doc/co2-unit-parts-list.md)
        --- parts used to build the observation units
    - [Circuit Schematic](https://github.com/arcticobservatory/co2_ou_device/blob/master/doc/co2-unit-schematic-v1.pdf)
        --- diagram of hardware and pin connections
    - [FiPy/Observation Unit Setup](https://github.com/arcticobservatory/co2_ou_device/blob/master/doc/co2-unit-fipy-setup.md)
        --- guide to installing the code on a FiPy and configuring the OU
    - [Data Layout](https://github.com/arcticobservatory/co2_ou_device/blob/master/doc/co2-unit-data-layout.md)
        --- OU naming, data directory structure, and data file formats

- [co2_ou_server](https://github.com/arcticobservatory/co2_ou_server) repo
    --- Code and documentation for the companion server

    - [Database Scripts](https://github.com/arcticobservatory/co2_ou_server/tree/master/database)
        --- Shell scripts that import the text-based CO2 data into a
            SQLite database for analysis, plus Python scripts to generate plots

Code Layout in this Repository
--------------------------------------------------

A Makefile controls many tasks including pre-compiling MicroPython bytecode and
running unit tests. Makefile tasks can use the MicroPython Unix port to quickly
run unit tests on the PC, without a FiPy (`make unittest`, the default target).
It can also push the code to the FiPy and the same run unit tests there (`make
dev_unittest`).

See the [Makefile](Makefile)'s targets and comments for details.

Scripts that interact with the FiPy assume that the FiPy is connected
via serial link.
They use `tio` (<https://tio.github.io/>)
as a terminal interface over the serial port
and Adafruit's `ampy` (<https://pypi.org/project/adafruit-ampy/>)
to transfer files.
`tio` should be installed via your distribution's package manager
(e.g. `sudo apt install tio`).
`ampy` will be installed in a Python virtualenv by the Makefile.

Directories:

- `src/`
    --- MicroPython source code, to be loaded onto a FiPy or optionally compiled first
- `src/lib/`
    --- Custom and third-party MicroPython libraries
- `thirdparty/`
    --- Third-party repos whose code we have adopted or adapted,
        checked out as git submodules
- `on_device_scripts/`
    --- Short MicroPython scripts to be run as batches on the device.
        Most have a corresponding `dev_<scriptname>` Makefile target
        that runs it (with dependencies).
- `target/`
    --- Where compiled bytecode is deposited

Scripts:

- `Makefile`
    --- GNU Make script with many tasks, see code for details
- `ampy_load_src`
    --- A shell script to load the code onto a FiPy (if not using an IDE)
- `update_thirdparty_libs`
    --- A shell script to update git submodules
        and copy third-party code to `lib/`
        for use on the device
- `create_code_update_dir`
    --- A shell script to diff two versions of this code
        and create an update that can be served to a deployed unit

Repository Tags
--------------------------------------------------

- d01_2019_aug
    --- Code as originally deployed August 13, 2019
- d02_2019_sep
    --- Code as deployed in the second deployment round, September 26, 2019
- d03_2020_sep
    --- Code as deployed for the second year, September 08, 2020
