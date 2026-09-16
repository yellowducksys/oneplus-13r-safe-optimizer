#!/usr/bin/env python3
"""
Master Test Runner for OnePlus 13R (CPH2691) Safe Optimization Guide.

Executes all 7 test tiers, provides granular filtering, and renders a structured
pass/fail/pending summary report.

Usage:
    python tests/run_tests.py                 # Run full 7-tier test suite
    python tests/run_tests.py --tier 1        # Run only Tier 1 (CLI)
    python tests/run_tests.py --tier 7        # Run only Tier 7 (Mock ADB)
    python tests/run_tests.py --verbose       # Verbose output per test method
"""

import sys
import os
import io
import time
import argparse
import unittest
from pathlib import Path
from typing import Dict, List, Any, Tuple

# Reconfigure stdout/stderr to utf-8 on Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

TIERS = {
    1: ("Tier 1: CLI Arguments & Help", "tests.test_cli"),
    2: ("Tier 2: Config Loading & Schema", "tests.test_config"),
    3: ("Tier 3: Phase Selection & Filters", "tests.test_phases"),
    4: ("Tier 4: Dry-Run Simulation", "tests.test_dry_run"),
    5: ("Tier 5: 100% Symmetric Undo", "tests.test_undo_symmetry"),
    6: ("Tier 6: Missing Package Resilience", "tests.test_missing_packages"),
    7: ("Tier 7: Mock ADB & Auth State Machine", "tests.test_mock_adb"),
}


class TierTestResult:
    def __init__(self, tier_num: int, tier_name: str):
        self.tier_num = tier_num
        self.tier_name = tier_name
        self.total = 0
        self.passed = 0
        self.failed = 0
        self.errors = 0
        self.skipped = 0
        self.duration = 0.0
        self.failure_messages: List[Tuple[str, str]] = []
        self.pending_implementation: bool = False


def run_tier(tier_num: int, module_name: str, verbose: bool = False) -> TierTestResult:
    tier_name = TIERS[tier_num][0]
    result = TierTestResult(tier_num, tier_name)

    loader = unittest.TestLoader()
    try:
        suite = loader.loadTestsFromName(module_name)
    except Exception as e:
        result.errors += 1
        result.failure_messages.append((module_name, f"Module load error: {e}"))
        return result

    result.total = suite.countTestCases()
    if result.total == 0:
        return result

    start_time = time.time()
    stream = sys.stdout if verbose else io.StringIO()
    runner = unittest.TextTestRunner(
        verbosity=2 if verbose else 0,
        stream=stream,
    )
    test_run = runner.run(suite)
    result.duration = time.time() - start_time

    result.passed = test_run.testsRun - len(test_run.failures) - len(test_run.errors) - len(test_run.skipped)
    result.failed = len(test_run.failures)
    result.errors = len(test_run.errors)
    result.skipped = len(test_run.skipped)

    # Check for pending implementation indicators
    all_failures_and_errors = test_run.failures + test_run.errors
    for test_case, trace in all_failures_and_errors:
        result.failure_messages.append((str(test_case), trace))
        if "optimize_13r.py" in trace or "Milestone M" in trace or "not found" in trace.lower():
            result.pending_implementation = True

    return result


def print_summary_table(results: List[TierTestResult]):
    print("\n" + "=" * 80)
    print("         ONEPLUS 13R (CPH2691) OPTIMIZER - TEST EXECUTION REPORT")
    print("=" * 80)
    header = f"{'Tier':<6} | {'Test Suite':<38} | {'Tests':<6} | {'Pass':<5} | {'Fail':<5} | {'Status'}"
    print(header)
    print("-" * 80)

    total_tests = 0
    total_passed = 0
    total_failed = 0
    total_errors = 0
    total_skipped = 0

    all_passed = True

    for r in results:
        total_tests += r.total
        total_passed += r.passed
        total_failed += r.failed + r.errors
        total_skipped += r.skipped

        if r.failed == 0 and r.errors == 0:
            status = "[PASS] OK"
        elif r.pending_implementation:
            status = "[PENDING] Awaiting M1/M2"
            all_passed = False
        else:
            status = "[FAIL] Error"
            all_passed = False

        name_trunc = r.tier_name[:38]
        print(f"Tier {r.tier_num:<1} | {name_trunc:<38} | {r.total:<6} | {r.passed:<5} | {r.failed + r.errors:<5} | {status}")

    print("-" * 80)
    summary_line = f"TOTAL  | {'All 7 Tiers Combined':<38} | {total_tests:<6} | {total_passed:<5} | {total_failed:<5} | "
    summary_line += "[PASS] ALL PASSED" if all_passed else "[WARN] ACTION NEEDED"
    print(summary_line)
    print("=" * 80)

    # Categorize failure messages
    non_pending_failures = []
    pending_failures = []
    for r in results:
        for test_case, trace in r.failure_messages:
            if "optimize_13r.py" in trace or "Milestone M" in trace or "config.yaml" in trace or "config.json" in trace:
                pending_failures.append((r.tier_name, test_case, trace))
            else:
                non_pending_failures.append((r.tier_name, test_case, trace))

    if pending_failures:
        print("\n[PENDING MILESTONE TARGETS]")
        print("   The following tests require Milestone M1 (config) and/or Milestone M2 (script):")
        for tier_name, test_case, trace in pending_failures[:6]:
            first_line = trace.strip().splitlines()[-1] if trace.strip() else ""
            print(f"   * [{tier_name}] {test_case}: {first_line}")
        if len(pending_failures) > 6:
            print(f"   ... and {len(pending_failures) - 6} more pending tests.")

    if non_pending_failures:
        print("\n[FAILURES / REGRESSIONS (Immediate Attention)]")
        for tier_name, test_case, trace in non_pending_failures:
            print(f"\n--- {tier_name}: {test_case} ---")
            print(trace)

    print("\n")
    return all_passed


def main():
    parser = argparse.ArgumentParser(description="OnePlus 13R Optimizer Master Test Runner")
    parser.add_argument("--tier", type=int, choices=range(1, 8), help="Execute a specific tier (1 to 7)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose per-test reporting")
    args = parser.parse_args()

    selected_tiers = [args.tier] if args.tier else sorted(TIERS.keys())

    print(f"[*] Starting test runner for OnePlus 13R (CPH2691) Safe Optimization...")
    print(f"[*] Project root: {PROJECT_ROOT}")
    print(f"[*] Executing tiers: {selected_tiers}\n")

    results = []
    for t in selected_tiers:
        module_name = TIERS[t][1]
        r = run_tier(t, module_name, verbose=args.verbose)
        results.append(r)

    all_passed = print_summary_table(results)
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
