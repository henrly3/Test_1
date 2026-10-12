"""Block device access with O_DIRECT and aligned buffers."""

import fcntl
import mmap
import os
import stat
import struct

BLKGETSIZE64 = 0x80081272
BLKSSZGET = 0x1268
BLKPBSZGET = 0x127B
BLKDISCARD = 0x1277
BLKFLSBUF = 0x1261


class DeviceError(Exception):
    pass


def aligned_buffer(size):
    """Anonymous mmap is page aligned, which satisfies O_DIRECT."""
    return mmap.mmap(-1, size)


def _real_name(path):
    return os.path.basename(os.path.realpath(path))


def mounted_partitions(path):
    """Return mount points that use the device or any of its partitions."""
    st = os.stat(path)
    if not stat.S_ISBLK(st.st_mode):
        return []
    name = _real_name(path)
    sys_dir = f"/sys/class/block/{name}"
    names = {name}
    if os.path.isdir(sys_dir):
        for entry in os.listdir(sys_dir):
            if entry.startswith(name):
                names.add(entry)
    hits = []
    try:
        with open("/proc/mounts") as f:
            for line in f:
                src, mnt = line.split()[:2]
                if src.startswith("/dev/") and _real_name(src) in names:
                    hits.append(f"{src} on {mnt}")
    except OSError:
        pass
    return hits


class BlockDevice:
    """A raw block device, or a regular file for dry runs and unit tests."""

    def __init__(self, path, writable=False, direct=True):
        self.path = path
        flags = (os.O_RDWR if writable else os.O_RDONLY) | getattr(os, "O_CLOEXEC", 0)
        self.direct = False
        if direct and hasattr(os, "O_DIRECT"):
            try:
                self.fd = os.open(path, flags | os.O_DIRECT)
                self.direct = True
            except OSError:
                self.fd = os.open(path, flags)
        else:
            self.fd = os.open(path, flags)

        st = os.fstat(self.fd)
        self.is_block = stat.S_ISBLK(st.st_mode)
        if self.is_block:
            self.size = struct.unpack("Q", fcntl.ioctl(self.fd, BLKGETSIZE64, b"\0" * 8))[0]
            self.logical_block = struct.unpack("i", fcntl.ioctl(self.fd, BLKSSZGET, b"\0" * 4))[0]
            self.physical_block = struct.unpack("i", fcntl.ioctl(self.fd, BLKPBSZGET, b"\0" * 4))[0]
        else:
            self.size = st.st_size
            self.logical_block = 512
            self.physical_block = 4096
        if self.size == 0:
            raise DeviceError(f"{path}: size is 0")

    def close(self):
        os.close(self.fd)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def read_into(self, buf, offset):
        n = os.preadv(self.fd, [buf], offset)
        if n != len(buf):
            raise DeviceError(f"short read at {offset}: {n}/{len(buf)}")

    def write_from(self, buf, offset):
        n = os.pwrite(self.fd, buf, offset)
        if n != len(buf):
            raise DeviceError(f"short write at {offset}: {n}/{len(buf)}")

    def flush(self):
        os.fsync(self.fd)

    def drop_cache(self):
        if self.is_block:
            try:
                fcntl.ioctl(self.fd, BLKFLSBUF)
            except OSError:
                pass

    def discard(self, offset, length):
        if not self.is_block:
            raise DeviceError("discard requires a block device")
        fcntl.ioctl(self.fd, BLKDISCARD, struct.pack("QQ", offset, length))
