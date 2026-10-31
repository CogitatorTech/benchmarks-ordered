"""Generate readable Markdown reports with tables and charts from benchmark data."""

import argparse
import csv
import json
import math
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]

STRUCTURE_MAP = {
    ("zig", "btree_map"): ("Ordered BTreeMap", "B-tree (16-way)", "Zig Ordered BTree"),
    ("zig", "cartesian_map"): ("Ordered CartesianTreeMap", "Cartesian Tree", "Zig Cartesian"),
    ("zig", "skiplist_map"): ("Ordered SkipListMap", "Skip List", "Zig SkipList"),
    ("zig", "sorted_set"): ("Ordered SortedSet", "Sorted Vector", "Zig SortedSet"),
    ("zig", "redblack_set"): ("Ordered RedBlackTreeSet", "Red-Black Tree", "Zig RedBlack"),
    ("zig", "treap_map"): ("std.Treap (Map)", "Treap", "Zig Treap Map"),
    ("zig", "treap_set"): ("std.Treap (Set)", "Treap", "Zig Treap Set"),
    ("rust", "btree_map"): ("std::collections::BTreeMap", "B-tree", "Rust std BTree"),
    ("rust", "btree_set"): ("std::collections::BTreeSet", "B-tree", "Rust std BTree"),
    ("rust", "indexset_map"): ("indexset::BTreeMap", "Two-Level B-tree", "Rust indexset"),
    ("rust", "indexset_set"): ("indexset::BTreeSet", "Two-Level B-tree", "Rust indexset"),
    ("c", "kbtree_map"): ("Klib kbtree", "B-tree", "C Klib kbtree"),
    ("c", "kbtree_set"): ("Klib kbtree", "B-tree", "C Klib kbtree"),
    ("c", "kavl_map"): ("Klib kavl", "AVL Tree", "C Klib kavl"),
    ("c", "kavl_set"): ("Klib kavl", "AVL Tree", "C Klib kavl"),
    ("c", "btree_map"): ("tidwall/btree.c", "B-tree", "C tidwall btree"),
    ("c", "btree_set"): ("tidwall/btree.c", "B-tree", "C tidwall btree"),
    ("cpp", "std_map"): ("std::map", "Red-Black Tree", "C++ std::map"),
    ("cpp", "std_set"): ("std::set", "Red-Black Tree", "C++ std::set"),
    ("cpp", "absl_map"): ("Abseil btree_map", "B-tree", "C++ Abseil BTree"),
    ("cpp", "absl_set"): ("Abseil btree_set", "B-tree", "C++ Abseil BTree"),
    ("cpp", "boost_flat_map"): ("Boost flat_map", "Flat Sorted Vector", "C++ Boost flat"),
    ("cpp", "boost_flat_set"): ("Boost flat_set", "Flat Sorted Vector", "C++ Boost flat"),
    ("java", "tree_map"): ("java.util.TreeMap", "Red-Black Tree (boxed Long)", "Java TreeMap"),
    ("java", "tree_set"): ("java.util.TreeSet", "Red-Black Tree (boxed Long)", "Java TreeSet"),
    ("java", "fastutil_avl_map"): ("fastutil AVLTreeMap", "AVL Tree (primitive long)", "Java fastutil AVL"),
    ("java", "fastutil_avl_set"): ("fastutil AVLTreeSet", "AVL Tree (primitive long)", "Java fastutil AVL"),
    ("java", "fastutil_rb_map"): ("fastutil RBTreeMap", "Red-Black Tree (primitive long)", "Java fastutil RB"),
    ("java", "fastutil_rb_set"): ("fastutil RBTreeSet", "Red-Black Tree (primitive long)", "Java fastutil RB"),
}

PHASES = ("insert", "hit", "miss", "iterate", "remove")


def find_latest_results(base_dir=None):
    results_dir = Path(base_dir or ROOT / "results")
    if not results_dir.exists():
        raise FileNotFoundError(f"Results directory not found: {results_dir}")
    candidates = [
        d
        for d in results_dir.iterdir()
        if d.is_dir()
        and ((d / "summary.csv").exists() or (d / "samples.csv").exists())
    ]
    if not candidates:
        raise FileNotFoundError(f"No benchmark results found in {results_dir}")
    return max(candidates, key=lambda d: d.name)


