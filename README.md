## Benchmarks for the Ordered Library

[![Tests](https://img.shields.io/github/actions/workflow/status/CogitatorTech/benchmarks-ordered/tests.yml?label=tests&style=flat&labelColor=333333&logo=github&logoColor=white)](https://github.com/CogitatorTech/benchmarks-ordered/actions/workflows/tests.yml)
[![Benchmark Results](https://img.shields.io/badge/benchmark%20results-view-507ec6?style=flat&labelColor=282c34&logo=github)](https://cogitatortech.github.io/benchmarks-ordered)
[![License](https://img.shields.io/badge/license-MIT-3776ab?style=flat&labelColor=333333)](LICENSE)

---

Benchmarks to compare sorted maps and sets implemented in the [Ordered](https://github.com/CogitatorTech/ordered) Zig library with similar
implementations in Rust, C, C++, and Java.

**You can see the latest benchmark results [here](https://cogitatortech.github.io/benchmarks-ordered/).**

### Implementations

| Language | Sorted Maps                                                                                                                                         | Sorted Sets                                                                                                                     |
|----------|-----------------------------------------------------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------|
| Zig      | [Ordered][ordered-repo] [`BTreeMap`][ordered-docs], [`CartesianTreeMap`][ordered-docs], and [`SkipListMap`][ordered-docs]; [`std.Treap`][zig-treap] | [Ordered][ordered-repo] [`SortedSet`][ordered-docs] and [`RedBlackTreeSet`][ordered-docs]; [`std.Treap`][zig-treap]             |
| Rust     | [`std::collections::BTreeMap`][rust-btreemap] and [`indexset::BTreeMap`][indexset-btreemap]                                                         | [`std::collections::BTreeSet`][rust-btreeset] and [`indexset::BTreeSet`][indexset-btreeset]                                     |
| C        | [Klib `kbtree`][klib-kbtree] with key-value entries, [Klib `kavl`][klib-kavl] AVL tree, and [`tidwall/btree.c`][tidwall-btree]                      | [Klib `kbtree`][klib-kbtree] with keys, [Klib `kavl`][klib-kavl] AVL tree, and [`tidwall/btree.c`][tidwall-btree]               |
| C++      | [`std::map`][cpp-map], [Abseil `btree_map`][abseil-btree], and [Boost `flat_map`][boost-flat-map]                                                   | [`std::set`][cpp-set], [Abseil `btree_set`][abseil-btree], and [Boost `flat_set`][boost-flat-set]                               |
| Java     | [`TreeMap<Long, Long>`][java-treemap], [fastutil `Long2LongAVLTreeMap`][fastutil-avl-map], and [fastutil `Long2LongRBTreeMap`][fastutil-rb-map]     | [`TreeSet<Long>`][java-treeset], [fastutil `LongAVLTreeSet`][fastutil-avl-set], and [fastutil `LongRBTreeSet`][fastutil-rb-set] |

[ordered-repo]: https://github.com/CogitatorTech/ordered
[ordered-docs]: https://cogitatortech.github.io/ordered/
[zig-treap]: https://ziglang.org/documentation/master/std/#std.treap.Treap
[rust-btreemap]: https://doc.rust-lang.org/std/collections/struct.BTreeMap.html
[rust-btreeset]: https://doc.rust-lang.org/std/collections/struct.BTreeSet.html
[indexset-btreemap]: https://docs.rs/indexset/latest/indexset/struct.BTreeMap.html
[indexset-btreeset]: https://docs.rs/indexset/latest/indexset/struct.BTreeSet.html
[klib-kbtree]: https://github.com/attractivechaos/klib/blob/master/kbtree.h
[klib-kavl]: https://github.com/attractivechaos/klib/blob/master/kavl.h
[tidwall-btree]: https://github.com/tidwall/btree.c
[cpp-map]: https://en.cppreference.com/w/cpp/container/map
[cpp-set]: https://en.cppreference.com/w/cpp/container/set
[abseil-btree]: https://abseil.io/docs/cpp/guides/container#btree-containers
[boost-flat-map]: https://www.boost.org/doc/libs/release/doc/html/doxygen/boost_container_header_reference/classboost_1_1container_1_1flat__map.html
[boost-flat-set]: https://www.boost.org/doc/libs/release/doc/html/doxygen/boost_container_header_reference/classboost_1_1container_1_1flat__set.html
[java-treemap]: https://docs.oracle.com/en/java/javase/25/docs/api/java.base/java/util/TreeMap.html
[java-treeset]: https://docs.oracle.com/en/java/javase/25/docs/api/java.base/java/util/TreeSet.html
[fastutil-avl-map]: https://fastutil.di.unimi.it/docs/it/unimi/dsi/fastutil/longs/Long2LongAVLTreeMap.html
[fastutil-rb-map]: https://fastutil.di.unimi.it/docs/it/unimi/dsi/fastutil/longs/Long2LongRBTreeMap.html
[fastutil-avl-set]: https://fastutil.di.unimi.it/docs/it/unimi/dsi/fastutil/longs/LongAVLTreeSet.html
[fastutil-rb-set]: https://fastutil.di.unimi.it/docs/it/unimi/dsi/fastutil/longs/LongRBTreeSet.html

---

### Quickstart

For the steps below to work, you need to have Git and [Nix](https://nixos.org/download/) (with flakes enabled) installed on your machine.

#### 1. Clone the repository

```bash
git clone https://github.com/CogitatorTech/benchmarks-ordered.git
cd benchmarks-ordered
```

#### 2. Set up the environment

```bash
nix develop
```

#### 3. Build and run the benchmarks

```bash
make build
make bench # This may take a while
```

The (raw) results of the benchmarks are stored in the `results/` directory.

#### 4. Generate the performance report (optional)

```bash
make report
```

### Measurement Method

The default workload uses 1,000, 10,000, 100,000, 300,000, and 1,000,000 elements.
Each workload runs with fixture seeds 42, 123, and 2026. Reports keep seeds separate.
Ascending and shuffled refer to insertion order. Lookup and removal use independent
shuffled permutations. Every implementation receives the same fixture for a given
size, order, and seed. Fixture files and SHA-256 hashes stay with the raw results.

Implementation order is shuffled between forks with a recorded schedule seed.
Each native fork runs three warmups and five measurements by default. Java uses
JMH with 20 warmups and five measurements per fork. The default is two forks.
For a published comparison, use a dedicated idle machine and pin the run to an
allowed CPU. This command uses CPU 2 as an example.

```bash
nix develop --command make bench ARGS="--cpu 2 --forks 3"
```

A smaller repeatable run can override sizes and seeds.

```bash
nix develop --command make bench ARGS="--sizes 1000,10000 --seeds 42 --forks 3"
```

Insertion includes empty container construction and node allocation. Java boxed
keys and values are prepared before timing, so boxing allocation cost is excluded.
Java uses a 1 GiB initial and maximum heap. Removal unlinks Java entries without
forcing garbage collection. GC may occur during measured work. Native removal
includes node freeing. Read and removal phases use freshly populated and validated
containers, so they measure recently accessed data rather than cold caches.

### Reading Reports

Tables show medians, sample interquartile ranges, sample counts, fork counts, and
individual fork medians. The IQR describes the middle half of samples. It is not a
confidence interval. Measurements within a fork share a process and are not
independent process runs. Highlighting marks the lowest measured median and does
not establish a winner. Older summary-only results show their range and mark
unavailable IQR and fork details explicitly.

HTML reports filter by operation, map or set, and insertion order. Charts cover all
five phases and show latency across dataset sizes for each implementation and
fixture seed. Scaling charts use equally spaced labels for the measured sizes.
Reports include run provenance and distinguish CI measurements. GitHub-hosted CI
timings are exploratory and are not performance regression gates.

New runs record the expected implementations, workloads, and sample identities.
Report generation rejects missing groups, invalid timings, duplicate samples, and
summary values that disagree with raw data. For older runs without a manifest,
coverage is checked against recorded toolchains when available, or observed
implementations otherwise. An entirely absent implementation cannot be detected
from legacy files that lack both sources of coverage information.

Mixed operations and other key distributions remain separate workloads. This suite
measures the existing integer container contract only.

---

### Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for details on how to make a contribution.

### License

This project is licensed under the MIT License (see [LICENSE](LICENSE)).
