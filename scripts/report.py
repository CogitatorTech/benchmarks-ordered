"""Generate readable Markdown and HTML reports with tables and charts from benchmark data."""

import argparse
import csv
import html
import json
import math
from pathlib import Path
import shutil
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


def format_html_metric(val, best_val):
    if val is None:
        return "-"
    formatted = f"{val:.2f}"
    if best_val is not None and formatted == f"{best_val:.2f}":
        return f'<strong class="best">{formatted}</strong>'
    return formatted


def render_chart_code(title, x_labels, values, y_label="Time (ns/op)"):
    if not x_labels or not values:
        return ""
    max_val = max(values)
    upper_bound = math.ceil(max_val * 1.15) if max_val > 0 else 10
    if upper_bound == 0:
        upper_bound = 10

    labels_str = ", ".join(f'"{lbl}"' for lbl in x_labels)
    values_str = ", ".join(f"{v:.2f}" for v in values)

    return f"""xychart-beta
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

    versions = meta.get("versions", {})
    if versions:
        version_summary = ", ".join(
            f"{lang}: {ver.splitlines()[0]}" for lang, ver in versions.items()
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
    <p>This benchmark isolates five fundamental phases of sorted container operations:</p>
    <ul>
      <li><strong>Insert:</strong> Time to insert <em>N</em> keys into an initially empty container. For native implementations, this includes memory allocation. For ascending input, sequential B-tree optimizations are highlighted; for shuffled input, balancing overhead is tested.</li>
      <li><strong>Lookup Hit:</strong> Time to query <em>N</em> keys that exist in the container. Measures pointer indirection, cache locality, and branching.</li>
      <li><strong>Lookup Miss:</strong> Time to query <em>N</em> absent keys interleaved between existing keys. Tests traversal depth and early exit efficiency.</li>
      <li><strong>Iterate:</strong> Time to perform an in-order scan across all elements. Highlights cache line density and memory locality (e.g. flat arrays and B-tree leaf nodes versus pointer-chasing binary trees).</li>
      <li><strong>Remove:</strong> Time to remove all <em>N</em> keys until the container is empty. Native runners include node deallocation time.</li>
    </ul>
    <p>The lowest latency value for each operation column in the tables below is displayed in <strong>bold with a green highlight</strong>.</p>
    <h3>Key Architectural Comparisons</h3>
    <ol>
      <li><strong>B-Trees versus Binary Trees:</strong> B-trees (Ordered <code>BTreeMap</code>, Rust <code>BTreeMap</code>, Abseil <code>btree_map</code>, and Klib <code>kbtree</code>) pack multiple keys per node. This lowers pointer chasing and improves cache locality compared to node-allocated trees (<code>std::map</code>, Java <code>TreeMap</code>, and Zig <code>RedBlackTreeSet</code>).</li>
      <li><strong>Intrusive and Dedicated AVL Trees:</strong> Klib <code>kavl</code> and fastutil <code>AVLTreeMap</code> use strict AVL height balancing. This leads to shorter branch heights than red-black trees, trading slightly slower insertions for faster lookups.</li>
      <li><strong>Flat Arrays:</strong> Boost <code>flat_map</code> and <code>flat_set</code> store elements in contiguous sorted memory. Sorted iteration and lookups are fast, but random insertions and removals require shifting elements (<em>O(N)</em> per operation), making large random mutation workloads expensive.</li>
      <li><strong>Java Boxed Collections versus Primitive Specialization:</strong> Java's standard <code>TreeMap&lt;Long, Long&gt;</code> stores boxed object pointers, incurring substantial GC and pointer overhead. The <code>fastutil</code> collections operate directly on primitive 64-bit integers (<code>long</code>), demonstrating the true algorithmic capacity of the JVM without object wrappers.</li>
    </ol>
  </section>"""


