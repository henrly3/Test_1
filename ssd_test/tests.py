"""Test cases. Each test takes a Context and returns a Result."""

import os
import random
import struct
import threading
import time
from dataclasses import dataclass, field

from .ata import SMART_CRITICAL_RAW, AtaDevice, AtaError
from .device import DeviceError, aligned_buffer

MiB = 1024 * 1024
STAMP_UNIT = 4096
STAMP_MAGIC = b"SSDTEST\0"
STAMP = struct.Struct("<8sQQ")


@dataclass
class Result:
    name: str
    status: str = "PASS"  # PASS / FAIL / SKIP / INFO
    message: str = ""
    metrics: dict = field(default_factory=dict)
    duration_s: float = 0.0


@dataclass
class Context:
    dev: object
    offset: int
    span: int
    block_size: int = MiB
    io_size: int = 4096
    queue_depth: int = 1
    duration: float = 10.0
    seed: int = 0
    slow_io_ms: float = 500.0
    identify: dict = None
    log: object = print


# ---------------------------------------------------------------- helpers

def _chunks(ctx, bs=None):
    bs = bs or ctx.block_size
    pos, end = ctx.offset, ctx.offset + ctx.span
    while pos < end:
        n = min(bs, end - pos)
        yield pos, n
        pos += n


def _progress(ctx, label, done, total, start):
    elapsed = time.perf_counter() - start
    mbps = done / MiB / elapsed if elapsed else 0.0
    ctx.log(f"\r  {label}: {done * 100 // total:3d}%  {mbps:8.1f} MB/s", end="", flush=True)


def _percentile(sorted_vals, p):
    if not sorted_vals:
        return 0.0
    k = min(len(sorted_vals) - 1, int(round(p / 100.0 * (len(sorted_vals) - 1))))
    return sorted_vals[k]


def _latency_stats(lat_ns):
    lat_ns.sort()
    us = [v / 1000.0 for v in lat_ns]
    return {
        "lat_avg_us": round(sum(us) / len(us), 1) if us else 0.0,
        "lat_p50_us": round(_percentile(us, 50), 1),
        "lat_p99_us": round(_percentile(us, 99), 1),
        "lat_p999_us": round(_percentile(us, 99.9), 1),
        "lat_max_us": round(us[-1], 1) if us else 0.0,
    }


