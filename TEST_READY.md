# TEST READY: OnePlus 13R (CPH2691) E2E Test Suite

**Status**: READY FOR VERIFICATION & CONTINUOUS INTEGRATION  
**Author**: E2E Test Engineer (`e2e_tester`)  
**Target Device**: OnePlus 13R (`CPH2691` / `CPH2691IN`, OxygenOS 15/16, Android 15/16)  
**Project Root**: `C:\Users\Harsh\.gemini\antigravity\scratch\oneplus_13r_optimizer`  
**Test Suite Directory**: `tests/`  

---

## 1. Executive Summary

The comprehensive, 7-Tier opaque-box test suite for the OnePlus 13R (CPH2691) Safe Optimization Guide overhaul has been built, self-verified, and placed under version control in `tests/`.

The suite provides **46 automated test cases** designed with zero external third-party dependencies, executing natively via Python's standard `unittest` framework on Windows PowerShell 5.1+, Windows Terminal, and POSIX platforms.

A high-fidelity Mock ADB simulator (`tests/mock_adb.py` and Windows wrappers `tests/mock_adb.cmd`, `tests/mock_adb.bat`) provides complete offline execution for all device-facing commands, simulating device authorization state transitions (`authorizing` -> `device`), package manager queries, hardware properties (`ro.product.model`), settings namespaces (`global`, `secure`, `system`), and verbatim Java runtime exceptions for deprecated OxygenOS packages.

---

## 2. Test Architecture & Tier Inventory

| Tier | Test Suite File | Scope & Objectives | Test Count | Current Status |
| :--- | :--- | :--- | :---: | :--- |
| **Tier 1** | `tests/test_cli.py` | CLI flags (`--help`, `-h`, `--dry-run`, invalid arguments, `--config`, `--no-color`), exit code contracts (0 for success/preview, 1 for runtime failure, 2 for CLI parse/config error). | 6 | ⏳ Awaiting `optimize_13r.py` (M2) |
| **Tier 2** | `tests/test_config.py` | Configuration loading (`config.yaml` & `config.json`), model verification (`CPH2691`), 15-package NEVER TOUCH blacklist integrity, safety invariant (zero blacklist packages in freeze targets), 12-phase schema validation, YAML/JSON parity, and CLI `--config` override. | 9 | ✅ 7 Passing / ⏳ 2 Awaiting M2 |
| **Tier 3** | `tests/test_phases.py` | Granular phase selection (`--phases 1,2,3`, `--phases 2`), phase skipping (`--skip 5,7`), combined filter logic (`--phases 1,2,3 --skip 2`), whitespace handling, and invalid phase reporting. | 6 | ⏳ Awaiting `optimize_13r.py` (M2) |
| **Tier 4** | `tests/test_dry_run.py` | Offline dry-run simulation without connected hardware (`--dry-run` exits 0), forward command preview, reverse rollback preview (`--dry-run --undo`), inclusion of at least 3 new categories, summary status table rendering, and zero side effects. | 5 | ⏳ Awaiting `optimize_13r.py` (M2) |
| **Tier 5** | `tests/test_undo_symmetry.py` | Programmatic verification of 100% symmetric rollback: every single applied setting (animations, radios, Doze whitelist, telemetry freeze, AOT compilation, Google Wallet/NFC, GPU Game Driver, display refresh rate) has an exact reverse command. | 7 | ⏳ Awaiting `optimize_13r.py` (M2) |
| **Tier 6** | `tests/test_missing_packages.py` | Real-World Issue 2 resilience: verifies that non-existent packages (`com.oplus.crashbox`, `com.heytap.pictorial`, `net.oneplus.forums`) do NOT crash the script, do NOT print unhandled Java crash dumps, and produce clean warnings (⚠️) with exit code 0. | 3 | ⏳ Awaiting `optimize_13r.py` (M2) |
| **Tier 7** | `tests/test_mock_adb.py` | Unit tests for Mock ADB simulator (version, start-server daemon, devices listing, authorization state machine, getprop, pm list, Java exceptions, settings datastore) and optimizer integration (server warmup, authorization retry loop, custom `--adb-path`). | 10 | ✅ 8 Passing / ⏳ 2 Awaiting M2 |
| **TOTAL** | **46 Tests** | **Comprehensive Full-Spectrum Verification** | **46** | **15 PASS / 31 PENDING M2** |

