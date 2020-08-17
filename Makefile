.PHONY: default clean connect reload load_py bytecode load_bytecode

# Basic install direct from source
# ==================================================

SRC_PY := $(wildcard src/*.py src/lib/*.py)
PORT ?= /dev/ttyUSB0

default:

clean:
	git clean -fXd ./

connect:
	tio $(PORT)

reload:
	rm -f .last_load_marker

load_py:
	./ampy_load_src $(PORT) src/

# Precompile bytecode
# ==================================================

BYTECODE_MPY := $(patsubst src/%,target/bytecode/%,$(SRC_PY:.py=.mpy))
MPY_CROSS := thirdparty/pycom-micropython-sigfox/mpy-cross/mpy-cross

clean:
	cd $(dir $(MPY_CROSS)) && make clean

$(MPY_CROSS):
	cd $(dir $(MPY_CROSS)) && make

target/bytecode/%.mpy: src/%.py | $(MPY_CROSS)
	$(MPY_CROSS) $< && mkdir -p $(@D) && mv $(<:.py=.mpy) $@

target/bytecode/main_bytecode.mpy: target/bytecode/main.mpy | $(MPY_CROSS)
	mv $< $@

target/bytecode/main.py:
	echo "import main_bytecode" > $@

bytecode: $(BYTECODE_MPY) target/bytecode/main_bytecode.mpy target/bytecode/main.py

load_bytecode: bytecode
	./ampy_load_src $(PORT) target/bytecode/
