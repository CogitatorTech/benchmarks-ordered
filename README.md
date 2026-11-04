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

Check out [docs/benchmarks.md](docs/benchmarks.md) for more details on the benchmarking methodology.

---

### Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for details on how to make a contribution.

### License

This project is licensed under the MIT License (see [LICENSE](LICENSE)).
