## Benchmarking Methodology

### Measurement Method

The default workload uses 1,000, 10,000, 100,000, 300,000, and 1,000,000 elements.
Each workload runs with fixture seeds 42, 123, and 2026.
Reports keep seeds separate.
The added sizes and seeds increase runtime, especially for flat containers under random mutation.
Ascending and shuffled refer to insertion order. Lookup and removal use independent shuffled permutations.
Every implementation receives the same fixture for a given size, order, and seed.
Fixture files and SHA-256 hashes stay with the raw results.

Implementation order is shuffled between forks with a recorded schedule seed.
Each native fork runs three warmups and five measurements by default.
Java uses JMH with 20 warmups and five measurements per fork. The default is two forks.
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
coverage is checked against observed implementations. Toolchain versions do not
identify which adapters existed at the time of the run. An entirely absent
implementation cannot be detected in legacy files without a manifest.

Mixed operations and other key distributions remain separate workloads.
This suite measures the existing integer container contract only.
