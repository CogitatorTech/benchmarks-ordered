## Benchmarks for the Ordered Library

[![Tests](https://img.shields.io/github/actions/workflow/status/CogitatorTech/benchmarks-ordered/tests.yml?label=tests&style=flat&labelColor=333333&logo=github&logoColor=white)](https://github.com/CogitatorTech/benchmarks-ordered/actions/workflows/tests.yml)
[![License](https://img.shields.io/badge/license-MIT-3776ab?style=flat&labelColor=333333)](LICENSE)

---

Benchmarks to compare sorted maps and sets implemented in the Ordered Zig library with similar implementations in Rust, C, C++, and Java.

### Implementations

| Language | Sorted Maps                                                                              | Sorted Sets                                                              |
|----------|------------------------------------------------------------------------------------------|--------------------------------------------------------------------------|
| Zig      | Ordered `BTreeMap`, `CartesianTreeMap`, and `SkipListMap`; `std.Treap`                   | Ordered `SortedSet` and `RedBlackTreeSet`; `std.Treap`                   |
| Rust     | `std::collections::BTreeMap` and `indexset::BTreeMap`                                    | `std::collections::BTreeSet` and `indexset::BTreeSet`                    |
| C        | Klib `kbtree` with key-value entries, Klib `kavl` AVL tree, and `tidwall/btree.c`        | Klib `kbtree` with keys, Klib `kavl` AVL tree, and `tidwall/btree.c`     |
| C++      | `std::map`, Abseil `btree_map`, and Boost `flat_map`                                     | `std::set`, Abseil `btree_set`, and Boost `flat_set`                     |
| Java     | `TreeMap<Long, Long>`, fastutil `Long2LongAVLTreeMap`, and fastutil `Long2LongRBTreeMap` | `TreeSet<Long>`, fastutil `LongAVLTreeSet`, and fastutil `LongRBTreeSet` |

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

The results of the benchmarks are stored in the `results` directory.

#### 4. Generate reports (optional)

```bash
make report
```

---

### Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for details on how to make a contribution.

### License

This project is licensed under the MIT License (see [LICENSE](LICENSE)).