def load_records(result_dir):
    summary_path = result_dir / "summary.csv"
    if summary_path.exists():
        with summary_path.open("r", newline="") as f:
            reader = csv.DictReader(f)
            records = []
            for r in reader:
                records.append({
                    "language": r["language"],
                    "implementation": r["implementation"],
                    "kind": r["kind"],
                    "size": int(r["size"]),
                    "order": r["order"],
                    "phase": r["phase"],
                    "median_ns_per_op": float(r["median_ns_per_op"]),
                    "min_ns_per_op": float(r["min_ns_per_op"]),
                    "max_ns_per_op": float(r["max_ns_per_op"]),
                    "samples": int(r["samples"]),
                })
            return records

    samples_path = result_dir / "samples.csv"
    if not samples_path.exists():
        raise FileNotFoundError(f"Neither summary.csv nor samples.csv found in {result_dir}")

    groups = {}
    with samples_path.open("r", newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            key = (
                r["language"],
                r["implementation"],
                r["kind"],
                int(r["size"]),
                r["order"],
                r["phase"],
            )
            groups.setdefault(key, []).append(float(r["ns_per_op"]))

    records = []
    for key, values in groups.items():
        records.append({
            "language": key[0],
            "implementation": key[1],
            "kind": key[2],
            "size": key[3],
            "order": key[4],
            "phase": key[5],
            "median_ns_per_op": statistics.median(values),
            "min_ns_per_op": min(values),
            "max_ns_per_op": max(values),
            "samples": len(values),
        })
    return records


def load_metadata(result_dir):
    meta_path = result_dir / "metadata.json"
    if meta_path.exists():
        try:
            return json.loads(meta_path.read_text())
        except Exception:
            return {}
    return {}


def render_environment(meta):
    lines = [
        "## System Environment and Metadata",
        "",
        "| Attribute | Value |",
        "|---|---|",
    ]
    cpu = meta.get("cpu", "Unknown")
    platform_info = meta.get("platform", "Unknown")
    governor = meta.get("governor", "Unknown")
    started = meta.get("started_utc", "Unknown")
    allocator = meta.get("native_allocator", "system malloc")
    c_flags = meta.get("native_flags", "Release mode")
    java_heap = meta.get("java_heap", "-Xms1g -Xmx1g")
    revision = meta.get("revision", "Unknown")

    lines.append(f"| CPU | `{cpu}` |")
    lines.append(f"| Operating System | `{platform_info}` |")
    lines.append(f"| CPU Frequency Governor | `{governor}` |")
    lines.append(f"| Native Allocator | `{allocator}` |")
    lines.append(f"| Compiler Optimization Flags | `{c_flags}` |")
    lines.append(f"| Java Heap Settings | `{java_heap}` |")
    lines.append(f"| Git Revision | `{revision}` |")
    lines.append(f"| Timestamp (UTC) | `{started}` |")

    versions = meta.get("versions", {})
    if versions:
        version_summary = ", ".join(
            f"{lang}: {ver.splitlines()[0]}" for lang, ver in versions.items()
        )
        lines.append(f"| Toolchain Versions | {version_summary} |")

    lines.append("")
    return "\n".join(lines)


def render_interpretation_guide():
    return """## Performance Interpretation Guide

This benchmark isolates five fundamental phases of sorted container operations:
- **Insert**: Time to insert $N$ keys into an initially empty container. For native implementations, this includes memory allocation. For ascending input, sequential B-tree optimizations are highlighted; for shuffled input, balancing overhead is tested.
- **Lookup Hit**: Time to query $N$ keys that exist in the container. Measures pointer indirection, cache locality, and branching.
- **Lookup Miss**: Time to query $N$ absent keys interleaved between existing keys. Tests traversal depth and early exit efficiency.
- **Iterate**: Time to perform an in-order scan across all elements. Highlights cache line density and memory locality (e.g. flat arrays and B-tree leaf nodes versus pointer-chasing binary trees).
- **Remove**: Time to remove all $N$ keys until the container is empty. Native runners include node deallocation time.

The lowest latency value for each operation column in the tables below is displayed in **bold**.

### Key Architectural Comparisons

1. **B-Trees versus Binary Trees**:
   B-trees (Ordered `BTreeMap`, Rust `BTreeMap`, Abseil `btree_map`, and Klib `kbtree`) pack multiple keys per node. This lowers pointer chasing and improves cache locality compared to node-allocated trees (`std::map`, Java `TreeMap`, and Zig `RedBlackTreeSet`).
2. **Intrusive and Dedicated AVL Trees**:
   Klib `kavl` and fastutil `AVLTreeMap` use strict AVL height balancing. This leads to shorter branch heights than red-black trees, trading slightly slower insertions for faster lookups.
3. **Flat Arrays**:
   Boost `flat_map` and `flat_set` store elements in contiguous sorted memory. Sorted iteration and lookups are fast, but random insertions and removals require shifting elements ($O(N)$ per operation), making large random mutation workloads expensive.
4. **Java Boxed Collections versus Primitive Specialization**:
   Java's standard `TreeMap<Long, Long>` stores boxed object pointers, incurring substantial GC and pointer overhead. The `fastutil` collections operate directly on primitive 64-bit integers (`long`), demonstrating the true algorithmic capacity of the JVM without object wrappers.
"""


def format_metric(val, best_val):
    if val is None:
        return "-"
    formatted = f"{val:.2f}"
    if best_val is not None and formatted == f"{best_val:.2f}":
        return f"**{formatted}**"
    return formatted


def render_chart(title, x_labels, values, y_label="Time (ns/op)"):
    if not x_labels or not values:
        return ""
    max_val = max(values)
    upper_bound = math.ceil(max_val * 1.15) if max_val > 0 else 10
    if upper_bound == 0:
        upper_bound = 10

    labels_str = ", ".join(f'"{lbl}"' for lbl in x_labels)
    values_str = ", ".join(f"{v:.2f}" for v in values)

    return f"""```mermaid
xychart-beta
    title "{title}"
    x-axis [{labels_str}]
    y-axis "{y_label}" 0 --> {upper_bound}
    bar [{values_str}]
```
"""


def generate_report(records, metadata):
    lines = [
        "# Benchmark Report: Sorted Maps and Sets",
        "",
        "This report provides structured comparison tables and visual charts generated from benchmark results.",
        "",
    ]

    lines.append(render_environment(metadata))
    lines.append(render_interpretation_guide())

    combos = sorted({(r["size"], r["order"]) for r in records})

    lines.append("## Benchmark Results by Workload")
    lines.append("")

    for size, order in combos:
        size_label = f"{size:,}"
        order_title = "Ascending Keys" if order == "ascending" else "Shuffled Keys"
        lines.append(f"### Workload: Size = {size_label} Elements ({order_title})")
        lines.append("")

        for kind in ("map", "set"):
            kind_title = "Sorted Maps" if kind == "map" else "Sorted Sets"
            lines.append(f"#### {kind_title}")
            lines.append("")

            matching = [
                r
                for r in records
                if r["size"] == size and r["order"] == order and r["kind"] == kind
            ]
            if not matching:
                continue

            by_impl = {}
            for r in matching:
                key = (r["language"], r["implementation"])
                by_impl.setdefault(key, {})[r["phase"]] = r["median_ns_per_op"]

            sorted_impls = sorted(by_impl.keys(), key=lambda k: (k[0], k[1]))

            best_by_phase = {}
            for phase in PHASES:
                vals = [
                    phases[phase]
                    for phases in by_impl.values()
                    if phase in phases and phases[phase] > 0
                ]
                if vals:
                    best_by_phase[phase] = min(vals)

            chart_labels = []
            chart_hit_values = []
            chart_iter_values = []

            table_rows = [
                "| Language | Implementation | Data Structure | Insert (ns/op) | Lookup Hit (ns/op) | Lookup Miss (ns/op) | Iterate (ns/op) | Remove (ns/op) |",
                "|---|---|---|---|---|---|---|---|",
            ]

            for lang, impl in sorted_impls:
                phases = by_impl[(lang, impl)]
                mapping = STRUCTURE_MAP.get(
                    (lang, impl), (impl, "Unknown", impl)
                )
                friendly_name = mapping[0]
                structure = mapping[1]
                short_label = mapping[2] if len(mapping) > 2 else friendly_name

                insert_str = format_metric(phases.get("insert"), best_by_phase.get("insert"))
                hit_str = format_metric(phases.get("hit"), best_by_phase.get("hit"))
                miss_str = format_metric(phases.get("miss"), best_by_phase.get("miss"))
                iter_str = format_metric(phases.get("iterate"), best_by_phase.get("iterate"))
                remove_str = format_metric(phases.get("remove"), best_by_phase.get("remove"))

                table_rows.append(
                    f"| {lang} | {friendly_name} | {structure} | {insert_str} | {hit_str} | {miss_str} | {iter_str} | {remove_str} |"
                )

                chart_labels.append(short_label)
                chart_hit_values.append(phases.get("hit", 0.0))
                chart_iter_values.append(phases.get("iterate", 0.0))

            lines.append("\n".join(table_rows))
            lines.append("")

            chart_title_hit = f"{kind_title}: Lookup Hit Latency (N = {size_label}, {order_title})"
            lines.append(render_chart(chart_title_hit, chart_labels, chart_hit_values))

            chart_title_iter = f"{kind_title}: Sorted Iteration Latency (N = {size_label}, {order_title})"
            lines.append(render_chart(chart_title_iter, chart_labels, chart_iter_values))

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--results",
        type=Path,
        help="Path to results directory containing summary.csv or samples.csv (default: latest)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "REPORT.md",
        help="Destination path for generated markdown report (default: REPORT.md)",
    )
    args = parser.parse_args()

    results_dir = args.results or find_latest_results()
    print(f"Reading benchmark results from: {results_dir}")

    records = load_records(results_dir)
    metadata = load_metadata(results_dir)
    report_md = generate_report(records, metadata)

    args.output.write_text(report_md)
    print(f"Report written to: {args.output}")

    in_dir_report = results_dir / "REPORT.md"
    in_dir_report.write_text(report_md)
    print(f"Copy written to: {in_dir_report}")


if __name__ == "__main__":
    main()