def expected_data(pattern, offset, length, seed):
    """Deterministic expected content for [offset, offset+length)."""
    if pattern == "zeros":
        return bytes(length)
    if pattern == "ones":
        return b"\xff" * length
    if pattern == "checker":
        return b"\xaa\x55" * (length // 2)
    if pattern == "random":
        rnd = random.Random(seed * 1_000_003 + offset // STAMP_UNIT)
        data = bytearray(rnd.randbytes(length))
        for pos in range(0, length, STAMP_UNIT):
            # Stamp each 4K unit with its own address so misdirected or
            # stale writes are detected, not only bit flips.
            STAMP.pack_into(data, pos, STAMP_MAGIC, offset + pos, seed)
        return bytes(data)
    raise ValueError(f"unknown pattern {pattern}")


def describe_mismatch(actual, expected, base_offset, limit=10):
    bad = []
    for pos in range(0, len(expected), STAMP_UNIT):
        a = actual[pos:pos + STAMP_UNIT]
        e = expected[pos:pos + STAMP_UNIT]
        if a != e:
            info = {"offset": base_offset + pos}
            magic, stamped_off, stamped_seed = STAMP.unpack_from(a, 0)
            if magic == STAMP_MAGIC:
                info["found_stamp_offset"] = stamped_off
                info["found_stamp_seed"] = stamped_seed
            info["bit_errors"] = sum(bin(x ^ y).count("1") for x, y in zip(a, e))
            bad.append(info)
    return len(bad), bad[:limit]


# ---------------------------------------------------------------- info tests

def test_identify(ctx):
    r = Result("identify", status="INFO")
    if not ctx.dev.is_block:
        r.status, r.message = "SKIP", "not a block device"
        return r
    try:
        info = AtaDevice(ctx.dev.fd).identify()
    except AtaError as e:
        r.status, r.message = "SKIP", f"ATA IDENTIFY unavailable: {e}"
        return r
    ctx.identify = info
    r.metrics = info
    r.message = (f"{info['model']} FW {info['firmware']} S/N {info['serial']}, "
                 f"{info['capacity_bytes'] / 1e9:.1f} GB, link {info['sata_speed_current']}")
    if not info["is_ssd"]:
        r.message += " (WARNING: drive does not report as non-rotating)"
    return r


def test_smart(ctx):
    r = Result("smart")
    if not ctx.dev.is_block:
        r.status, r.message = "SKIP", "not a block device"
        return r
    ata = AtaDevice(ctx.dev.fd)
    try:
        attrs = ata.smart_attributes()
        health = ata.smart_health_ok()
    except AtaError as e:
        r.status, r.message = "SKIP", f"SMART unavailable: {e}"
        return r
    failing = [a for a in attrs if a["failing"]]
    critical = [a for a in attrs if a["id"] in SMART_CRITICAL_RAW and a["raw"] > 0]
    r.metrics = {"health": health, "attributes": attrs}
    problems = []
    if health is False:
        problems.append("overall health FAILED")
    if failing:
        problems.append("below threshold: " + ", ".join(f"{a['id']} {a['name']}" for a in failing))
    if problems:
        r.status = "FAIL"
    if critical:
        problems.append("non-zero raw: " + ", ".join(f"{a['name']}={a['raw']}" for a in critical))
    temp = next((a["raw"] & 0xFF for a in attrs if a["id"] == 194), None)
    if temp is not None:
        r.metrics["temperature_c"] = temp
    r.message = "; ".join(problems) or f"health {'OK' if health else 'unknown'}, {len(attrs)} attributes"
    return r


# ---------------------------------------------------------------- performance

def _sequential(ctx, write):
    name = "seq_write" if write else "seq_read"
    r = Result(name, status="INFO")
    buf = aligned_buffer(ctx.block_size)
    if write:
        buf[:] = random.Random(ctx.seed).randbytes(ctx.block_size)
    ctx.dev.drop_cache()
    done, slow, lat = 0, 0, []
    start = time.perf_counter()
    for off, n in _chunks(ctx):
        view = memoryview(buf)[:n]
        t0 = time.perf_counter_ns()
        (ctx.dev.write_from if write else ctx.dev.read_into)(view, off)
        dt = time.perf_counter_ns() - t0
        lat.append(dt)
        if dt > ctx.slow_io_ms * 1e6:
            slow += 1
        done += n
        if len(lat) % 64 == 0:
            _progress(ctx, name, done, ctx.span, start)
    if write:
        ctx.dev.flush()
    elapsed = time.perf_counter() - start
    ctx.log("")
    r.metrics = {"bytes": done, "block_size": ctx.block_size,
                 "mbps": round(done / MiB / elapsed, 1), "slow_ios": slow}
    r.metrics.update(_latency_stats(lat))
    r.message = f"{r.metrics['mbps']} MB/s ({ctx.block_size // 1024} KiB blocks)"
    return r


def test_seq_read(ctx):
    return _sequential(ctx, write=False)


def test_seq_write(ctx):
    return _sequential(ctx, write=True)


def _random(ctx, write):
    name = "rand_write" if write else "rand_read"
    r = Result(name, status="INFO")
    bs = ctx.io_size
    slots = ctx.span // bs
    if slots == 0:
        r.status, r.message = "SKIP", "span smaller than io size"
        return r
    deadline = time.perf_counter() + ctx.duration
    lats, errors = [], []
    lock = threading.Lock()

    def worker(idx):
        rnd = random.Random(ctx.seed + idx)
        buf = aligned_buffer(bs)
        if write:
            buf[:] = rnd.randbytes(bs)
        op = ctx.dev.write_from if write else ctx.dev.read_into
        local = []
        try:
            while time.perf_counter() < deadline:
                off = ctx.offset + rnd.randrange(slots) * bs
                t0 = time.perf_counter_ns()
                op(buf, off)
                local.append(time.perf_counter_ns() - t0)
        except (OSError, DeviceError) as e:
            errors.append(str(e))
        with lock:
            lats.extend(local)

    start = time.perf_counter()
    threads = [threading.Thread(target=worker, args=(i,)) for i in range(ctx.queue_depth)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    if write:
        ctx.dev.flush()
    elapsed = time.perf_counter() - start
    ios = len(lats)
    r.metrics = {"ios": ios, "io_size": bs, "queue_depth": ctx.queue_depth,
                 "iops": round(ios / elapsed), "mbps": round(ios * bs / MiB / elapsed, 1)}
    r.metrics.update(_latency_stats(lats))
    r.message = (f"{r.metrics['iops']} IOPS, {r.metrics['mbps']} MB/s "
                 f"({bs // 1024} KiB QD{ctx.queue_depth}), p99 {r.metrics['lat_p99_us']} us")
    if errors:
        r.status, r.message = "FAIL", f"{len(errors)} I/O errors, first: {errors[0]}"
    return r


def test_rand_read(ctx):
    return _random(ctx, write=False)


def test_rand_write(ctx):
    return _random(ctx, write=True)


# ---------------------------------------------------------------- integrity

def test_read_scan(ctx):
    """Read the whole region; report I/O errors and slow blocks."""
    r = Result("read_scan")
    buf = aligned_buffer(ctx.block_size)
    errors, slow = [], []
    done = 0
    start = time.perf_counter()
    for i, (off, n) in enumerate(_chunks(ctx)):
        t0 = time.perf_counter()
        try:
            ctx.dev.read_into(memoryview(buf)[:n], off)
        except (OSError, DeviceError) as e:
            errors.append({"offset": off, "error": str(e)})
        dt_ms = (time.perf_counter() - t0) * 1000
        if dt_ms > ctx.slow_io_ms:
            slow.append({"offset": off, "ms": round(dt_ms, 1)})
        done += n
        if i % 64 == 0:
            _progress(ctx, "read_scan", done, ctx.span, start)
    ctx.log("")
    r.metrics = {"bytes": done, "read_errors": len(errors), "slow_blocks": len(slow),
                 "errors": errors[:20], "slow": slow[:20]}
    if errors:
        r.status = "FAIL"
    r.message = f"{len(errors)} read errors, {len(slow)} blocks slower than {ctx.slow_io_ms:g} ms"
    return r


def test_verify(ctx, patterns=("zeros", "ones", "checker", "random")):
    """Write each pattern over the region, read it back and compare."""
    r = Result("verify")
    buf = aligned_buffer(ctx.block_size)
    total_bad = 0
    details = {}
    for pattern in patterns:
        start = time.perf_counter()
        for i, (off, n) in enumerate(_chunks(ctx)):
            buf[:n] = expected_data(pattern, off, n, ctx.seed)
            ctx.dev.write_from(memoryview(buf)[:n], off)
            if i % 64 == 0:
                _progress(ctx, f"write {pattern:7s}", off - ctx.offset + n, ctx.span, start)
        ctx.dev.flush()
        ctx.dev.drop_cache()
        ctx.log("")

        bad_units, samples = 0, []
        start = time.perf_counter()
        for i, (off, n) in enumerate(_chunks(ctx)):
            ctx.dev.read_into(memoryview(buf)[:n], off)
            expected = expected_data(pattern, off, n, ctx.seed)
            if buf[:n] != expected:
                count, s = describe_mismatch(buf[:n], expected, off)
                bad_units += count
                samples.extend(s[:10 - len(samples)])
            if i % 64 == 0:
                _progress(ctx, f"read  {pattern:7s}", off - ctx.offset + n, ctx.span, start)
        ctx.log("")
        details[pattern] = {"bad_4k_units": bad_units, "samples": samples}
        total_bad += bad_units

    r.metrics = {"patterns": details, "bytes_per_pattern": ctx.span}
    if total_bad:
        r.status = "FAIL"
        r.message = f"{total_bad} corrupted 4 KiB units"
    else:
        r.message = f"{len(patterns)} patterns x {ctx.span / MiB:.0f} MiB verified"
    return r


def test_trim(ctx, length=64 * MiB):
    """Write data, TRIM it, and check what the drive returns afterwards."""
    r = Result("trim", status="INFO")
    if not ctx.dev.is_block:
        r.status, r.message = "SKIP", "not a block device"
        return r
    ident = ctx.identify or {}
    if ident and not ident.get("trim_supported"):
        r.status, r.message = "SKIP", "drive does not report TRIM support"
        return r
    length = min(length, ctx.span)
    sub = Context(ctx.dev, ctx.offset, length, ctx.block_size, seed=ctx.seed, log=ctx.log)
    buf = aligned_buffer(ctx.block_size)
    for off, n in _chunks(sub):
        buf[:n] = expected_data("random", off, n, ctx.seed)
        ctx.dev.write_from(memoryview(buf)[:n], off)
    ctx.dev.flush()

    t0 = time.perf_counter()
    try:
        ctx.dev.discard(ctx.offset, length)
    except OSError as e:
        r.status, r.message = "SKIP", f"BLKDISCARD failed: {e}"
        return r
    trim_ms = (time.perf_counter() - t0) * 1000
    ctx.dev.drop_cache()

    zero, old, other = 0, 0, 0
    for off, n in _chunks(sub):
        ctx.dev.read_into(memoryview(buf)[:n], off)
        data = buf[:n]
        if data == bytes(n):
            zero += n
        elif data == expected_data("random", off, n, ctx.seed):
            old += n
        else:
            other += n
    r.metrics = {"bytes": length, "trim_ms": round(trim_ms, 1),
                 "read_zero_bytes": zero, "read_old_bytes": old, "read_other_bytes": other,
                 "drat": ident.get("trim_drat"), "rzat": ident.get("trim_rzat")}
    r.message = (f"trimmed {length // MiB} MiB in {trim_ms:.1f} ms; after trim: "
                 f"{zero * 100 // length}% zeros, {old * 100 // length}% old data, "
                 f"{other * 100 // length}% other")
    if ident.get("trim_rzat") and zero != length:
        r.status = "FAIL"
        r.message += " (drive claims RZAT but did not return zeros)"
    return r


# ---------------------------------------------------------------- registry

TESTS = {
    "identify":   (test_identify, False),
    "smart":      (test_smart, False),
    "read_scan":  (test_read_scan, False),
    "seq_read":   (test_seq_read, False),
    "rand_read":  (test_rand_read, False),
    "seq_write":  (test_seq_write, True),
    "rand_write": (test_rand_write, True),
    "verify":     (test_verify, True),
    "trim":       (test_trim, True),
}

SAFE_DEFAULT = ["identify", "smart", "read_scan", "seq_read", "rand_read"]
FULL_DEFAULT = ["identify", "smart", "seq_write", "seq_read", "rand_write", "rand_read",
                "verify", "trim", "smart"]