---

## 3. How to Run the Tests

### Master Test Runner (Recommended)
Run all 7 tiers with structured summary table reporting:
```powershell
python tests/run_tests.py
```

### Run a Specific Tier
```powershell
python tests/run_tests.py --tier 1    # Run Tier 1 (CLI Arguments)
python tests/run_tests.py --tier 2    # Run Tier 2 (Configuration Loading & Schema)
python tests/run_tests.py --tier 3    # Run Tier 3 (Phase Selection & Filters)
python tests/run_tests.py --tier 4    # Run Tier 4 (Dry-Run Simulation)
python tests/run_tests.py --tier 5    # Run Tier 5 (100% Symmetric Undo)
python tests/run_tests.py --tier 6    # Run Tier 6 (Missing Package Resilience)
python tests/run_tests.py --tier 7    # Run Tier 7 (Mock ADB Harness & State Machine)
```

### Verbose Mode
```powershell
python tests/run_tests.py --verbose
```

### Standard Unittest Runner
```powershell
python -m unittest discover tests -v
```

### Pytest (Optional)
If `pytest` is installed in the Python environment:
```powershell
pytest tests/ -v
```

### Test the Mock ADB Simulator Directly
```powershell
# Query version
python tests/mock_adb.py version

# Query devices in long format
tests\mock_adb.cmd devices -l

# Query simulated device model
tests\mock_adb.cmd shell getprop ro.product.model

# Test missing package exception
tests\mock_adb.cmd shell pm disable-user --user 0 com.oplus.crashbox
```

---

## 4. Test Verification Summary

```text
================================================================================
         ONEPLUS 13R (CPH2691) OPTIMIZER - TEST EXECUTION REPORT
================================================================================
Tier   | Test Suite                             | Tests  | Pass  | Fail  | Status
--------------------------------------------------------------------------------
Tier 1 | Tier 1: CLI Arguments & Help           | 6      | 0     | 6     | [PENDING] Awaiting M1/M2
Tier 2 | Tier 2: Config Loading & Schema        | 9      | 7     | 2     | [PENDING] Awaiting M1/M2
Tier 3 | Tier 3: Phase Selection & Filters      | 6      | 0     | 6     | [PENDING] Awaiting M1/M2
Tier 4 | Tier 4: Dry-Run Simulation             | 5      | 0     | 5     | [PENDING] Awaiting M1/M2
Tier 5 | Tier 5: 100% Symmetric Undo            | 7      | 0     | 7     | [PENDING] Awaiting M1/M2
Tier 6 | Tier 6: Missing Package Resilience     | 3      | 0     | 3     | [PENDING] Awaiting M1/M2
Tier 7 | Tier 7: Mock ADB & Auth State Machine  | 10     | 8     | 2     | [PENDING] Awaiting M1/M2
--------------------------------------------------------------------------------
TOTAL  | All 7 Tiers Combined                   | 46     | 15    | 31    | [WARN] ACTION NEEDED
================================================================================
```

All 15 standalone tests covering the configuration assets (`config.yaml`, `config.json`) and the Mock ADB harness pass cleanly. The 31 remaining tests are rigorously asserting against the CLI contracts of `optimize_13r.py` and will turn green as soon as Milestone M2 (Python Automation CLI) is completed by the implementing agent.

---

## 5. Artifact Manifest

- `tests/__init__.py`: Test package initializer.
- `tests/test_helpers.py`: Shared execution harness, path resolvers, and config loaders.
- `tests/mock_adb.py`: High-fidelity standalone ADB emulator and state machine.
- `tests/mock_adb.cmd`: Windows CMD wrapper for seamless subprocess execution.
- `tests/mock_adb.bat`: Windows BAT wrapper for alternate shell execution.
- `tests/test_cli.py`: Tier 1 test suite.
- `tests/test_config.py`: Tier 2 test suite.
- `tests/test_phases.py`: Tier 3 test suite.
- `tests/test_dry_run.py`: Tier 4 test suite.
- `tests/test_undo_symmetry.py`: Tier 5 test suite.
- `tests/test_missing_packages.py`: Tier 6 test suite.
- `tests/test_mock_adb.py`: Tier 7 test suite.
- `tests/run_tests.py`: Unified master test runner with formatted terminal reporting.
- `TEST_READY.md`: This document.
