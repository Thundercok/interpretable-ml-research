# Spider Upstream Extraction & Standalone Workspace

## Overview

This directory (`work/spider-extraction-20261016/`) stages the extracted upstream **Spider** crawler codebase for relocation to an independent, dedicated repository.

Prior to this extraction, the Spider source tree was embedded directly inside the RAT (`multi-step-structured-reasoning`) repository under `spider/`. The goal of this decoupling is repository debloating and zero-maintenance isolation: RAT consumes only the standalone compiled CLI binary via `rat/crawler/spider_adapter.py` and does not compile, link, or maintain any Rust source code.

## Upstream & Version Details

- **Upstream Project**: [spider-rs/spider](https://github.com/spider-rs/spider)
- **License**: MIT License (see `pristine/LICENSE`)
- **Spider CLI Version**: `2.51.208` (`spider_cli/Cargo.toml`)
- **Spider Core Version**: `2.52.0` (`spider/Cargo.toml`)
- **Workspace Crates**:
  - `spider`: Core crawling and scraping engine
  - `spider_cli`: Command-line interface used by RAT
  - `spider_agent`: Web agent automation
  - `spider_agent_html`: HTML parsing and transformation
  - `spider_agent_types`: Shared type definitions
  - `spider_mcp`: Model Context Protocol server implementation
  - `spider_utils`: Utilities and shared helpers
  - `spider_worker`: Distributed crawler worker
- **Inventory Statistics**:
  - Total regular files: 325 (100% byte-matched to `scratch/spider_migration_bundle.tar.gz`)
  - Tracked Rust files: 269 (`.rs` extension, 123,868 non-empty lines)
  - Tracked text files: 321 (139,745 non-empty lines)
  - Executable scripts: `release.sh` (mode `0755`, 38 non-empty lines)

## Directory Structure

```text
work/spider-extraction-20261016/
├── README.md               # This document
├── inventory.json          # Complete 325-file manifest with SHA256 hashes and line metrics
├── patches/
│   └── 0001-fix-workspace-manifest-syntax.patch # Fix for Cargo.toml members syntax error
└── pristine/               # Exact byte-for-byte copy of the 325 files in spider/
```

## Local Modifications & Syntax Patch

The snapshot stored in the RAT repository includes:
1. `release.sh`: Workspace synchronization and publishing shell script.
2. `examples/cv_job_crawler.rs`: Custom recruitment/CV scraping example.
3. Syntax error in root `Cargo.toml`: Lines 11–13 placed an `[[example]]` definition inside the `members = [...]` array, which prevents `cargo` from parsing the root workspace manifest.

To preserve strict byte-for-byte parity with the in-repo snapshot and migration archive, `pristine/` is maintained without modifications.

Keep `pristine/` unchanged. Create a new build copy outside it, then apply
`patches/0001-fix-workspace-manifest-syntax.patch` in that copy. The patch removes
the invalid three-line example registration from the workspace members array;
it does not move or register that example elsewhere. The example source remains
preserved in the pristine snapshot.

## Standalone Build Instructions

Codex verified patch application, TOML parsing and `cargo metadata --offline
--no-deps --format-version 1` in a disposable standalone copy. This verifies
workspace metadata, not successful compilation or an identical release binary.
Record the actual Rust toolchain/target and dependency/build provenance.

In a fresh build copy, the candidate minimal HTTP build is:

```bash
patch -p1 < /absolute/path/to/patches/0001-fix-workspace-manifest-syntax.patch
cargo metadata --offline --no-deps --format-version 1
cargo build --offline --release -p spider_cli --bin spider --no-default-features --features "spider_cli/status_code,spider_cli/headers"
./target/release/spider --version
```

The command intentionally disables default CLI features (Chrome/WARC/cloud).
Do not substitute a default-feature build and describe it as the same binary
used by RAT. Full compilation of this staged tree remains to be validated in
the destination/build workspace; preserve the existing binary until then.

## Zero-Maintenance Boundary with RAT

RAT integrates with Spider strictly through an external binary boundary:
- **Binary Path**: `rat/bin/spider` (version 2.51.208, SHA256: `bd522395c85cb80df0172066ba8d49dc538dfdec04693dc67455f3a1ee756f54`)
- **Adapter Service**: `rat/crawler/spider_adapter.py` invokes the binary with `subprocess.Popen` and selector-based pipe reading. Actual scrape argv: `--url <URL> --limit 1 --budget "*,1" --http --return-format markdown -H scrape --output-html`.
- **Fail-Closed Default**: RAT's default registry in `rat/kernel/capabilities/__init__.py` specifies `enable_web=False`. Web tools are unavailable by default until per-hop network controls are completed.
- **Packaging Isolation**: `rat.spec` does not bundle `rat/bin/spider`; this is a packaging limitation, not proof of offline behavior. Web remains unavailable by default, and an enabled setup requires a separately installed compatible binary.
- **Independence**: RAT has zero build-time, compile-time, or runtime dependencies on the `spider/` source tree.

## Migration to New Repository

When the user specifies the target repository or path:
1. Copy `pristine/` to the destination repository.
2. Apply `patches/0001-fix-workspace-manifest-syntax.patch`.
3. Verify destination parity, recovery and the standalone build/dependency contract. Git initialization/commits/publishing follow explicit user instructions.
4. Only after the agreed source-migration conditions pass, remove the original `spider/` tree. Keep recovery material. Scratch build cleanup is a separate task and is not included in source deletion.

Codex review and isolated-test evidence: `audit/spider_extraction_codex_review_20261016/`. The 93 tests passed without Spider source, scratch build or bundled binary; this verifies default-disabled/missing-binary behavior, not live web operation.
