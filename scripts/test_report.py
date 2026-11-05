import copy
import csv
import json
import tempfile
import unittest
from pathlib import Path

import report


class ReportTests(unittest.TestCase):
    def test_find_latest_results(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            d1 = base / "20261001-100000"
            d2 = base / "20261002-120000"
            d1.mkdir()
            d2.mkdir()
            (d1 / "summary.csv").write_text("dummy")
            (d2 / "summary.csv").write_text("dummy")
            partial = base / "20261003-120000"
            partial.mkdir()
            (partial / "samples.csv").write_text("dummy")
            (partial / "summary.csv.tmp").write_text("dummy")
            latest = report.find_latest_results(base)
            self.assertEqual(latest, d2)
            (d1 / "summary.csv").unlink()
            (d2 / "summary.csv").unlink()
            with self.assertRaisesRegex(FileNotFoundError, "No completed"):
                report.find_latest_results(base)

    def test_load_records_from_summary(self):
        with tempfile.TemporaryDirectory() as temp:
            d = Path(temp)
            summary = d / "summary.csv"
            with summary.open("w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "language",
                    "implementation",
                    "kind",
                    "size",
                    "order",
                    "phase",
                    "median_ns_per_op",
                    "min_ns_per_op",
                    "max_ns_per_op",
                    "samples",
                ])
                for phase in report.PHASES:
                    writer.writerow(
                        ["zig", "btree_map", "map", 1000, "ascending", phase, 20.5, 19, 22, 3])
            records = report.load_records(d)
            self.assertEqual(len(records), 5)
            self.assertEqual(records[0]["language"], "zig")
            self.assertEqual(records[0]["median_ns_per_op"], 20.5)
            summary.write_text("\n".join(summary.read_text().splitlines()[:-1]) + "\n")
            with self.assertRaisesRegex(ValueError, "Incomplete"):
                report.load_records(d)

    def test_load_records_from_samples_fallback(self):
        with tempfile.TemporaryDirectory() as temp:
            d = Path(temp)
            samples = d / "samples.csv"
            with samples.open("w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "language",
                    "implementation",
                    "kind",
                    "size",
                    "order",
                    "phase",
                    "fork",
                    "sample",
                    "ns_per_op",
                ])
                for phase in report.PHASES:
                    for sample, ns in enumerate((25, 35)):
                        writer.writerow(
                            ["rust", "btree_map", "map", 1000, "ascending", phase, 0, sample, ns])
            records = report.load_records(d)
            self.assertEqual(len(records), 5)
            self.assertEqual(records[0]["median_ns_per_op"], 30.0)
            self.assertEqual(records[0]["min_ns_per_op"], 25.0)
            self.assertEqual(records[0]["max_ns_per_op"], 35.0)
            samples.write_text("\n".join(samples.read_text().splitlines()[:-1]) + "\n")
            with self.assertRaisesRegex(ValueError, "unequal sample counts"):
                report.load_records(d)

    def test_validate_records(self):
        records = [dict(language="zig", implementation="btree_map", kind="map", size=1000,
                        order="ascending", phase=phase, samples=2, min_ns_per_op=1,
                        median_ns_per_op=2, max_ns_per_op=3) for phase in report.PHASES]
        report.validate_records(records)
        bad_cases = [[], records[:-1], records + records[:1]]
        for field, value in (("phase", "unknown"), ("samples", 0), ("samples", 1),
                             ("median_ns_per_op", float("nan")), ("min_ns_per_op", -1),
                             ("max_ns_per_op", 1), ("size", 0), ("kind", "invalid")):
            bad = copy.deepcopy(records)
            bad[0][field] = value
            bad_cases.append(bad)
        for bad in bad_cases:
            with self.subTest(records=bad), self.assertRaises(ValueError):
                report.validate_records(bad)

    def test_manifest_detects_missing_implementation_and_sample_identity(self):
        records = [dict(language="rust", implementation="btree_map", kind="map", size=10,
                        order="ascending", seed=123, phase=phase, samples=2,
                        min_ns_per_op=1, median_ns_per_op=2, max_ns_per_op=3,
                        sample_ids={(0, 0), (1, 0)}) for phase in report.PHASES]
        meta = dict(implementations={"rust": ["btree_map"]}, sizes=[10], orders=["ascending"],
                    seeds=[123], forks=2, samples_per_fork=1)
        report.validate_records(records, meta)
        meta["implementations"]["rust"].append("btree_set")
        with self.assertRaisesRegex(ValueError, "coverage"):
            report.validate_records(records, meta)
        meta["implementations"]["rust"].pop()
        for row in records:
            row["sample_ids"] = {(0, 0), (0, 1)}
        with self.assertRaisesRegex(ValueError, "configuration"):
            report.validate_records(records, meta)

    def test_legacy_toolchains_do_not_require_new_implementations(self):
        records = [dict(language="rust", implementation="btree_map", kind="map", size=10,
                        order="ascending", phase=phase, samples=1, min_ns_per_op=2,
                        median_ns_per_op=2, max_ns_per_op=2) for phase in report.PHASES]
        report.validate_records(records, {"versions": {"rust": "historical rustc"}})
        with self.assertRaisesRegex(ValueError, "coverage"):
            report.validate_records(records, {"implementations": {
                "rust": ["btree_map", "btree_set"]}})

    def test_report_spread_filters_scaling_and_provenance(self):
        records = [dict(language="rust", implementation="btree_map", kind="map", size=size,
                        order="ascending", seed=seed, phase=phase, samples=4,
                        min_ns_per_op=1, median_ns_per_op=2, max_ns_per_op=3,
                        q1=1.5, q3=2.5, forks=2, fork_medians=[1.5, 2.5])
                   for size in (10, 100) for seed in (42, 123) for phase in report.PHASES]
        meta = dict(dirty=True, affinity=[2], ordered_source="/local/ordered",
                    runner_environment="GitHub-hosted CI")
        markdown = report.generate_report(records, meta)
        output = report.generate_html_report(records, meta)
        self.assertEqual(report.spread_text(records[0]), "IQR 1.50–2.50; 4 samples; 2 forks; fork medians [1.50, 2.50]")
        for content in (markdown, output):
            self.assertNotIn("IQR ", content)
            self.assertNotIn("fork medians", content)
            self.assertNotIn("Latency by Dataset Size", content)
            self.assertIn("GitHub-hosted CI", content)
            self.assertIn("/local/ordered", content)
            self.assertIn("Seed 123", content)
        scaling_md = report.scaling_charts(records)
        scaling_html = report.scaling_charts(records, as_html=True)
        for content in (scaling_md, scaling_html):
            self.assertIn("line [2.00, 2.00]", content)
            for phase in report.PHASES:
                self.assertIn(phase.title() + " Scaling", content)
        for name in ("phase", "kind", "order"):
            self.assertIn(f'id="{name}-filter"', output)
        self.assertIn("cell.hidden =", output)

    def test_raw_samples_reject_duplicates_and_nonfinite_values(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            header = "language,implementation,kind,size,order,phase,fork,sample,ns_per_op\n"
            rows = "".join(
                f"rust,btree_map,map,10,ascending,{phase},0,0,2\n" for phase in report.PHASES)
            (path / "samples.csv").write_text(header + rows)
            self.assertEqual(report.load_records(path)[0]["fork_medians"], [2])
            for invalid in (rows + rows.splitlines()[0] + "\n", rows.replace(",2\n", ",nan\n")):
                (path / "samples.csv").write_text(header + invalid)
                with self.assertRaises(ValueError):
                    report.load_records(path)
            (path / "metadata.json").write_text("broken")
            with self.assertRaises(json.JSONDecodeError):
                report.load_metadata(path)

    def test_summary_must_agree_with_raw_samples(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            with (path / "summary.csv").open("w", newline="") as source:
                writer = csv.writer(source)
                writer.writerow(["language", "implementation", "kind", "size", "order", "phase",
                                 "median_ns_per_op", "min_ns_per_op", "max_ns_per_op", "samples"])
                for phase in report.PHASES:
                    writer.writerow(
                        ["rust", "btree_map", "map", 10, "ascending", phase, 2, 2, 2, 1])
            header = "language,implementation,kind,size,order,phase,fork,sample,ns_per_op\n"
            rows = "".join(
                f"rust,btree_map,map,10,ascending,{phase},0,0,3\n" for phase in report.PHASES)
            (path / "samples.csv").write_text(header + rows)
            with self.assertRaisesRegex(ValueError, "disagree"):
                report.load_records(path)
            (path / "samples.csv").write_text(header + rows.replace(",3\n", ",2\n"))
            report.load_records(path)
            (path / "samples.csv").write_text(
                header + rows.replace("btree_map", "btree_set").replace(",map,", ",set,"))
            with self.assertRaisesRegex(ValueError, "coverage differ"):
                report.load_records(path)

    def test_format_metric(self):
        self.assertEqual(report.format_metric(10.5, 10.5), "**10.50**")
        self.assertEqual(report.format_metric(15.2, 10.5), "15.20")
        self.assertEqual(report.format_metric(None, 10.5), "-")
        self.assertEqual(report.format_metric(10.501, 10.5), "10.50")

    def test_render_chart(self):
        chart = report.render_chart("Test Chart", ["A", "B"], [10.5, 20.2])
        self.assertIn("xychart-beta", chart)
        self.assertIn('"A", "B"', chart)
        self.assertIn("10.50, 20.20", chart)
        self.assertIn('"labelRotation": 90', chart)
        self.assertIn('"labelPadding": 16', chart)
        self.assertIn('"height": 650', chart)
        chart = report.render_chart("Missing", ["A", "B", "C"], [None, 0, 20])
        self.assertNotIn('"A"', chart)
        self.assertIn('"B", "C"', chart)
        self.assertIn("bar [0.00, 20.00]", chart)
        self.assertEqual(report.render_chart("Missing", ["A"], [None]), "")

    def test_generate_report(self):
        records = [
            {
                "language": "zig",
                "implementation": "btree_map",
                "kind": "map",
                "size": 1000,
                "order": "ascending",
                "phase": "insert",
                "median_ns_per_op": 20.0,
                "min_ns_per_op": 19.0,
                "max_ns_per_op": 21.0,
                "samples": 1,
            },
            {
                "language": "zig",
                "implementation": "btree_map",
                "kind": "map",
                "size": 1000,
                "order": "ascending",
                "phase": "hit",
                "median_ns_per_op": 30.0,
                "min_ns_per_op": 29.0,
                "max_ns_per_op": 31.0,
                "samples": 1,
            },
            {
                "language": "rust",
                "implementation": "btree_map",
                "kind": "map",
                "size": 1000,
                "order": "ascending",
                "phase": "insert",
                "median_ns_per_op": 35.0,
                "min_ns_per_op": 34.0,
                "max_ns_per_op": 36.0,
                "samples": 1,
            },
            {
                "language": "rust",
                "implementation": "btree_map",
                "kind": "map",
                "size": 1000,
                "order": "ascending",
                "phase": "hit",
                "median_ns_per_op": 15.0,
                "min_ns_per_op": 14.0,
                "max_ns_per_op": 16.0,
                "samples": 1,
            },
        ]
        meta = {
            "cpu": "Test CPU",
            "platform": "Test OS",
            "revision": "123456",
        }
        output = report.generate_report(records, meta)
        self.assertIn("# Benchmark Report: Sorted Maps and Sets", output)
        self.assertIn("Test CPU", output)
        self.assertIn("Ordered BTreeMap", output)
        self.assertIn("| Zig | Ordered BTreeMap |", output)
        self.assertIn("| Rust | std::collections::BTreeMap |", output)
        # The best insert score (20.00) is bold; the slower insert score (35.00) is not bold.
        self.assertIn("**20.00**", output)
        self.assertIn("| 35.00 |", output)
        # The best hit score (15.00) is bold; the slower hit score (30.00) is not bold.
        self.assertIn("**15.00**", output)
        self.assertIn("| 30.00 |", output)
        self.assertNotIn("Sorted Iteration Latency", output)
        self.assertNotIn("bar [0.00", output)

    def test_format_language(self):
        self.assertEqual(report.format_language("c"), "C")
        self.assertEqual(report.format_language("cpp"), "C++")
        self.assertEqual(report.format_language("java"), "Java")
        self.assertEqual(report.format_language("rust"), "Rust")
        self.assertEqual(report.format_language("zig"), "Zig")
        self.assertEqual(report.format_language("unknown"), "Unknown")

    def test_format_html_metric(self):
        self.assertEqual(report.format_html_metric(10.5, 10.5),
                         '<strong class="best">10.50</strong>')
        self.assertEqual(report.format_html_metric(15.2, 10.5), "15.20")
        self.assertEqual(report.format_html_metric(None, 10.5), "-")

    def test_generate_html_report(self):
        records = [
            {
                "language": "zig",
                "implementation": "btree_map",
                "kind": "map",
                "size": 1000,
                "order": "ascending",
                "phase": "insert",
                "median_ns_per_op": 20.0,
                "min_ns_per_op": 19.0,
                "max_ns_per_op": 21.0,
                "samples": 1,
            },
            {
                "language": "zig",
                "implementation": "btree_map",
                "kind": "map",
                "size": 1000,
                "order": "ascending",
                "phase": "hit",
                "median_ns_per_op": 30.0,
                "min_ns_per_op": 29.0,
                "max_ns_per_op": 31.0,
                "samples": 1,
            },
            {
                "language": "rust",
                "implementation": "btree_map",
                "kind": "map",
                "size": 1000,
                "order": "ascending",
                "phase": "insert",
                "median_ns_per_op": 35.0,
                "min_ns_per_op": 34.0,
                "max_ns_per_op": 36.0,
                "samples": 1,
            },
            {
                "language": "rust",
                "implementation": "btree_map",
                "kind": "map",
                "size": 1000,
                "order": "ascending",
                "phase": "hit",
                "median_ns_per_op": 15.0,
                "min_ns_per_op": 14.0,
                "max_ns_per_op": 16.0,
                "samples": 1,
            },
        ]
        meta = {
            "cpu": "Test CPU",
            "platform": "Test OS",
            "revision": "123456",
        }
        output = report.generate_html_report(records, meta)
        self.assertIn("<!DOCTYPE html>", output)
        self.assertIn("Benchmark Report: Sorted Maps and Sets", output)
        self.assertIn("Test CPU", output)
        self.assertIn("Ordered BTreeMap", output)
        self.assertIn("<td>Zig</td>", output)
        self.assertIn("<td>Rust</td>", output)
        self.assertIn('<strong class="best">20.00</strong>', output)
        self.assertIn('<td class="num"><span class="runner-up">35.00</span></td>', output)
        self.assertIn('<strong class="best">15.00</strong>', output)
        self.assertIn('<td class="num"><span class="runner-up">30.00</span></td>', output)
        self.assertIn('<strong class="best">Bold green</strong>', output)
        self.assertIn('<strong class="runner-up">light orange</strong>', output)
        self.assertIn("<li><strong>Insert</strong>:", output)
        self.assertIn("<li><strong>Lookup hit</strong>:", output)
        self.assertIn("<li><strong>B-trees versus binary trees</strong>:", output)
        self.assertIn("xychart-beta", output)
        self.assertIn('<table class="sortable">', output)
        self.assertIn("table.sortable th", output)
        self.assertIn("aria-sort", output)
        self.assertIn(
            '<th><button type="button">Language<span aria-hidden="true"></span></button></th>',
            output)
        self.assertIn("th.querySelector('button').addEventListener('click', sortColumn)", output)
        self.assertIn("h.removeAttribute('aria-sort')", output)
        self.assertNotIn("setAttribute('role', 'button')", output)
        self.assertNotIn("addEventListener('keydown'", output)
        self.assertIn("labelRotation: 90", output)
        self.assertIn("labelPadding: 16", output)
        self.assertIn("height: 650", output)
        self.assertIn(".mermaid { display: block; text-align: center; }", output)
        self.assertNotIn("Sorted Iteration Latency", output)
        self.assertNotIn("bar [0.00", output)
        self.assertNotIn('href="samples.csv"', output)

    def test_build_site(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            res_dir = base / "results"
            site_dir = base / "site"
            res_dir.mkdir()

            summary = res_dir / "summary.csv"
            with summary.open("w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "language",
                    "implementation",
                    "kind",
                    "size",
                    "order",
                    "phase",
                    "median_ns_per_op",
                    "min_ns_per_op",
                    "max_ns_per_op",
                    "samples",
                ])
                for phase in report.PHASES:
                    writer.writerow(
                        ["zig", "btree_map", "map", 1000, "ascending", phase, 20.5, 19, 22, 3])
            (res_dir / "metadata.json").write_text(json.dumps({"cpu": "Test CPU"}))
            with (res_dir / "samples.csv").open("w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(
                    ["language", "implementation", "kind", "size", "order", "phase", "fork",
                     "sample", "ns_per_op"])
                for phase in report.PHASES:
                    for sample, value in enumerate((19, 20.5, 22)):
                        writer.writerow(
                            ["zig", "btree_map", "map", 1000, "ascending", phase, 0, sample, value])

            report.build_site(res_dir, site_dir)

            self.assertTrue((site_dir / "index.html").exists())
            self.assertTrue((site_dir / "REPORT.md").exists())
            self.assertTrue((site_dir / ".nojekyll").exists())
            self.assertTrue((site_dir / "summary.csv").exists())
            self.assertTrue((site_dir / "samples.csv").exists())
            self.assertTrue((site_dir / "metadata.json").exists())
            self.assertIn('href="summary.csv"', (site_dir / "index.html").read_text())

            with (res_dir / "samples.csv").open("w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(
                    ["language", "implementation", "kind", "size", "order", "phase", "fork",
                     "sample", "ns_per_op"])
                for phase in report.PHASES:
                    writer.writerow(["zig", "btree_map", "map", 1000, "ascending", phase, 0, 0, 30])
            summary.unlink()
            (res_dir / "metadata.json").unlink()
            (site_dir / "flake.lock").write_text("stale")
            (site_dir / "custom.txt").write_text("keep")
            report.build_site(res_dir, site_dir)
            for name in ("summary.csv", "metadata.json", "flake.lock"):
                self.assertFalse((site_dir / name).exists())
                self.assertNotIn(f'href="{name}"', (site_dir / "index.html").read_text())
            self.assertEqual((site_dir / "samples.csv").read_bytes(),
                             (res_dir / "samples.csv").read_bytes())
            self.assertIn('href="samples.csv"', (site_dir / "index.html").read_text())
            self.assertEqual((site_dir / "custom.txt").read_text(), "keep")


if __name__ == "__main__":
    unittest.main()
