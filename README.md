CO2 Observation Unit for FiPy --- MicroPython Code
==================================================

This is the MicroPython code for the DAO CO2 Observation Unit.

The CO2 Observation Units are based on a FiPy microcontroller.
They push data via LTE CAT-M1 to a server here in the lab.

Repository branches and tags
--------------------------------------------------

Branches:

- **master** --- default branch
- **diagnostic** --- branch that keeps as close to original deploy behavior
  as possible, but adds more diagnostic information (most notably signal
  strength measurement)
- **bugfix** --- branch that includes updates from diagnostic, plus
  non-invasive bugfixes for the second-round deploy

Tags:

- **2019-varanger-deploy** --- Code that was originally deployed August 13, 2019
- **2019-varanger-deploy-b-sept** --- Code that was deployed in the second deployment round, September 26, 2019

Hardware and Software Setup
--------------------------------------------------

- [Circuit schematic (PDF)](doc/co2-unit-schematic-v1.pdf): diagram of hardware and pin connections
- [FiPy/Unit Setup](doc/co2-unit-fipy-setup.md): guide to installing the code on a FiPy and configuring the unit

Code Layout
--------------------------------------------------

- `src/` --- MicroPython source code, ready to be loaded onto a FiPy
- `src/lib/` --- Custom and third-party MicroPython libraries
- `ampy_load_src` --- A shell script to load the code onto a FiPy (if not using an IDE)
- `thirdparty/` --- Third-party libs whose code we have adopted or adapted,
    as git submodules
- `update_thirdparty_libs` --- A shell script to update git submodules
    and copy third-party code to `lib/`
