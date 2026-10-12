"""Unit tests. They run against a regular file, so no SSD is needed."""

import json
import struct

import pytest

from ssd_test import ata, cli
from ssd_test.device import BlockDevice
from ssd_test import tests as cases
from ssd_test.tests import Context, describe_mismatch, expected_data

MiB = 1024 * 1024


@pytest.fixture
def image(tmp_path):
    path = tmp_path / "disk.img"
    path.write_bytes(bytes(8 * MiB))
    return str(path)


def _ata_str(text, length):
    raw = text.ljust(length).encode()
    out = bytearray(length)
    out[0::2], out[1::2] = raw[1::2], raw[0::2]
    return bytes(out)


def test_parse_size():
    assert cli.parse_size("4k") == 4096
    assert cli.parse_size("1M") == MiB
    assert cli.parse_size("2GiB") == 2 * 1024 * MiB
    assert cli.parse_size("512") == 512


def test_build_cdb_identify():
    cdb = ata.build_cdb(ata.ATA_CMD_IDENTIFY, ata.PROTO_PIO_DATA_IN, count=1, data_in=True)
    assert len(cdb) == 16
    assert cdb[0] == 0x85 and cdb[1] == 0x08 and cdb[2] == 0x0E
    assert cdb[6] == 1 and cdb[14] == 0xEC


def test_parse_identify():
    w = [0] * 256
    w[76] = (1 << 3) | (1 << 2) | (1 << 1) | (1 << 8)
    w[77] = 3 << 1
    w[82], w[85] = 1, 1 | (1 << 5)
    w[83] = 1 << 10
    w[100], w[101] = 0x5000, 0x0E8E  # 0x0E8E5000 sectors
    w[169] = 1
    w[69] = 1 << 14
    w[217] = 1
    buf = bytearray(struct.pack("<256H", *w))
    buf[20:40] = _ata_str("SN123", 20)
    buf[46:54] = _ata_str("FW1.0", 8)
    buf[54:94] = _ata_str("TEST SATA SSD", 40)
    info = ata.parse_identify(bytes(buf))
    assert info["model"] == "TEST SATA SSD"
    assert info["serial"] == "SN123"
    assert info["firmware"] == "FW1.0"
    assert info["sectors"] == 0x0E8E5000
    assert info["is_ssd"] and info["trim_supported"] and info["trim_drat"]
    assert not info["trim_rzat"]
    assert info["sata_speed_current"] == "6.0 Gb/s"
    assert info["ncq_supported"]


def test_parse_smart():
    data, thr = bytearray(512), bytearray(512)
    # id, flags(2), value, worst, raw(6), reserved
    data[2:14] = bytes([5, 0x33, 0, 100, 100]) + (3).to_bytes(6, "little") + b"\0"
    data[14:26] = bytes([177, 0x13, 0, 4, 4]) + (999).to_bytes(6, "little") + b"\0"
    thr[2:4] = bytes([5, 10])
    thr[14:16] = bytes([177, 5])
    attrs = {a["id"]: a for a in ata.parse_smart(bytes(data), bytes(thr))}
    assert attrs[5]["raw"] == 3 and not attrs[5]["failing"]
    assert attrs[177]["failing"] and attrs[177]["raw"] == 999


def test_expected_data_stamped():
    a = expected_data("random", 8192, 16384, seed=7)
    assert a == expected_data("random", 8192, 16384, seed=7)
    assert a != expected_data("random", 8192, 16384, seed=8)
    magic, off, seed = struct.unpack_from("<8sQQ", a, 4096)
    assert magic == b"SSDTEST\0" and off == 8192 + 4096 and seed == 7


def test_describe_mismatch_detects_misdirected_write():
    exp = expected_data("random", 0, 8192, seed=1)
    actual = bytearray(exp)
    actual[4096:8192] = expected_data("random", 1 << 20, 4096, seed=1)
    count, samples = describe_mismatch(bytes(actual), exp, 0)
    assert count == 1
    assert samples[0]["offset"] == 4096
    assert samples[0]["found_stamp_offset"] == 1 << 20


def test_verify_passes_on_file(image):
    with BlockDevice(image, writable=True) as dev:
        ctx = Context(dev, 0, 4 * MiB, block_size=MiB, seed=3, log=lambda *a, **k: None)
        res = cases.test_verify(ctx)
    assert res.status == "PASS", res.message


def test_cli_requires_destructive(image, capsys):
    assert cli.run([image, "-t", "seq_write"]) == 2
    assert "--destructive" in capsys.readouterr().err


def test_cli_full_run_on_file(image, tmp_path):
    report = tmp_path / "r.json"
    rc = cli.run([image, "--destructive", "-y", "--span", "4M", "--duration", "0.3",
                  "--qd", "2", "--json", str(report)])
    assert rc == 0
    data = json.loads(report.read_text())
    status = {r["name"]: r["status"] for r in data["results"]}
    assert status["verify"] == "PASS"
    assert status["identify"] == "SKIP" and status["trim"] == "SKIP"
    assert data["overall"] == "PASS"


def test_cli_min_limit_fails(image):
    assert cli.run([image, "-t", "seq_read", "--span", "1M", "--min-seq-read", "1e12"]) == 1
