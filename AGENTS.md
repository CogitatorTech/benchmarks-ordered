# AGENTS.md

## Purpose

This repository compares sorted maps and sets in Ordered, Zig, Rust, C, C++, and Java.
Keep benchmark dependencies here. Do not modify Ordered as part of a benchmark change.

## Environment

- Use `nix develop` for all development, builds, and measurements.
- Commit `flake.lock`. It pins toolchains, Ordered, klib, and Abseil through Nixpkgs.
- Keep `pyproject.toml`, `uv.lock`, and `.python-version` for Python development tooling.
- Keep the original Makefile style with configuration and target sections and documented help entries.
- Keep benchmark implementations under `benchmarks/<language>/` and shared C/C++ code under `benchmarks/common/`.
- Keep Rust as a standalone Cargo project in `benchmarks/rust/` and commit its `Cargo.lock`.
- Use `ORDERED_SOURCE` for the pinned library. Local overrides must be recorded in results.
- Keep the Ordered revision in Nix and `build.zig.zon` aligned.
- Never silently skip an implementation when a toolchain or dependency is missing.
- Keep source, comments, documentation, and tests in English.
- Prefer small changes, complete sentences, title case headings, and Oxford commas.
- Do not use em dashes.

## Writing Style

- Write in simple, plain English. Use short sentences and everyday words.
- Use Oxford commas in inline lists: "a, b, and c" not "a, b, c".
- Do not use em dashes. Restructure the sentence, or use a colon or semicolon instead.
- Avoid colorful adjectives and adverbs. Write "vector quantization library" not "powerful vector quantization library".
- Use noun phrases for checklist items, not imperative verbs. Write "distance metric coverage" not "cover distance metrics".
- Headings in Markdown files must be in title case: "Build from Source" not "Build from source". Minor words (a, an, the, and, but, or, for, in, on,
  at, to, by, of, is, are, was, were, be) stay lowercase unless they are the first word.

## Benchmark Contract

- Compare containers that maintain sorted key order. Hash maps are outside this suite.
- Maps store signed 64-bit integer keys and values. Sets store the same keys.
- Every implementation consumes the same generated fixture, including independent insertion,
  lookup, and removal permutations. Dataset generation and parsing stay outside timers.
- Measure insertion, lookup hits, lookup misses, sorted iteration, and removal separately.
- Include container allocation in insertion and node freeing in native removal. Document Java GC.
- Consume results and validate counts, values, and iteration order. A failed check invalidates a run.
- Keep correctness validation outside measured regions wherever possible.
- Build native runners with release optimization. Do not enable fast math or disable checks in harness code.
- Keep raw samples and environment metadata. Do not publish a universal winner from one workload.
- Use JMH for Java, including JVM forks and warmup. Document boxing and heap settings.
- CI checks correctness and buildability. CI timings are not performance regression gates.

## Validation

Run `make test` and `make lint` inside `nix develop` after changes. Run `make smoke` after changing
a runner, workload, or result format. Use `make bench` for repeatable local measurements.
Add a regression test for nontrivial harness logic and use edge fixtures for container adapters.
Never run full benchmarks automatically during shell startup or dependency setup.

## Scope

The first suite covers integer maps and sets on one thread. Strings, prefix queries, range queries,
concurrency, and cross-language memory accounting require separately documented workloads.
Do not add a framework, dashboard, or dependency unless the comparison needs it.
