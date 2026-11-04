"""Generate readable Markdown and HTML reports with tables and charts from benchmark data."""

import argparse
import csv
import html
import json
import math
import shutil
import statistics
import sys
from pathlib import Path

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
    ("java", "fastutil_avl_map"): ("fastutil AVLTreeMap", "AVL Tree (primitive long)",
                                   "Java fastutil AVL"),
    ("java", "fastutil_avl_set"): ("fastutil AVLTreeSet", "AVL Tree (primitive long)",
                                   "Java fastutil AVL"),
    ("java", "fastutil_rb_map"): ("fastutil RBTreeMap", "Red-Black Tree (primitive long)",
                                  "Java fastutil RB"),
    ("java", "fastutil_rb_set"): ("fastutil RBTreeSet", "Red-Black Tree (primitive long)",
                                  "Java fastutil RB"),
}

PHASES = ("insert", "hit", "miss", "iterate", "remove")
DOWNLOADS = ("summary.csv", "samples.csv", "metadata.json", "flake.lock")
LANGUAGE_NAMES = {
    "c": "C",
    "cpp": "C++",
    "java": "Java",
    "rust": "Rust",
    "zig": "Zig",
}


def format_language(lang):
    return LANGUAGE_NAMES.get(lang, lang.capitalize() if lang else "")


def find_latest_results(base_dir=None):
    results_dir = Path(base_dir or ROOT / "results")
    if not results_dir.exists():
        raise FileNotFoundError(f"Results directory not found: {results_dir}")
    candidates = [
        d
        for d in results_dir.iterdir()
        if d.is_dir()
           and (d / "summary.csv").is_file()
    ]
    if not candidates:
        raise FileNotFoundError(f"No completed benchmark results found in {results_dir}")
    return max(candidates, key=lambda d: d.name)


KEY_FIELDS = ("language", "implementation", "kind", "size", "order", "seed", "phase")


def record_key(record):
    return tuple(
        record.get(field, 42) if field == "seed" else record[field] for field in KEY_FIELDS)


def load_records(result_dir):
    records = []
    summary_path = result_dir / "summary.csv"
    if summary_path.exists():
        with summary_path.open(newline="") as source:
            for row in csv.DictReader(source):
                for field in ("size", "samples"):
                    row[field] = int(row[field])
                row["seed"] = int(row.get("seed", 42))
                for field in ("median_ns_per_op", "min_ns_per_op", "max_ns_per_op"):
                    row[field] = float(row[field])
                row["summary_only"] = True
                records.append(row)
        validate_records(records)

    groups = {}
    samples_path = result_dir / "samples.csv"
    if samples_path.exists():
        with samples_path.open(newline="") as source:
            reader = csv.DictReader(source)
            if not set((*KEY_FIELDS[:-2], "phase", "fork", "sample", "ns_per_op")).issubset(
                reader.fieldnames or []):
                raise ValueError("Invalid samples header")
            for row in reader:
                row["size"] = int(row["size"])
                row["seed"] = int(row.get("seed", 42))
                value = float(row["ns_per_op"])
                fork, sample = int(row["fork"]), int(row["sample"])
                if not math.isfinite(value) or value < 0 or fork < 0 or sample < 0:
                    raise ValueError("Invalid raw sample")
                group = groups.setdefault(record_key(row), {})
                if (fork, sample) in group:
                    raise ValueError("Duplicate raw sample")
                group[fork, sample] = value
        raw_records = []
        for key, values in groups.items():
            observations = list(values.values())
            forks = sorted({fork for fork, _ in values})
            fork_medians = [
                statistics.median(value for (f, _), value in values.items() if f == fork) for fork
                in forks]
            q1, _, q3 = statistics.quantiles(observations, n=4, method="inclusive") if len(
                observations) > 1 else observations * 3
            raw_records.append(dict(zip(KEY_FIELDS, key),
                                    median_ns_per_op=statistics.median(observations),
                                    min_ns_per_op=min(observations),
                                    max_ns_per_op=max(observations),
                                    samples=len(observations), q1=q1, q3=q3, forks=len(forks),
                                    fork_medians=fork_medians, sample_ids=set(values)))
        validate_records(raw_records)
        if records:
            indexed = {record_key(row): row for row in raw_records}
            if set(indexed) != {record_key(row) for row in records}:
                raise ValueError("Summary and raw sample coverage differ")
            for row in records:
                raw = indexed[record_key(row)]
                if row["samples"] != raw["samples"] or any(
                    not math.isclose(row[field], raw[field], rel_tol=1e-9, abs_tol=1e-12) for field
                    in ("median_ns_per_op", "min_ns_per_op", "max_ns_per_op")):
                    raise ValueError("Summary and raw samples disagree")
                row.update(raw)
        else:
            records = raw_records
    if not records:
        raise ValueError("Benchmark results are empty")
    validate_records(records, load_metadata(result_dir))
    return records