def generate_html_report(records, metadata):
    combos = sorted({(r["size"], r["order"]) for r in records})

    nav_links = [
        '        <a class="btn" href="#system-environment">System Environment</a>',
        '        <a class="btn" href="#interpretation-guide">Interpretation Guide</a>',
    ]
    for size, order in combos:
        size_label = f"{size:,}"
        order_title = "Ascending" if order == "ascending" else "Shuffled"
        anchor = f"workload-{size}-{order}"
        nav_links.append(f'        <a class="btn" href="#{anchor}">Size {size_label} ({order_title})</a>')

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
        "    td.num, th.num {",
        "      text-align: right;",
        "      font-variant-numeric: tabular-nums;",
        "      font-family: var(--font-mono);",
        "    }",
        "    .best {",
        "      font-weight: 700;",
        "      color: var(--best-color);",
        "      background: var(--best-bg);",
        "      padding: 0.15rem 0.35rem;",
        "      border-radius: 4px;",
        "    }",
        "    .chart-card {",
        "      background: var(--card-bg);",
        "      border: 1px solid var(--border);",
        "      border-radius: 8px;",
        "      padding: 1rem;",
        "      margin: 1rem 0 1.5rem;",
        "      overflow-x: auto;",
        "    }",
        "    .mermaid { display: flex; justify-content: center; }",
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
        '        <a class="btn" href="summary.csv" download>Download summary.csv</a>',
        '        <a class="btn" href="samples.csv" download>Download samples.csv</a>',
        '        <a class="btn" href="metadata.json" download>Download metadata.json</a>',
        "      </div>",
        '      <div class="btn-group">',
        *nav_links,
        "      </div>",
        "    </header>",
        render_html_environment(metadata),
        render_html_interpretation_guide(),
        '    <section id="results-by-workload">',
        "      <h2>Benchmark Results by Workload</h2>",
    ]

    for size, order in combos:
        size_label = f"{size:,}"
        order_title = "Ascending Keys" if order == "ascending" else "Shuffled Keys"
        anchor = f"workload-{size}-{order}"
        lines.append(f'      <section id="{anchor}" class="workload-section">')
        lines.append(f"        <h3>Workload: Size = {size_label} Elements ({order_title})</h3>")

        for kind in ("map", "set"):
            kind_title = "Sorted Maps" if kind == "map" else "Sorted Sets"
            lines.append(f"        <h4>{kind_title}</h4>")

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
                '        <div class="table-container">',
                "          <table>",
                "            <thead>",
                "              <tr>",
                "                <th>Language</th>",
                "                <th>Implementation</th>",
                "                <th>Data Structure</th>",
                '                <th class="num">Insert (ns/op)</th>',
                '                <th class="num">Lookup Hit (ns/op)</th>',
                '                <th class="num">Lookup Miss (ns/op)</th>',
                '                <th class="num">Iterate (ns/op)</th>',
                '                <th class="num">Remove (ns/op)</th>',
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

                insert_str = format_html_metric(phases.get("insert"), best_by_phase.get("insert"))
                hit_str = format_html_metric(phases.get("hit"), best_by_phase.get("hit"))
                miss_str = format_html_metric(phases.get("miss"), best_by_phase.get("miss"))
                iter_str = format_html_metric(phases.get("iterate"), best_by_phase.get("iterate"))
                remove_str = format_html_metric(phases.get("remove"), best_by_phase.get("remove"))

                table_rows.append(
                    f"              <tr>"
                    f"<td>{html.escape(lang)}</td>"
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
                chart_hit_values.append(phases.get("hit", 0.0))
                chart_iter_values.append(phases.get("iterate", 0.0))

            table_rows.extend([
                "            </tbody>",
                "          </table>",
                "        </div>",
            ])
            lines.extend(table_rows)

            chart_title_hit = f"{kind_title}: Lookup Hit Latency (N = {size_label}, {order_title})"
            lines.append(render_html_chart(chart_title_hit, chart_labels, chart_hit_values))

            chart_title_iter = f"{kind_title}: Sorted Iteration Latency (N = {size_label}, {order_title})"
            lines.append(render_html_chart(chart_title_iter, chart_labels, chart_iter_values))

        lines.append("      </section>")

    lines.extend([
        "    </section>",
        "    <footer>",
        "      <p>Ordered Benchmarks Suite</p>",
        "    </footer>",
        "  </div>",
        '  <script type="module">',
        "    import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs';",
        "    const isDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;",
        "    mermaid.initialize({",
        "      startOnLoad: true,",
        "      theme: isDark ? 'dark' : 'neutral'",
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
    report_html = generate_html_report(records, metadata)

    (site_dir / "index.html").write_text(report_html, encoding="utf-8")
    (site_dir / "REPORT.md").write_text(report_md, encoding="utf-8")
    (site_dir / ".nojekyll").write_text("", encoding="utf-8")

    for filename in ("summary.csv", "samples.csv", "metadata.json", "flake.lock"):
        src = results_dir / filename
        if src.exists():
            shutil.copyfile(src, site_dir / filename)


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

    report_html = generate_html_report(records, metadata)
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
