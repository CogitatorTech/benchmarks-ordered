################################################################################
# Configuration and Variables
################################################################################
PYTHON         ?= python3
ZIG            ?= zig
CARGO          ?= cargo
NIXFMT         ?= nixfmt
UV             ?= uv
ARGS           ?=
BENCHMARKS_DIR := benchmarks
HARNESS        := scripts/bench.py

export ZIG CARGO

SHELL       := /usr/bin/env bash
.SHELLFLAGS := -eu -o pipefail -c

################################################################################
# Targets
################################################################################

.PHONY: all help build run test lint format smoke bench setup-hooks test-hooks
.DEFAULT_GOAL := help

help: ## Show the help messages for all targets
	@grep -E '^[a-zA-Z0-9_-]+:.*?## ' Makefile | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-14s %s\n", $$1, $$2}'

all: test lint ## Build runners, run correctness tests, and check formatting

build: ## Build all benchmark runners in release mode
	@echo "Building benchmark runners..."
	$(PYTHON) $(HARNESS) build $(ARGS)

run: smoke ## Run the smoke benchmark

test: ## Run harness tests and correctness checks for all implementations
	@echo "Running benchmark correctness tests..."
	$(PYTHON) -m unittest discover -s scripts -p 'test_*.py'
	$(PYTHON) $(HARNESS) test $(ARGS)

lint: ## Check Zig, Rust, and Nix formatting and Python syntax
	@echo "Running code style checks..."
	$(ZIG) fmt --check build.zig $(BENCHMARKS_DIR)/zig
	$(CARGO) fmt --manifest-path $(BENCHMARKS_DIR)/rust/Cargo.toml --check
	$(NIXFMT) --check flake.nix
	$(PYTHON) -m compileall -q scripts

format: ## Format Zig, Rust, and Nix files
	@echo "Formatting source files..."
	$(ZIG) fmt build.zig $(BENCHMARKS_DIR)/zig
	$(CARGO) fmt --manifest-path $(BENCHMARKS_DIR)/rust/Cargo.toml
	$(NIXFMT) flake.nix

smoke: build ## Run a short benchmark to verify result collection
	@echo "Running the smoke benchmark..."
	$(PYTHON) $(HARNESS) bench --sizes 1000 --warmups 1 --samples 1 --forks 1 $(ARGS)

bench: build ## Run benchmarks with the default workloads or ARGS overrides
	@echo "Running benchmarks..."
	$(PYTHON) $(HARNESS) bench $(ARGS)

setup-hooks: ## Install Git hooks using the locked Python environment
	@echo "Installing Git hooks..."
	$(UV) run --locked pre-commit install --hook-type pre-commit
	$(UV) run --locked pre-commit install --hook-type pre-push

test-hooks: ## Run Git hooks on all files manually
	@echo "Running Git hooks..."
	$(UV) run --locked pre-commit run --all-files