def validate_records(records, metadata=None):
    if not records:
        raise ValueError("Benchmark results are empty")
    groups = {}
    for record in records:
        key = record_key(record)[:-1]
        phase = record["phase"]
        timings = [record[field] for field in
                   ("min_ns_per_op", "median_ns_per_op", "max_ns_per_op")]
        if any(not math.isfinite(v) or v < 0 for v in timings) or timings != sorted(timings):
            raise ValueError(f"Invalid timing values: {key}")
        if record["kind"] not in ("map", "set") or not record["implementation"].endswith(
            "_" + record["kind"]) or record["size"] <= 0 or record["order"] not in ("ascending",
                                                                                    "shuffled"):
            raise ValueError(f"Invalid workload: {key}")
        phases = groups.setdefault(key, {})
        if phase not in PHASES or phase in phases or record["samples"] < 1:
            raise ValueError(f"Invalid benchmark phase or sample count: {key}")
        phases[phase] = record
    for key, phases in groups.items():
        if set(phases) != set(PHASES) or len({r["samples"] for r in phases.values()}) != 1:
            raise ValueError(f"Incomplete benchmark phases or unequal sample counts: {key}")
        if "sample_ids" in next(iter(phases.values())) and len(
            {frozenset(r["sample_ids"]) for r in phases.values()}) != 1:
            raise ValueError(f"Unequal sample identities: {key}")
    meta = metadata or {}
    implementations = meta.get("implementations")
    if implementations is None:
        implementations = {}
        for language, implementation, *_ in groups:
            implementations.setdefault(language, set()).add(implementation)
    sizes = meta.get("sizes", sorted({r["size"] for r in records}))
    orders = meta.get("orders", sorted({r["order"] for r in records}))
    seeds = meta.get("seeds", sorted({r.get("seed", 42) for r in records}))
    expected = {(lang, impl, "set" if impl.endswith("set") else "map", size, order, seed)
                for lang, impls in implementations.items() for impl in impls
                for size in sizes for order in orders for seed in seeds}
    if set(groups) != expected:
        raise ValueError("Incomplete implementation or workload coverage")
    if "samples_per_fork" in meta:
        identities = {(fork, sample) for fork in range(meta["forks"]) for sample in
                      range(meta["samples_per_fork"])}
        for row in records:
            if row["samples"] != len(identities) or (
                "sample_ids" in row and row["sample_ids"] != identities):
                raise ValueError("Samples differ from the recorded run configuration")


def load_metadata(result_dir):
    meta_path = result_dir / "metadata.json"
    if meta_path.exists():
        meta = json.loads(meta_path.read_text())
        if not isinstance(meta, dict):
            raise ValueError("Metadata must be an object")
        return meta
    return {}


def provenance_rows(meta):
    return [("Runner environment", meta.get("runner_environment", "Unknown")),
            ("Dirty working tree", meta.get("dirty", "Unknown")),
            ("Ordered source", meta.get("ordered_source", "Unknown")),
            ("Ordered local revision and changes",
             meta.get("ordered_git", "No local Git information")),
            ("CPU affinity", meta.get("affinity", "Unknown")),
            ("Warmups by language", meta.get("warmups", "Unknown")),
            ("Samples per fork", meta.get("samples_per_fork", "Unknown")),
            ("Forks", meta.get("forks", "Unknown")),
            ("Fixture seeds", meta.get("seeds", "Legacy seed 42")),
            ("Schedule seed", meta.get("schedule_seed", "Legacy fixed order"))]


def spread_text(record):
    if "q1" not in record:
        return f"Range {record['min_ns_per_op']:.2f}–{record['max_ns_per_op']:.2f}; {record['samples']} samples; IQR and forks unavailable"
    medians = ", ".join(f"{v:.2f}" for v in record["fork_medians"])
    return f"IQR {record['q1']:.2f}–{record['q3']:.2f}; {record['samples']} samples; {record['forks']} forks; fork medians [{medians}]"


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
            f"{format_language(lang)}: {ver.splitlines()[0]}" for lang, ver in versions.items()
        )
        lines.append(f"| Toolchain Versions | {version_summary} |")

    lines.extend(
        f"| {label} | `{str(value).replace(chr(10), ' ').replace('|', '/')}` |" for label, value in
        provenance_rows(meta))
    lines.append("")
    return "\n".join(lines)


def render_interpretation_guide():
    return """## Performance Interpretation Guide

Ascending and shuffled describe insertion order only. Lookup and removal use independent shuffled permutations. Containers are populated and validated before read and removal phases, so these measure recently accessed data. CI timings are exploratory; publish comparisons from a dedicated idle machine with recorded CPU affinity. This benchmark isolates five phases of sorted container operations:
- **Insert**: Time to insert $N$ keys into an initially empty container. Container construction and node allocation are included in new runs. Legacy Java runs excluded empty container construction. For ascending input, sequential B-tree optimizations are highlighted; for shuffled input, balancing overhead is tested.
- **Lookup hit**: Time to query $N$ keys that exist in the container. Measures pointer indirection, cache locality, and branching.
- **Lookup miss**: Time to query $N$ absent keys interleaved between existing keys. Tests traversal depth and early exit efficiency.
- **Iterate**: Time to perform an in-order scan across all elements. Highlights cache line density and memory locality (for example, flat arrays and B-tree leaf nodes versus pointer-chasing binary trees).
- **Remove**: Time to remove all $N$ keys until the container is empty. Native runners include node deallocation time. Java removal unlinks entries and does not force garbage collection.

Bold values mark the lowest measured median, not a proven winner.

### Architectural Comparisons

1. **B-trees versus binary trees**: B-trees (Ordered `BTreeMap`, Rust `BTreeMap`, Abseil `btree_map`, and Klib `kbtree`) pack multiple keys per node. This can reduce pointer chasing compared to node-allocated trees (`std::map`, Java `TreeMap`, and Zig `RedBlackTreeSet`).
2. **Intrusive and dedicated AVL trees**: Klib `kavl` and fastutil `AVLTreeMap` use strict AVL height balancing. Their balance rules differ from red-black trees. Measured latency also depends on node layout, allocation, and input.
3. **Flat arrays**: Boost `flat_map` and `flat_set` store elements in contiguous sorted memory. The layout can benefit reads, but random insertions and removals require shifting elements ($O(N)$ per operation), making large random mutation workloads expensive.
4. **Java boxed collections versus primitive specialization**: Java's standard `TreeMap<Long, Long>` stores boxed object pointers, incurring substantial GC and pointer overhead. The `fastutil` collections operate directly on primitive 64-bit integers (`long`), avoiding boxed key and value storage. Boxed inputs are prepared outside timers, so boxing allocation cost is excluded.
"""


