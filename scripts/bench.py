"""Build and run reproducible sorted collection comparisons."""

import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import random
import shutil
import statistics
import struct
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build"
IMPLS = {
    "zig": ["btree_map", "cartesian_map", "skiplist_map", "sorted_set", "redblack_set", "treap_map", "treap_set"],
    "rust": ["btree_map", "btree_set"],
    "c": ["kbtree_map", "kbtree_set"],
    "cpp": ["std_map", "std_set", "absl_map", "absl_set"],
    "java": ["tree_map", "tree_set"],
}
PHASES = ("insert", "hit", "miss", "iterate", "remove")


def run(cmd, **kwargs):
    return subprocess.run([str(x) for x in cmd], check=True, **kwargs)


def fixture(path, size, order):
    """The file is little-endian u64 count followed by three i64 key arrays."""
    insertion = list(range(0, size * 2, 2))
    if order == "shuffled":
        random.Random(42).shuffle(insertion)
    lookup = list(range(0, size * 2, 2))
    removal = lookup.copy()
    random.Random(43).shuffle(lookup)
    random.Random(44).shuffle(removal)
    with path.open("wb") as out:
        out.write(struct.pack("<Q", size))
        for keys in (insertion, lookup, removal):
            out.write(struct.pack(f"<{size}q", *keys))


def require_env():
    for var in ("ORDERED_SOURCE", "KLIB_SOURCE", "ABSEIL_PREFIX"):
        if var not in os.environ:
            raise RuntimeError("Enter nix develop before building or running benchmarks")


def build(languages):
    require_env()
    BUILD.mkdir(exist_ok=True)
    if "zig" in languages:
        run([os.environ.get("ZIG", "zig"), "build", "-Doptimize=ReleaseFast", "-Dordered=" + os.environ["ORDERED_SOURCE"]], cwd=ROOT)
    if "rust" in languages:
        run([os.environ.get("CARGO", "cargo"), "build", "--manifest-path", ROOT / "benchmarks/rust/Cargo.toml", "--release", "--locked"], cwd=ROOT)
    if "c" in languages:
        for kind in ("map", "set"):
            flags = ["-DBENCH_SET"] if kind == "set" else []
            run(["cc", "-O3", "-std=c11", "-Wall", "-Wextra", "-I", ROOT / "benchmarks/common", *flags, "-I" + os.environ["KLIB_SOURCE"], ROOT / "benchmarks/c/main.c", "-o", BUILD / ("c-" + kind)])
    if "cpp" in languages:
        run(["cmake", "-S", ROOT, "-B", BUILD / "cpp-build", "-G", "Ninja", "-DCMAKE_BUILD_TYPE=Release", "-DCMAKE_PREFIX_PATH=" + os.environ["ABSEIL_PREFIX"]])
        run(["cmake", "--build", BUILD / "cpp-build"])
    if "java" in languages:
        run(["mvn", "-q", "-f", ROOT / "benchmarks/java/pom.xml", "clean", "package"], cwd=ROOT)


def native_command(language, impl, data):
    exe = {"zig": ROOT / "zig-out/bin/zig-bench", "rust": ROOT / "benchmarks/rust/target/release/rust-bench", "c": BUILD / ("c-set" if impl.endswith("set") else "c-map"), "cpp": BUILD / "cpp-build/cpp-bench"}[language]
    return [exe, impl, data]


def parse_native(output):
    rows = list(csv.reader(output.splitlines()))
    if len(rows) != len(PHASES) or any(len(r) != 2 for r in rows) or tuple(r[0] for r in rows) != PHASES:
        raise ValueError("Runner returned an incomplete or unordered phase list")
    result = {}
    for phase, elapsed in rows:
        ns = int(elapsed)
        if ns < 0:
            raise ValueError("Negative elapsed time")
        result[phase] = ns
    return result


