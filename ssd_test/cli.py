"""Command line entry point."""

import argparse
import json
import os
import sys
import time

from . import __version__
from .device import BlockDevice, DeviceError, mounted_partitions
from .tests import FULL_DEFAULT, SAFE_DEFAULT, TESTS, Context, Result

MiB = 1024 * 1024


def parse_size(text):
    units = {"k": 1024, "m": MiB, "g": 1024 * MiB, "t": 1024 ** 4}
    text = text.strip().lower()
    for suffix in ("ib", "b"):
        if text.endswith(suffix) and text[-len(suffix) - 1:-len(suffix)] in units:
            text = text[:-len(suffix)]
            break
    if text and text[-1] in units:
        return int(float(text[:-1]) * units[text[-1]])
    return int(text)


def build_parser():
    p = argparse.ArgumentParser(
        prog="ssd_test",
        description="SATA SSD test program: identify, SMART, performance, integrity, TRIM.")
    p.add_argument("device", help="block device (e.g. /dev/sdb) or a regular file for dry runs")
    p.add_argument("-t", "--tests", default=None,
                   help=f"comma separated tests. available: {','.join(TESTS)}. "
                        f"default: {','.join(SAFE_DEFAULT)} (read-only), or the full "
                        "suite when --destructive is given")
    p.add_argument("--destructive", action="store_true",
                   help="allow tests that WRITE to the device (destroys data)")
    p.add_argument("-y", "--yes", action="store_true", help="skip the interactive confirmation")
    p.add_argument("--offset", type=parse_size, default=0, help="start of test region (default 0)")
    p.add_argument("--span", type=parse_size, default=None,
                   help="size of test region (default 1G; 'all' via --full-span)")
    p.add_argument("--full-span", action="store_true", help="test the whole device")
    p.add_argument("--bs", type=parse_size, default=MiB, help="sequential block size (default 1M)")
    p.add_argument("--io-size", type=parse_size, default=4096, help="random I/O size (default 4K)")
    p.add_argument("--qd", type=int, default=1, help="random I/O queue depth / threads (default 1)")
    p.add_argument("--duration", type=float, default=10.0, help="random test duration seconds")
    p.add_argument("--loops", type=int, default=1, help="repeat the test list N times")
    p.add_argument("--seed", type=int, default=None, help="random seed (default: time based)")
    p.add_argument("--slow-ms", type=float, default=500.0, help="slow I/O threshold in ms")
    p.add_argument("--no-direct", action="store_true", help="do not use O_DIRECT")
    p.add_argument("--json", metavar="FILE", help="write the full report as JSON")
    p.add_argument("--min-seq-read", type=float, help="fail seq_read below this MB/s")
    p.add_argument("--min-seq-write", type=float, help="fail seq_write below this MB/s")
    p.add_argument("--min-rand-read-iops", type=float, help="fail rand_read below this IOPS")
    p.add_argument("--min-rand-write-iops", type=float, help="fail rand_write below this IOPS")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return p


def apply_limits(result, args):
    limits = {
        "seq_read": ("mbps", args.min_seq_read, "MB/s"),
        "seq_write": ("mbps", args.min_seq_write, "MB/s"),
        "rand_read": ("iops", args.min_rand_read_iops, "IOPS"),
        "rand_write": ("iops", args.min_rand_write_iops, "IOPS"),
    }
    key, minimum, unit = limits.get(result.name, (None, None, None))
    if minimum is None or result.status not in ("INFO", "PASS"):
        return
    value = result.metrics.get(key, 0)
    if value < minimum:
        result.status = "FAIL"
        result.message += f" (below limit {minimum:g} {unit})"
    else:
        result.status = "PASS"


def confirm(device, size, tests):
    print(f"\n*** WARNING: tests {', '.join(tests)} will OVERWRITE data on {device} "
          f"({size / 1e9:.1f} GB). ***")
    answer = input(f"Type the device path ({device}) to continue: ")
    return answer.strip() == device