def format_metric(val, best_val, runner_up_vals=None):
    if val is None:
        return "-"
    formatted = f"{val:.2f}"
    if best_val is not None and val == best_val:
        return f"**{formatted}**"
    return formatted


def format_html_metric(val, best_val, runner_up_vals=None):
    if val is None:
        return "-"
    formatted = f"{val:.2f}"
    if best_val is not None and val == best_val:
        return f'<strong class="best">{formatted}</strong>'
    if runner_up_vals is not None and val in runner_up_vals:
        return f'<span class="runner-up">{formatted}</span>'
    return formatted


def render_chart_code(title, x_labels, values, y_label="Time (ns/op)"):
    points = [(label, value) for label, value in zip(x_labels, values) if value is not None]
    if not points:
        return ""
    x_labels, values = zip(*points)
    max_val = max(values)
    upper_bound = math.ceil(max_val * 1.15) if max_val > 0 else 10
    if upper_bound == 0:
        upper_bound = 10

    labels_str = ", ".join(f'"{lbl}"' for lbl in x_labels)
    values_str = ", ".join(f"{v:.2f}" for v in values)

    return f"""%%{{init: {{"xyChart": {{"width": 900, "height": 650, "xAxis": {{"labelRotation": 90, "labelPadding": 16}}}}}}}}%%
xychart-beta
    title "{title}"
    x-axis [{labels_str}]
    y-axis "{y_label}" 0 --> {upper_bound}
    bar [{values_str}]"""


def render_chart(title, x_labels, values, y_label="Time (ns/op)"):
    code = render_chart_code(title, x_labels, values, y_label)
    if not code:
        return ""
    return f"""```mermaid
{code}
```
"""


def render_html_chart(title, x_labels, values, y_label="Time (ns/op)"):
    code = render_chart_code(title, x_labels, values, y_label)
    if not code:
        return ""
    return f"""  <div class="chart-card">
    <pre class="mermaid">
{code}
    </pre>
  </div>"""


def generate_report(records, metadata):
    lines = [
        "# Benchmark Report: Sorted Maps and Sets",
        "",
        "This report provides structured comparison tables and visual charts generated from benchmark results.",
        "",
    ]

    lines.append(render_environment(metadata))
    lines.append(render_interpretation_guide())

    combos = sorted({(r["size"], r["order"], r.get("seed", 42)) for r in records},
                    key=lambda c: (-c[0], c[1], c[2]))

    lines.append("## Benchmark Results by Workload")
    lines.append("")

    for size, order, seed in combos:
        size_label = f"{size:,}"
        order_title = "Ascending Keys" if order == "ascending" else "Shuffled Keys"
        lines.append(f"### Workload: Size = {size_label} Elements ({order_title}, Seed {seed})")
        lines.append("")

        for kind in ("map", "set"):
            kind_title = "Sorted Maps" if kind == "map" else "Sorted Sets"
            lines.append(f"#### {kind_title}")
            lines.append("")

            matching = [
                r
                for r in records
                if r["size"] == size and r["order"] == order and r.get("seed", 42) == seed and r[
                    "kind"] == kind
            ]
            if not matching:
                continue

            by_impl = {}
            for r in matching:
                key = (r["language"], r["implementation"])
                by_impl.setdefault(key, {})[r["phase"]] = r["median_ns_per_op"]

            sorted_impls = sorted(by_impl.keys(), key=lambda k: (k[0], k[1]))

            best_by_phase = {}
            runners_up_by_phase = {}
            for phase in PHASES:
                vals = [
                    phases[phase]
                    for phases in by_impl.values()
                    if phase in phases and phases[phase] >= 0
                ]
                if vals:
                    sorted_vals = sorted(vals)
                    best_by_phase[phase] = sorted_vals[0]
                    remaining = [v for v in sorted_vals if v != sorted_vals[0]]
                    runners_up_by_phase[phase] = set(remaining[:2])

            chart_labels = []

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

                insert_str = format_metric(phases.get("insert"), best_by_phase.get("insert"),
                                           runners_up_by_phase.get("insert"))
                hit_str = format_metric(phases.get("hit"), best_by_phase.get("hit"),
                                        runners_up_by_phase.get("hit"))
                miss_str = format_metric(phases.get("miss"), best_by_phase.get("miss"),
                                         runners_up_by_phase.get("miss"))
                iter_str = format_metric(phases.get("iterate"), best_by_phase.get("iterate"),
                                         runners_up_by_phase.get("iterate"))
                remove_str = format_metric(phases.get("remove"), best_by_phase.get("remove"),
                                           runners_up_by_phase.get("remove"))

                table_rows.append(
                    f"| {format_language(lang)} | {friendly_name} | {structure} | {insert_str} | {hit_str} | {miss_str} | {iter_str} | {remove_str} |"
                )

                chart_labels.append(short_label)

            lines.append("\n".join(table_rows))
            lines.append("")

            for phase in PHASES:
                values = [by_impl[key].get(phase) for key in sorted_impls]
                title = f"{kind_title} {phase.title()} Latency (N = {size_label}, {order_title}, Seed {seed})"
                chart = render_chart(title, chart_labels, values)
                lines.append(chart)

    return "\n".join(lines)


