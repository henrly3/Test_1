"""ATA commands over Linux SG_IO using SCSI ATA PASS-THROUGH(16) (SAT).

Works for SATA drives attached through libata (/dev/sdX) and most USB-SATA
bridges that implement SAT.
"""

import ctypes
import fcntl
import struct

SG_IO = 0x2285
SG_DXFER_NONE = -1
SG_DXFER_FROM_DEV = -3

ATA_PASS_THROUGH_16 = 0x85
PROTO_NON_DATA = 3
PROTO_PIO_DATA_IN = 4

ATA_CMD_IDENTIFY = 0xEC
ATA_CMD_SMART = 0xB0
SMART_READ_DATA = 0xD0
SMART_READ_THRESHOLDS = 0xD1
SMART_RETURN_STATUS = 0xDA
SMART_LBA_MID = 0x4F
SMART_LBA_HIGH = 0xC2

SMART_ATTR_NAMES = {
    1: "Raw_Read_Error_Rate",
    5: "Reallocated_Sector_Ct",
    9: "Power_On_Hours",
    12: "Power_Cycle_Count",
    170: "Available_Reservd_Space",
    171: "Program_Fail_Count",
    172: "Erase_Fail_Count",
    173: "Ave_Block_Erase_Count",
    174: "Unexpect_Power_Loss_Ct",
    177: "Wear_Leveling_Count",
    179: "Used_Rsvd_Blk_Cnt_Tot",
    181: "Program_Fail_Cnt_Total",
    182: "Erase_Fail_Count_Total",
    183: "Runtime_Bad_Block",
    187: "Reported_Uncorrect",
    192: "Power-Off_Retract_Count",
    194: "Temperature_Celsius",
    195: "Hardware_ECC_Recovered",
    196: "Reallocated_Event_Count",
    197: "Current_Pending_Sector",
    198: "Offline_Uncorrectable",
    199: "UDMA_CRC_Error_Count",
    202: "Percent_Lifetime_Remain",
    231: "SSD_Life_Left",
    232: "Available_Reservd_Space",
    233: "Media_Wearout_Indicator",
    235: "POR_Recovery_Count",
    241: "Total_LBAs_Written",
    242: "Total_LBAs_Read",
}

# Attributes whose non-zero raw value indicates media/link trouble.
SMART_CRITICAL_RAW = {5, 187, 197, 198, 199}


class AtaError(Exception):
    pass


class _SgIoHdr(ctypes.Structure):
    _fields_ = [
        ("interface_id", ctypes.c_int),
        ("dxfer_direction", ctypes.c_int),
        ("cmd_len", ctypes.c_ubyte),
        ("mx_sb_len", ctypes.c_ubyte),
        ("iovec_count", ctypes.c_ushort),
        ("dxfer_len", ctypes.c_uint),
        ("dxferp", ctypes.c_void_p),
        ("cmdp", ctypes.c_void_p),
        ("sbp", ctypes.c_void_p),
        ("timeout", ctypes.c_uint),
        ("flags", ctypes.c_uint),
        ("pack_id", ctypes.c_int),
        ("usr_ptr", ctypes.c_void_p),
        ("status", ctypes.c_ubyte),
        ("masked_status", ctypes.c_ubyte),
        ("msg_status", ctypes.c_ubyte),
        ("sb_len_wr", ctypes.c_ubyte),
        ("host_status", ctypes.c_ushort),
        ("driver_status", ctypes.c_ushort),
        ("resid", ctypes.c_int),
        ("duration", ctypes.c_uint),
        ("info", ctypes.c_uint),
    ]


def build_cdb(command, protocol, features=0, count=0, lba_low=0, lba_mid=0,
              lba_high=0, data_in=False, check_condition=False):
    """Build an ATA PASS-THROUGH(16) CDB for a 28-bit ATA command."""
    flags = 0
    if check_condition:
        flags |= 0x20
    if data_in:
        # t_dir=from device, byt_blok=blocks, t_length=in sector count field
        flags |= 0x08 | 0x04 | 0x02
    return bytes([
        ATA_PASS_THROUGH_16,
        protocol << 1,
        flags,
        0, features & 0xFF,
        0, count & 0xFF,
        0, lba_low & 0xFF,
        0, lba_mid & 0xFF,
        0, lba_high & 0xFF,
        0,  # device
        command,
        0,  # control
    ])


def _sg_io(fd, cdb, data_len, timeout_ms=10000):
    cdb_buf = ctypes.create_string_buffer(cdb, len(cdb))
    sense = ctypes.create_string_buffer(64)
    data = ctypes.create_string_buffer(data_len) if data_len else None

    hdr = _SgIoHdr()
    hdr.interface_id = ord("S")
    hdr.dxfer_direction = SG_DXFER_FROM_DEV if data_len else SG_DXFER_NONE
    hdr.cmd_len = len(cdb)
    hdr.mx_sb_len = len(sense)
    hdr.dxfer_len = data_len
    hdr.dxferp = ctypes.cast(data, ctypes.c_void_p) if data else None
    hdr.cmdp = ctypes.cast(cdb_buf, ctypes.c_void_p)
    hdr.sbp = ctypes.cast(sense, ctypes.c_void_p)
    hdr.timeout = timeout_ms

    try:
        fcntl.ioctl(fd, SG_IO, hdr)
    except OSError as e:
        raise AtaError(f"SG_IO ioctl failed: {e}") from e
    if hdr.host_status or (hdr.driver_status & 0x0F):
        raise AtaError(f"SG_IO transport error host=0x{hdr.host_status:x} "
                       f"driver=0x{hdr.driver_status:x}")
    return (data.raw if data else b""), sense.raw[:hdr.sb_len_wr], hdr.status


