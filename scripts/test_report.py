import csv
import json
from pathlib import Path
import tempfile
import unittest

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
            latest = report.find_latest_results(base)
            self.assertEqual(latest, d2)

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
                writer.writerow([
                    "zig",
                    "btree_map",
                    "map",
                    "1000",
                    "ascending",
                    "insert",
                    "20.5",
                    "19.0",
                    "22.0",
                    "3",
                ])
            records = report.load_records(d)
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["language"], "zig")
            self.assertEqual(records[0]["median_ns_per_op"], 20.5)

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
                writer.writerow([
                    "rust",
                    "btree_map",
                    "map",
                    "1000",
                    "ascending",
                    "hit",
                    "0",
                    "0",
                    "25.0",
                ])
                writer.writerow([
                    "rust",
                    "btree_map",
                    "map",
                    "1000",
                    "ascending",
                    "hit",
                    "0",
                    "1",
                    "35.0",
                ])
            records = report.load_records(d)
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["median_ns_per_op"], 30.0)
            self.assertEqual(records[0]["min_ns_per_op"], 25.0)
            self.assertEqual(records[0]["max_ns_per_op"], 35.0)

    def test_format_metric(self):
        self.assertEqual(report.format_metric(10.5, 10.5), "**10.50**")
        self.assertEqual(report.format_metric(15.2, 10.5), "15.20")
        self.assertEqual(report.format_metric(None, 10.5), "-")

    def test_render_chart(self):
        chart = report.render_chart("Test Chart", ["A", "B"], [10.5, 20.2])
        self.assertIn("xychart-beta", chart)
        self.assertIn('"A", "B"', chart)
        self.assertIn("10.50, 20.20", chart)

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
        # Best insert (20.00) is bold, worse insert (35.00) is not bold
        self.assertIn("**20.00**", output)
        self.assertIn("| 35.00 |", output)
        # Best hit (15.00) is bold, worse hit (30.00) is not bold
        self.assertIn("**15.00**", output)
        self.assertIn("| 30.00 |", output)

    def test_format_html_metric(self):
        self.assertEqual(report.format_html_metric(10.5, 10.5), '<strong class="best">10.50</strong>')
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
        self.assertIn('<strong class="best">20.00</strong>', output)
        self.assertIn('<td class="num">35.00</td>', output)
        self.assertIn('<strong class="best">15.00</strong>', output)
        self.assertIn('<td class="num">30.00</td>', output)
        self.assertIn("xychart-beta", output)

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
                writer.writerow([
                    "zig",
                    "btree_map",
                    "map",
                    "1000",
                    "ascending",
                    "insert",
                    "20.5",
                    "19.0",
                    "22.0",
                    "3",
                ])
            (res_dir / "metadata.json").write_text(json.dumps({"cpu": "Test CPU"}))
            (res_dir / "samples.csv").write_text("header\n")

            report.build_site(res_dir, site_dir)

            self.assertTrue((site_dir / "index.html").exists())
            self.assertTrue((site_dir / "REPORT.md").exists())
            self.assertTrue((site_dir / ".nojekyll").exists())
            self.assertTrue((site_dir / "summary.csv").exists())
            self.assertTrue((site_dir / "samples.csv").exists())
            self.assertTrue((site_dir / "metadata.json").exists())


if __name__ == "__main__":
    unittest.main()