def scaling_charts(records, as_html=False):
    lines = []
    groups = {}
    for row in records:
        key = (row["kind"], row["order"], row.get("seed", 42), row["phase"], row["language"],
               row["implementation"])
        groups.setdefault(key, []).append(row)
    for (kind, order, seed, phase, language, impl), rows in sorted(groups.items()):
        rows.sort(key=lambda r: r["size"])
        if len(rows) < 2:
            continue
        title = f"{format_language(language)} {impl} {phase.title()} Scaling ({order}, Seed {seed})"
        code = render_chart_code(title, [str(r["size"]) for r in rows],
                                 [r["median_ns_per_op"] for r in rows]).replace("    bar [",
                                                                                "    line [")
        if as_html:
            lines.append(
                f'<div data-kind="{kind}" data-order="{order}" data-phase="{phase}"><h3>{html.escape(title)}</h3><pre class="mermaid">{html.escape(code)}</pre></div>')
        else:
            lines.append(f"### {title}\n\n```mermaid\n{code}\n```\n")
    return "\n".join(lines)


def render_html_environment(meta):
    cpu = meta.get("cpu", "Unknown")
    platform_info = meta.get("platform", "Unknown")
    governor = meta.get("governor", "Unknown")
    started = meta.get("started_utc", "Unknown")
    allocator = meta.get("native_allocator", "system malloc")
    c_flags = meta.get("native_flags", "Release mode")
    java_heap = meta.get("java_heap", "-Xms1g -Xmx1g")
    revision = meta.get("revision", "Unknown")

    rows = [
        ("CPU", f"<code>{html.escape(str(cpu))}</code>"),
        ("Operating System", f"<code>{html.escape(str(platform_info))}</code>"),
        ("CPU Frequency Governor", f"<code>{html.escape(str(governor))}</code>"),
        ("Native Allocator", f"<code>{html.escape(str(allocator))}</code>"),
        ("Compiler Optimization Flags", f"<code>{html.escape(str(c_flags))}</code>"),
        ("Java Heap Settings", f"<code>{html.escape(str(java_heap))}</code>"),
        ("Git Revision", f"<code>{html.escape(str(revision))}</code>"),
        ("Timestamp (UTC)", f"<code>{html.escape(str(started))}</code>"),
    ]

    rows.extend((label, html.escape(str(value))) for label, value in provenance_rows(meta))

    versions = meta.get("versions", {})
    if versions:
        version_summary = ", ".join(
            f"{format_language(lang)}: {ver.splitlines()[0]}" for lang, ver in versions.items()
        )
        rows.append(("Toolchain Versions", html.escape(version_summary)))

    lines = [
        '  <section class="card" id="system-environment">',
        '    <h2>System Environment and Metadata</h2>',
        '    <div class="table-container">',
        '      <table>',
        '        <thead>',
        '          <tr><th>Attribute</th><th>Value</th></tr>',
        '        </thead>',
        '        <tbody>',
    ]
    for attr, val in rows:
        lines.append(f"          <tr><td>{attr}</td><td>{val}</td></tr>")
    lines.extend([
        '        </tbody>',
        '      </table>',
        '    </div>',
        '  </section>',
    ])
    return "\n".join(lines)