def jmh_samples(results, forks, samples):
    phases = [r["benchmark"].rsplit(".", 1)[1] for r in results]
    if sorted(phases) != sorted(PHASES):
        raise ValueError("JMH did not return every phase exactly once")
    for phase, result in zip(phases, results):
        metric = result["primaryMetric"]
        if metric["scoreUnit"] != "ns/op" or len(metric["rawData"]) != forks:
            raise ValueError("Unexpected JMH units or fork count")
        for fork, values in enumerate(metric["rawData"]):
            if len(values) != samples:
                raise ValueError("Unexpected JMH sample count")
            for sample, ns in enumerate(values):
                if not math.isfinite(ns) or ns < 0:
                    raise ValueError("Invalid JMH time")
                yield phase, fork, sample, ns


def metadata(languages):
    versions = {}
    for name, cmd in {"zig": [os.environ.get("ZIG", "zig"), "version"], "rust": ["rustc", "--version"], "c": ["cc", "--version"], "cpp": ["c++", "--version"], "java": ["java", "-version"]}.items():
        if name in languages:
            version = run(cmd, capture_output=True, text=True)
            versions[name] = (version.stdout.strip() or version.stderr.strip())
    revision = run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip() if (ROOT / ".git").exists() else "staged"
    status = run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True).stdout if (ROOT / ".git").exists() else "staged"
    cpu = platform.processor()
    if Path("/proc/cpuinfo").exists():
        cpu = next((s.split(":", 1)[1].strip() for s in Path("/proc/cpuinfo").read_text().splitlines() if s.startswith("model name")), cpu)
    ordered_path = Path(os.environ["ORDERED_SOURCE"])
    ordered_git = None
    if (ordered_path / ".git").exists():
        ordered_git = {
            "revision": run(["git", "rev-parse", "HEAD"], cwd=ordered_path, capture_output=True, text=True).stdout.strip(),
            "status": run(["git", "status", "--porcelain"], cwd=ordered_path, capture_output=True, text=True).stdout,
            "diff": run(["git", "diff", "HEAD"], cwd=ordered_path, capture_output=True, text=True).stdout,
        }
    governor = Path("/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor")
    return {"started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "ordered_git": ordered_git,
            "affinity": sorted(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else None,
            "governor": governor.read_text().strip() if governor.exists() else None,
            "platform": platform.platform(), "cpu": cpu, "python": sys.version, "versions": versions,
            "revision": revision, "dirty": bool(status), "git_status": status,
            "ordered_source": os.environ.get("ORDERED_SOURCE"), "klib_source": os.environ.get("KLIB_SOURCE"),
            "abseil_prefix": os.environ.get("ABSEIL_PREFIX"), "flake_lock": json.loads((ROOT / "flake.lock").read_text()),
            "argv": sys.argv, "native_allocator": "system malloc; Zig libc_allocator", "native_flags": "ReleaseFast / Cargo release / -O3 / CMake Release", "java_heap": "-Xms1g -Xmx1g"}


def bench(args, languages):
    require_env()
    sizes = [int(n) for n in args.sizes.split(",")]
    if any(n <= 0 or n > 10_000_000 for n in sizes):
        raise ValueError("Sizes must be between 1 and 10000000")
    dest = Path(args.output or ROOT / "results" / time.strftime("%Y%m%d-%H%M%S"))
    dest.mkdir(parents=True, exist_ok=False)
    (dest / "metadata.json").write_text(json.dumps(metadata(languages), indent=2) + "\n")
    shutil.copyfile(ROOT / "flake.lock", dest / "flake.lock")
    samples = []
    with (dest / "samples.csv").open("w", newline="") as out:
        writer = csv.writer(out)
        header = ["language", "implementation", "kind", "size", "order", "phase", "fork", "sample", "ns_per_op"]
        writer.writerow(header)
        for size in sizes:
            for order in ("ascending", "shuffled"):
                data = dest / f"{size}-{order}.bin"
                fixture(data, size, order)
                (dest / f"{size}-{order}.sha256").write_text(hashlib.sha256(data.read_bytes()).hexdigest() + "\n")
                for language in languages:
                    warmups = args.warmups if args.warmups is not None else (20 if language == "java" else 3)
                    for impl in IMPLS[language]:
                        kind = "set" if impl.endswith("set") else "map"
                        print(f"{language} {impl} {size} {order}", flush=True)
                        if language == "java":
                            result = dest / f"jmh-{impl}-{size}-{order}.json"
                            cmd = ["java", "-jar", ROOT / "benchmarks/java/target/benchmarks.jar", "bench.CollectionsBench.*", "-p", "implementation=" + impl, "-p", "fixture=" + str(data.resolve()), "-f", str(args.forks), "-wi", str(warmups), "-i", str(args.samples), "-rff", result, "-rf", "json", "-foe", "true"]
                            with (dest / f"jmh-{impl}-{size}-{order}.log").open("w") as log:
                                run(cmd, stdout=log, stderr=subprocess.STDOUT)
                            results = json.loads(result.read_text())
                            for phase, fork, sample, ns in jmh_samples(results, args.forks, args.samples):
                                row = [language, impl, kind, size, order, phase, fork, sample, ns / size]
                                writer.writerow(row)
                                samples.append(row)
                        else:
                            # A process is a fork; warmups and measurements run inside it.
                            cmd = native_command(language, impl, data) + [str(warmups), str(args.samples)]
                            for fork in range(args.forks):
                                result = run(cmd, capture_output=True, text=True)
                                chunks = result.stdout.strip().split("\n\n")
                                if len(chunks) != args.samples:
                                    raise ValueError("Unexpected native sample count")
                                for sample, chunk in enumerate(chunks):
                                    for phase, ns in parse_native(chunk).items():
                                        row = [language, impl, kind, size, order, phase, fork, sample, ns / size]
                                        writer.writerow(row)
                                        samples.append(row)
                        out.flush()
    groups = {}
    for row in samples:
        groups.setdefault(tuple(row[:6]), []).append(row[-1])
    with (dest / "summary.csv").open("w", newline="") as out:
        writer = csv.writer(out)
        writer.writerow(header[:6] + ["median_ns_per_op", "min_ns_per_op", "max_ns_per_op", "samples"])
        for key, values in groups.items():
            writer.writerow([*key, statistics.median(values), min(values), max(values), len(values)])
    print(f"Results: {dest}")


def check(languages):
    import tempfile
    with tempfile.TemporaryDirectory() as temp:
        for size in (0, 1, 2, 31):
            for order in ("ascending", "shuffled"):
                data = Path(temp) / "fixture.bin"
                fixture(data, size, order)
                for language in languages:
                    if language == "java":
                        run(["java", "-cp", ROOT / "benchmarks/java/target/benchmarks.jar", "bench.CollectionsBench", data])
                    else:
                        for impl in IMPLS[language]:
                            result = run(native_command(language, impl, data) + ["0", "1"], capture_output=True, text=True)
                            parse_native(result.stdout.strip())
    print("All selected implementations passed edge fixtures.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("build", "test", "bench"))
    parser.add_argument("--languages", default=",".join(IMPLS))
    parser.add_argument("--sizes", default="1000,100000,1000000")
    parser.add_argument("--warmups", type=int, help="Override native (3) and Java (20) warmup counts")
    parser.add_argument("--samples", type=int, default=5)
    parser.add_argument("--forks", type=int, default=2)
    parser.add_argument("--output")
    args = parser.parse_args()
    languages = args.languages.split(",")
    if any(lang not in IMPLS for lang in languages) or len(set(languages)) != len(languages):
        parser.error("Languages must be known and unique")
    if (args.warmups is not None and args.warmups < 0) or args.samples < 1 or args.forks < 1:
        parser.error("Nonnegative warmups and positive samples and forks are required")
    if args.action in ("build", "test"):
        build(languages)
    if args.action == "test":
        check(languages)
    if args.action == "bench":
        bench(args, languages)


if __name__ == "__main__":
    main()
