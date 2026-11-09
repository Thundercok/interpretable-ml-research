# EVRP / SaigonRide Standalone Workspace

## Overview

This directory (`work/evrp-extraction-20261016/`) stages the extracted **EVRP / SaigonRide** module for independent relocation outside the RAT (`multi-step-structured-reasoning`) repository.

## Provenance & Candidate Repositories

- **Import Origin**: `https://github.com/Thundercok/evrp-optimizer.git`
- **Subtree Import Revision**: `2c8fa69f8f3cfeae475792159ff0ebcf20529044` (104 original commits preserved in `.migration-backups/20261013_evrp/evrp-optimizer.bundle`)
- **Documentation Destination Link**: `https://github.com/Thundercok/SaigonRide` (referenced in root `README.md`)
- **Status of Remotes**: Unauthenticated remote queries to both repositories currently return 404 / `Repository not found`. The full 104-commit history is safely backed up in the Git bundle.
- **Local Extra Files**: 7 files verified exact byte-for-byte:
  1. `data/vietnam_charging_stations.csv`
  2. `data/vietnam_charging_stations.json`
  3. `data/vietnam_charging_stations_raw.json`
  4. `results/benchmark_results.json`
  5. `results/benchmark_table.md`
  6. `scripts/fetch_charging_stations.py`
  7. `scripts/run_benchmark.py`

## Inventory Statistics

- **Total Regular Files**: 448 (447 git-tracked, 1 untracked bytecode file)
- **Total Bytes on Disk**: 41,379,543 bytes (~41.4 MB)
- **Total Non-Empty Lines**: 191,214 lines (26,903 scanner-visible authored source lines across 247 source files)
- **Primary Languages**:
  - C# (`.cs`): 160 files (17,794 non-empty lines)
  - Razor (`.cshtml`): 62 files (4,765 non-empty lines)
  - Python (`.py`): 3 files (1,507 non-empty lines)
  - JavaScript / CSS: 88 files (149,998 non-empty lines)

## Decoupling & Isolation from RAT

- **No Shared Runtime**: RAT has zero runtime, build-time, or test dependencies on EVRP.
- **Verified Offline Startup**: When `modules/evrp` is completely absent, RAT's default registry initializes all 17 operations cleanly, and all 93 unit/runtime tests pass (`tests/test_spider_adapter.py`, `tests/test_assistant_runtime.py`, `tests/test_work_context.py`).
- **Research Boundary**: EVRP solver heuristics (`EvrpSolverService.cs`) and synthetic procedural benchmarks (`run_benchmark.py`) are legacy domain assets. They do not constitute CoT evaluation evidence, BKS comparisons, or model quality benchmarks for the NCKH research study.