def render_html_interpretation_guide():
    return """  <section class="card" id="interpretation-guide">
    <h2>Performance Interpretation Guide</h2>
    <p>Ascending and shuffled describe insertion order only. Lookup and removal use independent shuffled permutations. Containers are populated and validated before read and removal phases, so these measure recently accessed data. CI timings are exploratory; publish comparisons from a dedicated idle machine with recorded CPU affinity. This benchmark isolates five phases of sorted container operations:</p>
    <ul>
      <li><strong>Insert</strong>: Time to insert <em>N</em> keys into an initially empty container. Container construction and node allocation are included in new runs. Legacy Java runs excluded empty container construction. For ascending input, sequential B-tree optimizations are highlighted; for shuffled input, balancing overhead is tested.</li>
      <li><strong>Lookup hit</strong>: Time to query <em>N</em> keys that exist in the container. Measures pointer indirection, cache locality, and branching.</li>
      <li><strong>Lookup miss</strong>: Time to query <em>N</em> absent keys interleaved between existing keys. Tests traversal depth and early exit efficiency.</li>
      <li><strong>Iterate</strong>: Time to perform an in-order scan across all elements. Highlights cache line density and memory locality (for example, flat arrays and B-tree leaf nodes versus pointer-chasing binary trees).</li>
      <li><strong>Remove</strong>: Time to remove all <em>N</em> keys until the container is empty. Native runners include node deallocation time. Java removal unlinks entries and does not force garbage collection.</li>
    </ul>
    <p><strong class="best">Bold green</strong> values mark the lowest measured median, and <strong class="runner-up">light orange</strong> values mark the next two lowest medians, not proven winners.</p>
    <h3>Key Architectural Comparisons</h3>
    <ol>
      <li><strong>B-trees versus binary trees</strong>: B-trees (Ordered <code>BTreeMap</code>, Rust <code>BTreeMap</code>, Abseil <code>btree_map</code>, and Klib <code>kbtree</code>) pack multiple keys per node. This can reduce pointer chasing compared to node-allocated trees (<code>std::map</code>, Java <code>TreeMap</code>, and Zig <code>RedBlackTreeSet</code>).</li>
      <li><strong>Intrusive and dedicated AVL trees</strong>: Klib <code>kavl</code> and fastutil <code>AVLTreeMap</code> use strict AVL height balancing. Their balance rules differ from red-black trees. Measured latency also depends on node layout, allocation, and input.</li>
      <li><strong>Flat arrays</strong>: Boost <code>flat_map</code> and <code>flat_set</code> store elements in contiguous sorted memory. The layout can benefit reads, but random insertions and removals require shifting elements (<em>O(N)</em> per operation), making large random mutation workloads expensive.</li>
      <li><strong>Java boxed collections versus primitive specialization</strong>: Java's standard <code>TreeMap&lt;Long, Long&gt;</code> stores boxed object pointers, incurring substantial GC and pointer overhead. The <code>fastutil</code> collections operate directly on primitive 64-bit integers (<code>long</code>), avoiding boxed key and value storage. Boxed inputs are prepared outside timers, so boxing allocation cost is excluded.</li>
    </ol>
  </section>"""


