.PHONY: default clean connect reload load_py bytecode load_bytecode

# Basic install direct from source
# ==================================================

# Source Python files
SRC_PY := $(wildcard src/*.py src/lib/*.py)

# Default port UART port to connect to FiPy with.
# Can override on command-line with PORT=
PORT ?= /dev/ttyUSB0

default:

# Clean via git
clean:
	git clean -fXd ./

# Connect to the FiPy UART port with tio
connect:
	tio $(PORT)

# Reload all sources
reload:
	rm -f .last_load_marker

# Load sources onto the FiPy
load_py:
	./ampy_load_src $(PORT) src/

# Precompile bytecode
# ==================================================
# This uses the mpy-cross program in the Pycom MicroPython firmware to
# precompile all source to bytecode .mpy files.
# These files give about a 25 to 50 percent size savings,
# and they seem to load faster.
# You will also catch syntax errors on compilation.

# Target bytecode mpy files
BYTECODE_MPY := $(patsubst src/%,target/bytecode/%,$(SRC_PY:.py=.mpy))

# The cross-compiler itself
MPY_CROSS := thirdparty/pycom-micropython-sigfox/mpy-cross/mpy-cross

clean:
	cd $(dir $(MPY_CROSS)) && make clean

# Compile the cross compiler itself
$(MPY_CROSS):
	cd $(dir $(MPY_CROSS)) && make

# Generic rule to cross-compile individual files
target/bytecode/%.mpy: src/%.py | $(MPY_CROSS)
	$(MPY_CROSS) $< && mkdir -p $(@D) && mv $(<:.py=.mpy) $@

# MicroPython does not look for 'main.mpy",
# so rename to 'main_bytecode.py'
# and create a main.py that simply imports it
target/bytecode/main_bytecode.mpy: target/bytecode/main.mpy | $(MPY_CROSS)
	mv $< $@

target/bytecode/main.py:
	echo "import main_bytecode" > $@

# All bytecode files
bytecode: $(BYTECODE_MPY) target/bytecode/main_bytecode.mpy target/bytecode/main.py

# Load byetcode files onto FiPy
load_bytecode: bytecode
	./ampy_load_src $(PORT) target/bytecode/
