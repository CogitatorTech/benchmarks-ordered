## Benchmarks for the Ordered Library

[![Tests](https://img.shields.io/github/actions/workflow/status/CogitatorTech/benchmarks-ordered/tests.yml?label=tests&style=flat&labelColor=333333&logo=github&logoColor=white)](https://github.com/CogitatorTech/benchmarks-ordered/actions/workflows/tests.yml)
[![License](https://img.shields.io/badge/license-MIT-3776ab?style=flat&labelColor=333333)](LICENSE)

---

Benchmarks to compare sorted maps and sets implemented in the Ordered Zig library with similar implementations in Rust, C, C++, and Java.

### Implementations

| Language | Sorted Maps                                                            | Sorted Sets                                            |
|----------|------------------------------------------------------------------------|--------------------------------------------------------|
| Zig      | Ordered `BTreeMap`, `CartesianTreeMap`, and `SkipListMap`; `std.Treap` | Ordered `SortedSet` and `RedBlackTreeSet`; `std.Treap` |
| Rust     | `std::collections::BTreeMap`                                           | `std::collections::BTreeSet`                           |
| C        | Klib `kbtree` with key-value entries                                   | Klib `kbtree` with keys                                |
| C++      | `std::map` and Abseil `btree_map`                                      | `std::set` and Abseil `btree_set`                      |
| Java     | `TreeMap<Long, Long>`                                                  | `TreeSet<Long>`                                        |

---

### Quickstart

For the steps below to work, you need to have [Nix](https://nixos.org/download/) installed on your machine.

#### 1. Set up the environment

```bash
nix develop
```

#### 2. Clone the repository

```bash
git clone https://github.com/CogitatorTech/benchmarks-ordered.git
cd benchmarks-ordered
```

#### 3. Build and run the benchmarks

```bash
make build
make bench
```

The results of the benchmarks are stored in the `results` directory.

---

### Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for details on how to make a contribution.

### License

This project is licensed under the MIT License (see [LICENSE](LICENSE)).
