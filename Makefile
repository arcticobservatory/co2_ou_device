# Basic install direct from source
# ==================================================

.PHONY: default clean distclean load_py reload dev_connect \
    dev_reset_wdt dev_erase_flash_fs \
    dev_lte_firmware_info dev_lte_firmware_update

# Source Python files
SRC_PY := $(wildcard src/*.py src/lib/*.py)

# Default port UART port to connect to FiPy with.
# Can override on command-line with PORT=
PORT ?= /dev/ttyUSB0

default:

# Clean via git
clean:
	git clean -fXd ./

distclean: clean
	rm -rf .venv

# A virtualenv for Python, especially the ampy tool to talk to the FiPy
.venv:
	virtualenv .venv --python=python3
	. .venv/bin/activate && pip install adafruit-ampy

# Load sources onto the FiPy
load_py: | .venv
	./ampy_load_src $(PORT) src/

# Reload all sources
reload:
	rm -f .last_load_marker

# Connect to the FiPy UART port with tio.
# Will go into an interactive mode and never exit.
# Cannot be used in scripts.
dev_connect:
	tio $(PORT)

# Reset watchdog timer on device
dev_reset_wdt: | .venv
	. .venv/bin/activate && ampy --port $(PORT) run on_device_scripts/reset_wdt.py

# Reflash device
dev_erase_flash_fs: dev_reset_wdt | .venv
	. .venv/bin/activate && ampy --port $(PORT) run on_device_scripts/reformat_flash.py && rm -f .last_load_marker

dev_lte_firmware_info: dev_reset_wdt | .venv
	. .venv/bin/activate && ampy --port $(PORT) run on_device_scripts/lte_firmware_info.py

# Update modem firmware. Requires firmware to be present on SD card.
# Will go into an interactive mode and never exit.
# Cannot be used in scripts.
dev_lte_firmware_update: dev_reset_wdt dev_lte_firmware_info | .venv
	. .venv/bin/activate && ampy --port $(PORT) run --no-output on_device_scripts/lte_firmware_update.py
	tio $(PORT)

# Precompile bytecode
# ==================================================
# This uses the mpy-cross program in the Pycom MicroPython firmware to
# precompile all source to bytecode .mpy files.
# These files give about a 25 to 50 percent size savings,
# and they seem to load faster.
# You will also catch syntax errors on compilation.

.PHONY: clean_bytecode bytecode load_bytecode

# Target bytecode mpy files
BYTECODE_MPY := $(patsubst src/%,target/bytecode/%,$(SRC_PY:.py=.mpy))
# MicroPython does not look for 'main.mpy", so rename to 'main_bytecode.py'.
BYTECODE_MPY := $(patsubst %/main.mpy,%/main_bytecode.mpy,$(BYTECODE_MPY))

# $(info BYETCODE_MPY $(BYTECODE_MPY))		# debug output

# The cross-compiler itself
MPY_CROSS := thirdparty/pycom-micropython-sigfox/mpy-cross/mpy-cross

distclean: clean_bytecode

clean_bytecode:
	cd $(dir $(MPY_CROSS)) && make clean

# Compile the cross compiler itself
$(MPY_CROSS):
	cd $(dir $(MPY_CROSS)) && make

# Generic rule to cross-compile individual files
target/bytecode/%.mpy: src/%.py $(MPY_CROSS)
	$(MPY_CROSS) $< && mkdir -p $(@D) && mv $(<:.py=.mpy) $@

# MicroPython does not look for 'main.mpy", so rename to 'main_bytecode.py'
.INTERMEDIATE: target/bytecode/main.mpy
target/bytecode/main_bytecode.mpy: target/bytecode/main.mpy
	mv $< $@

# Also create a plain 'main.py' that simply imports 'main_bytecode'
target/bytecode/main.py:
	echo "import main_bytecode" > $@

# All bytecode files
bytecode: $(BYTECODE_MPY) target/bytecode/main.py

# Load byetcode files onto FiPy
load_bytecode: bytecode
	./ampy_load_src $(PORT) target/bytecode/

# MicroPython Unix port for unit testing
# ==================================================
#
# Note. I cannot seem to get the Unix port to compile in the Pycom fork,
# so here we use the vanilla MicroPython fork.

.PHONY: clean_unix unix_port unix_repl unittest

# The Unix port fork's cross-compiler
UNIX_MPY_CROSS := thirdparty/micropython/mpy-cross/mpy-cross
# The Unix port itself
UNIX_MICROPYTHON := thirdparty/micropython/unix/micropython

# Lib directories when running the Unix port
export MICROPYPATH=src/:src/lib

distclean: clean_unix

clean_unix:
	cd $(dir $(UNIX_MPY_CROSS)) && make clean
	cd $(dir $(UNIX_MICROPYTHON)) && make clean

# Build mpy-cross in the Unix port's root dir
$(UNIX_MPY_CROSS):
	cd $(@D) && make

# Build the Unix port itself
$(UNIX_MICROPYTHON): $(UNIX_MPY_CROSS)
	cd $(@D) && make axtls && make CWARN=

# Build the Unix port
unix_port: $(UNIX_MICROPYTHON)

# Run the Unix REPL
unix_repl: unix_port
	$(UNIX_MICROPYTHON)

# Run all unit tests in Python sys.path
unittest: unix_port
	$(UNIX_MICROPYTHON) -m test_all

# Run unit tests on device
dev_unittest: dev_reset_wdt | .venv
	. .venv/bin/activate && ampy --port $(PORT) run on_device_scripts/run_unit_tests.py