def _ata_status_descriptor(sense):
    """Return the ATA Status Return descriptor (code 0x09) from sense data."""
    if len(sense) < 8 or (sense[0] & 0x7F) != 0x72:
        return None
    pos, end = 8, min(len(sense), 8 + sense[7])
    while pos + 1 < end:
        code, length = sense[pos], sense[pos + 1]
        if code == 0x09 and length >= 0x0C:
            return sense[pos:pos + 2 + length]
        pos += 2 + length
    return None


def _check_ata_error(sense, scsi_status):
    desc = _ata_status_descriptor(sense)
    if desc is not None:
        error, status = desc[3], desc[13]
        if status & 0x01:  # ERR bit
            raise AtaError(f"ATA command aborted: status=0x{status:02x} error=0x{error:02x}")
    elif scsi_status not in (0, 2):
        raise AtaError(f"SCSI status 0x{scsi_status:02x}")


def ata_string(raw):
    """ATA strings store two chars per little-endian word, high byte first."""
    swapped = bytearray(len(raw))
    swapped[0::2] = raw[1::2]
    swapped[1::2] = raw[0::2]
    return swapped.decode("ascii", errors="replace").strip()


def parse_identify(buf):
    w = struct.unpack("<256H", buf[:512])
    lba48 = bool(w[83] & (1 << 10))
    sectors = (w[100] | w[101] << 16 | w[102] << 32 | w[103] << 48) if lba48 else (w[60] | w[61] << 16)

    logical = 512
    if (w[106] & 0xC000) == 0x4000 and w[106] & (1 << 12):
        logical = (w[117] | w[118] << 16) * 2
    physical = logical
    if (w[106] & 0xC000) == 0x4000 and w[106] & (1 << 13):
        physical = logical << (w[106] & 0x0F)

    gens = {1: "1.5 Gb/s", 2: "3.0 Gb/s", 3: "6.0 Gb/s"}
    supported = [gens[g] for g in (3, 2, 1) if w[76] & (1 << g)] if w[76] not in (0, 0xFFFF) else []
    current = gens.get((w[77] >> 1) & 0x7, "unknown") if w[77] not in (0, 0xFFFF) else "unknown"

    return {
        "model": ata_string(buf[54:94]),
        "serial": ata_string(buf[20:40]),
        "firmware": ata_string(buf[46:54]),
        "sectors": sectors,
        "logical_sector_size": logical,
        "physical_sector_size": physical,
        "capacity_bytes": sectors * logical,
        "is_ssd": w[217] == 1,
        "rotation_rate": w[217],
        "sata_speeds_supported": supported,
        "sata_speed_current": current,
        "ncq_supported": bool(w[76] & (1 << 8)) and w[76] != 0xFFFF,
        "queue_depth": (w[75] & 0x1F) + 1,
        "smart_supported": bool(w[82] & 1),
        "smart_enabled": bool(w[85] & 1),
        "trim_supported": bool(w[169] & 1),
        "trim_drat": bool(w[69] & (1 << 14)),  # deterministic read after trim
        "trim_rzat": bool(w[69] & (1 << 5)),   # read zeros after trim
        "write_cache_enabled": bool(w[85] & (1 << 5)),
    }


def parse_smart(data, thresholds=None):
    thr = {}
    if thresholds:
        for i in range(30):
            e = thresholds[2 + i * 12: 14 + i * 12]
            if e[0]:
                thr[e[0]] = e[1]
    attrs = []
    for i in range(30):
        e = data[2 + i * 12: 14 + i * 12]
        attr_id = e[0]
        if attr_id == 0:
            continue
        flags = e[1] | e[2] << 8
        raw = int.from_bytes(e[5:11], "little")
        threshold = thr.get(attr_id)
        failing = threshold is not None and threshold > 0 and e[3] <= threshold
        attrs.append({
            "id": attr_id,
            "name": SMART_ATTR_NAMES.get(attr_id, "Unknown_Attribute"),
            "flags": flags,
            "prefailure": bool(flags & 1),
            "value": e[3],
            "worst": e[4],
            "threshold": threshold,
            "raw": raw,
            "failing": failing,
        })
    return attrs


class AtaDevice:
    def __init__(self, fd):
        self.fd = fd

    def identify(self):
        cdb = build_cdb(ATA_CMD_IDENTIFY, PROTO_PIO_DATA_IN, count=1, data_in=True)
        data, sense, status = _sg_io(self.fd, cdb, 512)
        _check_ata_error(sense, status)
        return parse_identify(data)

    def _smart_read(self, feature):
        cdb = build_cdb(ATA_CMD_SMART, PROTO_PIO_DATA_IN, features=feature, count=1,
                        lba_mid=SMART_LBA_MID, lba_high=SMART_LBA_HIGH, data_in=True)
        data, sense, status = _sg_io(self.fd, cdb, 512)
        _check_ata_error(sense, status)
        return data

    def smart_attributes(self):
        data = self._smart_read(SMART_READ_DATA)
        try:
            thresholds = self._smart_read(SMART_READ_THRESHOLDS)
        except AtaError:
            thresholds = None
        return parse_smart(data, thresholds)

    def smart_health_ok(self):
        """True = passed, False = drive reports failure, None = undetermined."""
        cdb = build_cdb(ATA_CMD_SMART, PROTO_NON_DATA, features=SMART_RETURN_STATUS,
                        lba_mid=SMART_LBA_MID, lba_high=SMART_LBA_HIGH, check_condition=True)
        _, sense, _ = _sg_io(self.fd, cdb, 0)
        desc = _ata_status_descriptor(sense)
        if desc is None:
            return None
        mid, high = desc[9], desc[11]
        if (mid, high) == (0x4F, 0xC2):
            return True
        if (mid, high) == (0xF4, 0x2C):
            return False
        return None