def generate_html_report(records, metadata, downloads=()):
    combos = sorted({(r["size"], r["order"], r.get("seed", 42)) for r in records},
                    key=lambda c: (-c[0], c[1], c[2]))

    nav_links = [
        '        <a class="btn" href="#system-environment">System Environment</a>',
        '        <a class="btn" href="#interpretation-guide">Interpretation Guide</a>',
    ]
    for size, order, seed in combos:
        size_label = f"{size:,}"
        order_title = "Ascending" if order == "ascending" else "Shuffled"
        anchor = f"workload-{size}-{order}-{seed}"
        nav_links.append(
            f'        <a class="btn" href="#{anchor}">Size {size_label} ({order_title}, Seed {seed})</a>')

    lines = [
        "<!DOCTYPE html>",
        '<html lang="en">',
        "<head>",
        '  <meta charset="UTF-8">',
        '  <meta name="viewport" content="width=device-width, initial-scale=1.0">',
        "  <title>Benchmark Report: Sorted Maps and Sets</title>",
        "  <style>",
        "    :root {",
        "      --bg: #ffffff;",
        "      --card-bg: #f8fafc;",
        "      --text: #0f172a;",
        "      --text-muted: #64748b;",
        "      --border: #e2e8f0;",
        "      --table-header: #f1f5f9;",
        "      --table-stripe: #f8fafc;",
        "      --best-bg: #dcfce7;",
        "      --best-color: #166534;",
        "      --runner-up-bg: #ffedd5;",
        "      --runner-up-color: #9a3412;",
        "      --accent: #2563eb;",
        "      --font-mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;",
        "    }",
        "    @media (prefers-color-scheme: dark) {",
        "      :root {",
        "        --bg: #0d1117;",
        "        --card-bg: #161b22;",
        "        --text: #f0f6fc;",
        "        --text-muted: #8b949e;",
        "        --border: #30363d;",
        "        --table-header: #21262d;",
        "        --table-stripe: #161b22;",
        "        --best-bg: #0f3d24;",
        "        --best-color: #7ee787;",
        "        --runner-up-bg: #431407;",
        "        --runner-up-color: #fdba74;",
        "        --accent: #58a6ff;",
        "      }",
        "    }",
        "    * { box-sizing: border-box; margin: 0; padding: 0; }",
        "    body {",
        '      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;',
        "      line-height: 1.6;",
        "      color: var(--text);",
        "      background-color: var(--bg);",
        "      padding: 2rem 1rem;",
        "    }",
        "    .container { max-width: 1200px; margin: 0 auto; }",
        "    header { margin-bottom: 2rem; border-bottom: 1px solid var(--border); padding-bottom: 1.5rem; }",
        "    h1 { font-size: 2rem; margin-bottom: 0.5rem; }",
        "    h2 { font-size: 1.5rem; margin: 2rem 0 1rem; border-bottom: 1px solid var(--border); padding-bottom: 0.5rem; }",
        "    h3 { font-size: 1.25rem; margin: 1.5rem 0 0.75rem; }",
        "    h4 { font-size: 1.1rem; margin: 1rem 0 0.5rem; color: var(--text-muted); }",
        "    p { margin-bottom: 1rem; }",
        "    ul, ol { margin: 0 0 1rem 1.5rem; }",
        "    li { margin-bottom: 0.25rem; }",
        "    .btn-group { display: flex; flex-wrap: wrap; gap: 0.5rem; margin: 1rem 0; }",
        "    .btn {",
        "      display: inline-block;",
        "      padding: 0.4rem 0.8rem;",
        "      font-size: 0.875rem;",
        "      font-weight: 500;",
        "      text-decoration: none;",
        "      border-radius: 6px;",
        "      border: 1px solid var(--border);",
        "      background: var(--card-bg);",
        "      color: var(--accent);",
        "      transition: background 0.15s, border-color 0.15s, color 0.15s;",
        "    }",
        "    .btn:hover { background: var(--accent); border-color: var(--accent); color: #ffffff; }",
        "    .card {",
        "      background: var(--card-bg);",
        "      border: 1px solid var(--border);",
        "      border-radius: 8px;",
        "      padding: 1.25rem;",
        "      margin-bottom: 1.5rem;",
        "    }",
        "    .table-container {",
        "      overflow-x: auto;",
        "      margin: 1rem 0 1.5rem;",
        "      border: 1px solid var(--border);",
        "      border-radius: 8px;",
        "    }",
        "    table { width: 100%; border-collapse: collapse; font-size: 0.9rem; }",
        "    th, td {",
        "      padding: 0.65rem 0.85rem;",
        "      text-align: left;",
        "      border-bottom: 1px solid var(--border);",
        "    }",
        "    th { background: var(--table-header); font-weight: 600; }",
        "    tr:nth-child(even) td { background: var(--table-stripe); }",
        "    tr:last-child td { border-bottom: none; }",
        "    [hidden] { display: none !important; }",
        "    td.num, th.num {",
        "      text-align: right;",
        "      font-variant-numeric: tabular-nums;",
        "      font-family: var(--font-mono);",
        "    }",
        "    table.sortable th {",
        "      padding: 0;",
        "    }",
        "    table.sortable th button {",
        "      display: block;",
        "      width: 100%;",
        "      border: 0;",
        "      background: transparent;",
        "      color: inherit;",
        "      font: inherit;",
        "      text-align: inherit;",
        "      padding: 0.75rem 1.5rem 0.75rem 1rem;",
        "      cursor: pointer;",
        "      user-select: none;",
        "      position: relative;",
        "    }",
        "    table.sortable th:hover {",
        "      background: var(--border);",
        "    }",
        "    table.sortable th button:focus-visible {",
        "      outline: 2px solid var(--accent);",
        "      outline-offset: -2px;",
        "    }",
        "    table.sortable th span::after {",
        '      content: "↕";',
        "      position: absolute;",
        "      right: 0.5rem;",
        "      opacity: 0.4;",
        "      font-size: 0.75rem;",
        "    }",
        '    table.sortable th[aria-sort="ascending"] span::after {',
        '      content: "▲";',
        "      opacity: 1;",
        "      color: var(--accent);",
        "    }",
        '    table.sortable th[aria-sort="descending"] span::after {',
        '      content: "▼";',
        "      opacity: 1;",
        "      color: var(--accent);",
        "    }",
        "    .best {",
        "      font-weight: 700;",
        "      color: var(--best-color);",
        "      background: var(--best-bg);",
        "      padding: 0.15rem 0.35rem;",
        "      border-radius: 4px;",
        "    }",
        "    .runner-up {",
        "      font-weight: 600;",
        "      color: var(--runner-up-color);",
        "      background: var(--runner-up-bg);",
        "      padding: 0.15rem 0.35rem;",
        "      border-radius: 4px;",
        "    }",
        "    strong.runner-up {",
        "      font-weight: 700;",
        "    }",
        "    .chart-card {",
        "      background: var(--card-bg);",
        "      border: 1px solid var(--border);",
        "      border-radius: 8px;",
        "      padding: 1rem;",
        "      margin: 1rem 0 1.5rem;",
        "      overflow-x: auto;",
        "    }",
        # Flex layout collapses Mermaid's temporary SVG text measurements.
        "    .mermaid { display: block; text-align: center; }",
        "    code {",
        "      font-family: var(--font-mono);",
        "      font-size: 0.85em;",
        "      background: var(--border);",
        "      padding: 0.15em 0.35em;",
        "      border-radius: 4px;",
        "    }",
        "    footer {",
        "      margin-top: 3rem;",
        "      padding-top: 1.5rem;",
        "      border-top: 1px solid var(--border);",
        "      font-size: 0.875rem;",
        "      color: var(--text-muted);",
        "      text-align: center;",
        "    }",
        "  </style>",
        "</head>",
        "<body>",
        '  <div class="container">',
        "    <header>",
        "      <h1>Benchmark Report: Sorted Maps and Sets</h1>",
        "      <p>This report provides structured comparison tables and visual charts generated from benchmark results.</p>",
        '      <div class="btn-group">',
        '        <a class="btn" href="REPORT.md" download>Download REPORT.md</a>',
        *(f'        <a class="btn" href="{filename}" download>Download {filename}</a>'
          for filename in DOWNLOADS if filename in downloads),
        "      </div>",
        '      <div class="btn-group">',
        *nav_links,
        "      </div>",
        "    </header>",
        render_html_environment(metadata),
        render_html_interpretation_guide(),
        '<div class="card" id="filters">',
        '<label>Operation <select id="phase-filter"><option value="">All</option>' + ''.join(
            f'<option value="{phase}">{phase.title()}</option>' for phase in
            PHASES) + '</select></label>',
        '<label> Container <select id="kind-filter"><option value="">All</option><option value="map">Map</option><option value="set">Set</option></select></label>',
        '<label> Insertion order <select id="order-filter"><option value="">All</option><option value="ascending">Ascending</option><option value="shuffled">Shuffled</option></select></label>',
        '</div>',
        '    <section id="results-by-workload">',
        "      <h2>Benchmark Results by Workload</h2>",
    ]

    for size, order, seed in combos:
        size_label = f"{size:,}"
        order_title = "Ascending Keys" if order == "ascending" else "Shuffled Keys"
        anchor = f"workload-{size}-{order}-{seed}"
        lines.append(f'      <section id="{anchor}" class="workload-section" data-order="{order}">')
        lines.append(
            f"        <h3>Workload: Size = {size_label} Elements ({order_title}, Seed {seed})</h3>")

        for kind in ("map", "set"):
            kind_title = "Sorted Maps" if kind == "map" else "Sorted Sets"
            lines.append(f'<div data-kind="{kind}" data-order="{order}">')
            lines.append(f"        <h4>{kind_title}</h4>")

            matching = [
                r
                for r in records
                if r["size"] == size and r["order"] == order and r.get("seed", 42) == seed and r[
                    "kind"] == kind
            ]
            if not matching:
                lines.append("</div>")
                continue

            by_impl = {}
            for r in matching:
                key = (r["language"], r["implementation"])
                by_impl.setdefault(key, {})[r["phase"]] = r["median_ns_per_op"]

            sorted_impls = sorted(by_impl.keys(), key=lambda k: (k[0], k[1]))

            best_by_phase = {}
            runners_up_by_phase = {}
            for phase in PHASES:
                vals = [
                    phases[phase]
                    for phases in by_impl.values()
                    if phase in phases and phases[phase] >= 0
                ]
                if vals:
                    sorted_vals = sorted(vals)
                    best_by_phase[phase] = sorted_vals[0]
                    remaining = [v for v in sorted_vals if v != sorted_vals[0]]
                    runners_up_by_phase[phase] = set(remaining[:2])

            chart_labels = []

            table_rows = [
                '        <div class="table-container">',
                '          <table class="sortable">',
                "            <thead>",
                "              <tr>",
                '                <th><button type="button">Language<span aria-hidden="true"></span></button></th>',
                '                <th><button type="button">Implementation<span aria-hidden="true"></span></button></th>',
                '                <th><button type="button">Data Structure<span aria-hidden="true"></span></button></th>',
                '                <th class="num"><button type="button">Insert (ns/op)<span aria-hidden="true"></span></button></th>',
                '                <th class="num"><button type="button">Lookup Hit (ns/op)<span aria-hidden="true"></span></button></th>',
                '                <th class="num"><button type="button">Lookup Miss (ns/op)<span aria-hidden="true"></span></button></th>',
                '                <th class="num"><button type="button">Iterate (ns/op)<span aria-hidden="true"></span></button></th>',
                '                <th class="num"><button type="button">Remove (ns/op)<span aria-hidden="true"></span></button></th>',
                "              </tr>",
                "            </thead>",
                "            <tbody>",
            ]

            for lang, impl in sorted_impls:
                phases = by_impl[(lang, impl)]
                mapping = STRUCTURE_MAP.get(
                    (lang, impl), (impl, "Unknown", impl)
                )
                friendly_name = mapping[0]
                structure = mapping[1]
                short_label = mapping[2] if len(mapping) > 2 else friendly_name

                insert_str = format_html_metric(phases.get("insert"), best_by_phase.get("insert"), runners_up_by_phase.get("insert"))
                hit_str = format_html_metric(phases.get("hit"), best_by_phase.get("hit"), runners_up_by_phase.get("hit"))
                miss_str = format_html_metric(phases.get("miss"), best_by_phase.get("miss"), runners_up_by_phase.get("miss"))
                iter_str = format_html_metric(phases.get("iterate"), best_by_phase.get("iterate"), runners_up_by_phase.get("iterate"))
                remove_str = format_html_metric(phases.get("remove"), best_by_phase.get("remove"), runners_up_by_phase.get("remove"))

                table_rows.append(
                    f"              <tr>"
                    f"<td>{html.escape(format_language(lang))}</td>"
                    f"<td>{html.escape(friendly_name)}</td>"
                    f"<td>{html.escape(structure)}</td>"
                    f'<td class="num">{insert_str}</td>'
                    f'<td class="num">{hit_str}</td>'
                    f'<td class="num">{miss_str}</td>'
                    f'<td class="num">{iter_str}</td>'
                    f'<td class="num">{remove_str}</td>'
                    f"</tr>"
                )

                chart_labels.append(short_label)

            table_rows.extend([
                "            </tbody>",
                "          </table>",
                "        </div>",
            ])
            lines.extend(table_rows)

            for phase in PHASES:
                values = [by_impl[key].get(phase) for key in sorted_impls]
                title = f"{kind_title} {phase.title()} Latency (N = {size_label}, {order_title}, Seed {seed})"
                chart = render_html_chart(title, chart_labels, values)
                lines.append(f'<div data-phase="{phase}">{chart}</div>')
            lines.append("</div>")

        lines.append("      </section>")

    lines.extend([
        "    </section>",
        "    <footer>",
        "      <p>Ordered Benchmarks Suite</p>",
        "    </footer>",
        "  </div>",
        "  <script>",
        "    const phases = ['insert', 'hit', 'miss', 'iterate', 'remove'];",
        "    function filterResults() {",
        "      const phase = document.getElementById('phase-filter').value;",
        "      const kind = document.getElementById('kind-filter').value;",
        "      const order = document.getElementById('order-filter').value;",
        "      document.querySelectorAll('[data-kind], [data-phase], .workload-section').forEach(el => {",
        "        el.hidden = Boolean((el.dataset.kind && kind && el.dataset.kind !== kind) || (el.dataset.order && order && el.dataset.order !== order) || (el.dataset.phase && phase && el.dataset.phase !== phase));",
        "      });",
        "      document.querySelectorAll('table.sortable tr').forEach(row => {",
        "        Array.from(row.cells).forEach((cell, index) => { cell.hidden = index >= 3 && Boolean(phase && phases[index - 3] !== phase); });",
        "      });",
        "    }",
        "    document.querySelectorAll('#filters select').forEach(el => el.addEventListener('change', filterResults));",
        "    document.querySelectorAll('table.sortable').forEach((table) => {",
        "      const headers = table.querySelectorAll('thead th');",
        "      const tbody = table.querySelector('tbody');",
        "      if (!tbody) return;",
        "      headers.forEach((th, colIndex) => {",
        "        const sortColumn = () => {",
        "          const currentSort = th.getAttribute('aria-sort');",
        "          const nextSort = currentSort === 'ascending' ? 'descending' : 'ascending';",
        "          headers.forEach((h) => h.removeAttribute('aria-sort'));",
        "          th.setAttribute('aria-sort', nextSort);",
        "          const isNum = th.classList.contains('num');",
        "          const rows = Array.from(tbody.querySelectorAll('tr'));",
        "          rows.sort((rowA, rowB) => {",
        "            const cellA = rowA.cells[colIndex]?.textContent.trim() ?? '';",
        "            const cellB = rowB.cells[colIndex]?.textContent.trim() ?? '';",
        "            if (isNum) {",
        "              const numA = cellA === '-' || cellA === '' ? Infinity : parseFloat(cellA.replace(/,/g, ''));",
        "              const numB = cellB === '-' || cellB === '' ? Infinity : parseFloat(cellB.replace(/,/g, ''));",
        "              const diff = (isNaN(numA) ? Infinity : numA) - (isNaN(numB) ? Infinity : numB);",
        "              return nextSort === 'ascending' ? diff : -diff;",
        "            }",
        "            const comp = cellA.localeCompare(cellB, undefined, { numeric: true, sensitivity: 'base' });",
        "            return nextSort === 'ascending' ? comp : -comp;",
        "          });",
        "          rows.forEach((row) => tbody.appendChild(row));",
        "        };",
        "        th.querySelector('button').addEventListener('click', sortColumn);",
        "      });",
        "    });",
        "  </script>",
        '  <script type="module">',
        "    import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs';",
        "    const isDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;",
        "    mermaid.initialize({",
        "      startOnLoad: true,",
        "      theme: isDark ? 'dark' : 'neutral',",
        "      xyChart: {",
        "        width: 900,",
        "        height: 650,",
        "        xAxis: {",
        "          labelRotation: 90,",
        "          labelPadding: 16",
        "        }",
        "      }",
        "    });",
        "  </script>",
        "</body>",
        "</html>",
    ])
    return "\n".join(lines)