def run(argv=None):
    args = build_parser().parse_args(argv)
    if args.seed is None:
        args.seed = int(time.time()) & 0xFFFFFFFF

    names = args.tests.split(",") if args.tests else (FULL_DEFAULT if args.destructive else SAFE_DEFAULT)
    unknown = [n for n in names if n not in TESTS]
    if unknown:
        print(f"unknown tests: {', '.join(unknown)}", file=sys.stderr)
        return 2
    writing = sorted({n for n in names if TESTS[n][1]})
    if writing and not args.destructive:
        print(f"tests {', '.join(writing)} write to the device; add --destructive", file=sys.stderr)
        return 2

    if not os.path.exists(args.device):
        print(f"{args.device}: not found", file=sys.stderr)
        return 2
    if writing:
        mounts = mounted_partitions(args.device)
        if mounts:
            print("refusing to write, device is mounted:\n  " + "\n  ".join(mounts), file=sys.stderr)
            return 2

    try:
        dev = BlockDevice(args.device, writable=bool(writing), direct=not args.no_direct)
    except (OSError, DeviceError) as e:
        print(f"cannot open {args.device}: {e}", file=sys.stderr)
        return 2

    with dev:
        align = max(dev.logical_block, 4096)
        offset = args.offset - args.offset % align
        span = dev.size - offset if args.full_span else (args.span or 1024 * MiB)
        span = min(span, dev.size - offset)
        span -= span % align
        if span <= 0:
            print("test region is empty (check --offset/--span)", file=sys.stderr)
            return 2
        if args.bs % align or args.io_size % dev.logical_block:
            print(f"--bs must be a multiple of {align}, --io-size of {dev.logical_block}",
                  file=sys.stderr)
            return 2
        if writing and not args.yes and not confirm(args.device, dev.size, writing):
            print("aborted")
            return 1

        print(f"ssd_test {__version__}  device={args.device}  size={dev.size / 1e9:.1f} GB  "
              f"O_DIRECT={'on' if dev.direct else 'off'}  seed={args.seed}")
        print(f"region: offset={offset / MiB:.0f} MiB span={span / MiB:.0f} MiB\n")

        ctx = Context(dev=dev, offset=offset, span=span, block_size=args.bs,
                      io_size=args.io_size, queue_depth=max(1, args.qd),
                      duration=args.duration, seed=args.seed, slow_io_ms=args.slow_ms)

        results = []
        for loop in range(args.loops):
            for name in names:
                label = f"[{loop + 1}/{args.loops}] {name}" if args.loops > 1 else name
                print(f"== {label}")
                func = TESTS[name][0]
                t0 = time.perf_counter()
                try:
                    res = func(ctx)
                except (OSError, DeviceError) as e:
                    res = Result(name, status="FAIL", message=f"I/O error: {e}")
                except KeyboardInterrupt:
                    print("\ninterrupted")
                    res = Result(name, status="FAIL", message="interrupted")
                    res.duration_s = round(time.perf_counter() - t0, 2)
                    results.append(res)
                    print_summary(results)
                    write_json(args, dev, offset, span, results)
                    return 130
                res.duration_s = round(time.perf_counter() - t0, 2)
                apply_limits(res, args)
                print(f"   {res.status:4s}  {res.message}  ({res.duration_s:.1f}s)\n")
                results.append(res)

    print_summary(results)
    write_json(args, dev, offset, span, results)
    return 1 if any(r.status == "FAIL" for r in results) else 0


def print_summary(results):
    print("=" * 72)
    print(f"{'TEST':12s} {'RESULT':6s} DETAIL")
    print("-" * 72)
    for r in results:
        print(f"{r.name:12s} {r.status:6s} {r.message}")
    print("-" * 72)
    failed = sum(r.status == "FAIL" for r in results)
    print(f"OVERALL: {'FAIL' if failed else 'PASS'} ({failed} failed, {len(results)} run)")


def write_json(args, dev, offset, span, results):
    if not args.json:
        return
    report = {
        "version": __version__,
        "device": args.device,
        "size_bytes": dev.size,
        "offset": offset,
        "span": span,
        "seed": args.seed,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "results": [r.__dict__ for r in results],
        "overall": "FAIL" if any(r.status == "FAIL" for r in results) else "PASS",
    }
    with open(args.json, "w") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"JSON report written to {args.json}")


def main():
    sys.exit(run())
