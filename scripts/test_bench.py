import csv
import copy
from pathlib import Path
import struct
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import bench


class HarnessTests(unittest.TestCase):
    def test_fixture_permutations_and_independent_probes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.bin"
            bench.fixture(path, 31, "shuffled")
            first = path.read_bytes()
            bench.fixture(path, 31, "shuffled")
            self.assertEqual(first, path.read_bytes())
            self.assertEqual(struct.unpack_from("<Q", first)[0], 31)
            arrays = [struct.unpack_from("<31q", first, 8 + i * 31 * 8) for i in range(3)]
            for array in arrays:
                self.assertEqual(sorted(array), list(range(0, 62, 2)))
            self.assertEqual(len(set(arrays)), 3)
            bench.fixture(path, 31, "ascending")
            self.assertEqual(struct.unpack_from("<31q", path.read_bytes(), 8), tuple(range(0, 62, 2)))

    def test_empty_fixture(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.bin"
            bench.fixture(path, 0, "ascending")
            self.assertEqual(path.read_bytes(), bytes(8))

    def test_native_output_validation(self):
        good = "\n".join(f"{phase},10" for phase in bench.PHASES)
        self.assertEqual(bench.parse_native(good), dict.fromkeys(bench.PHASES, 10))
        for bad in ("", good.replace("insert", "unknown"), good.replace("10", "-1"), good + "\ninsert,10", "insert,wrong"):
            with self.subTest(bad=bad), self.assertRaises((ValueError, csv.Error)):
                bench.parse_native(bad)

    def test_jmh_samples_and_validation(self):
        results = [{"benchmark": "bench.CollectionsBench." + phase,
                    "primaryMetric": {"scoreUnit": "ns/op", "rawData": [[10, 20], [30, 40]]}}
                   for phase in bench.PHASES]
        rows = list(bench.jmh_samples(results, 2, 2))
        self.assertEqual(len(rows), 20)
        self.assertEqual(rows[:4], [("insert", 0, 0, 10), ("insert", 0, 1, 20),
                                    ("insert", 1, 0, 30), ("insert", 1, 1, 40)])
        bad_cases = [results[:-1], results + results[:1]]
        for field, value in (("scoreUnit", "ms/op"), ("rawData", [[]]),
                             ("rawData", [[float("nan"), 20], [30, 40]])):
            bad = copy.deepcopy(results)
            bad[0]["primaryMetric"][field] = value
            bad_cases.append(bad)
        for bad in bad_cases:
            with self.assertRaises(ValueError):
                list(bench.jmh_samples(bad, 2, 2))

    def test_implementation_names(self):
        for language, impls in bench.IMPLS.items():
            self.assertTrue(len(impls) > 0)
            for impl in impls:
                self.assertTrue(
                    impl.endswith("_map") or impl.endswith("_set"),
                    f"{impl} must end with _map or _set",
                )

    def test_summary_is_published_only_after_success(self):
        output = "\n".join(f"{phase},10" for phase in bench.PHASES)
        with tempfile.TemporaryDirectory() as directory:
            args = SimpleNamespace(sizes="1", output=str(Path(directory) / "success"),
                                   warmups=0, samples=1, forks=1)
            with patch.object(bench, "require_env"), patch.object(bench, "metadata", return_value={}), \
                 patch.object(bench, "IMPLS", {"rust": ["btree_map"]}), \
                 patch.object(bench, "run", return_value=SimpleNamespace(stdout=output)):
                bench.bench(args, ["rust"])
                self.assertTrue((Path(args.output) / "summary.csv").is_file())
                self.assertFalse((Path(args.output) / "summary.csv.tmp").exists())
                args.output = str(Path(directory) / "failed")
                with patch.object(bench.statistics, "median", side_effect=ValueError("interrupted")):
                    with self.assertRaisesRegex(ValueError, "interrupted"):
                        bench.bench(args, ["rust"])
                self.assertFalse((Path(args.output) / "summary.csv").exists())
                self.assertTrue((Path(args.output) / "summary.csv.tmp").is_file())


if __name__ == "__main__":
    unittest.main()