def build_site(results_dir, site_dir):
    site_dir = Path(site_dir)
    site_dir.mkdir(parents=True, exist_ok=True)

    records = load_records(results_dir)
    metadata = load_metadata(results_dir)

    report_md = generate_report(records, metadata)
    report_html = generate_html_report(records, metadata, [name for name in DOWNLOADS if
                                                           (results_dir / name).is_file()])

    (site_dir / "index.html").write_text(report_html, encoding="utf-8")
    (site_dir / "REPORT.md").write_text(report_md, encoding="utf-8")
    (site_dir / ".nojekyll").write_text("", encoding="utf-8")

    for filename in DOWNLOADS:
        src = results_dir / filename
        if src.is_file():
            shutil.copyfile(src, site_dir / filename)
        else:
            (site_dir / filename).unlink(missing_ok=True)


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
    parser.add_argument(
        "--html",
        type=Path,
        help="Destination path for generated HTML report (optional)",
    )
    parser.add_argument(
        "--site-dir",
        type=Path,
        help="Destination directory to prepare for GitHub Pages deployment (optional)",
    )
    args = parser.parse_args()

    results_dir = args.results or find_latest_results()
    print(f"Reading benchmark results from: {results_dir}")

    records = load_records(results_dir)
    metadata = load_metadata(results_dir)
    report_md = generate_report(records, metadata)

    args.output.write_text(report_md, encoding="utf-8")
    print(f"Report written to: {args.output}")

    in_dir_report = results_dir / "REPORT.md"
    in_dir_report.write_text(report_md, encoding="utf-8")
    print(f"Copy written to: {in_dir_report}")

    report_html = generate_html_report(records, metadata, [name for name in DOWNLOADS if
                                                           (results_dir / name).is_file()])
    in_dir_html = results_dir / "index.html"
    in_dir_html.write_text(report_html, encoding="utf-8")
    print(f"Copy written to: {in_dir_html}")

    if args.html:
        args.html.write_text(report_html, encoding="utf-8")
        print(f"HTML report written to: {args.html}")

    if args.site_dir:
        build_site(results_dir, args.site_dir)
        print(f"GitHub Pages site prepared at: {args.site_dir}")


if __name__ == "__main__":
    main()
