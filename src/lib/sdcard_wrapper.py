import logging
import sdcard

_logger = logging.getLogger("sdcard_wrapper")
#_logger.setLevel(logging.DEBUG)

class SdCardWrapper(sdcard.SDCard):
    """
    Wrap the readblocks method so that it only reads one block at a time

    This avoids a nasty error with file.readinto(buffer).

    If you try to read into a buffer larger than one block (512 bytes),
    the SDCard driver will use SPI CMD18 to try to read multiple blocks.

    For some reason, on our hardware, this command will fail the second time
    you try to use it, and it will put the SD card into an error state.

    So this class replaces the readblocks method with one that makes multiple
    calls to the underlying readblocks method, so that the driver only ever
    uses SPI CMD17 to read one block at a time.

    Note that readblocks is called by the MicroPython file and filesystem
    abstractions. Those libraries deal with fragmented files by calling
    readblocks multiple times. So we do not have to worry about fragmented
    files here. If we are asked to read multiple blocks, it is because we do
    want that sequence of blocks. Verified by watching debug output while
    reading a fragmented file.

    See also the firmware f_read function in fatfs/ff.c:
    https://github.com/pycom/pycom-micropython-sigfox/blob/df9f237c3fc0985f80181c62ba4f4ebd636bfae5/lib/fatfs/ff.c#L3463
    """

    def readblocks(self, blocknum, buf):
        BLOCKSIZE = const(512)

        nblocks, err = divmod(len(buf), BLOCKSIZE)
        if err:
            _logger.error("Bad buffer size %d. Must be a multiple of %d", len(buf), BLOCKSIZE)
            return 1

        _logger.debug("readblocks blocknum=%d, len(buf)=%d, blocks=%d", blocknum, len(buf), nblocks)

        offset = 0
        mv = memoryview(buf)
        while nblocks:
            blockwindow = mv[offset : offset+BLOCKSIZE]
            result = super().readblocks(blocknum, blockwindow)
            if result!=0:
                _logger.error("Error reading block %d. super().readblocks returned %d", blocknum, result)
                return 1

            offset += BLOCKSIZE
            blocknum += 1       # See note above about non-contiguous files
            nblocks -= 1

        return 0
