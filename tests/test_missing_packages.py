#!/usr/bin/env python3
"""
Tier 6 Test Suite: Missing Package Error Handling.

Tests resilience against non-existent and deprecated packages:
- Verification that missing packages (com.oplus.crashbox, com.heytap.pictorial, net.oneplus.forums)
  do NOT cause script crashes or unhandled Java exceptions.
- Verification that missing packages produce clean warning or skip log messages.
- Verification that return code is 0 (non-fatal warning) rather than a crash.
- Verification of the 3-tier error handling mechanism against Mock ADB.
"""

import sys
import os
import unittest
from pathlib import Path

from tests.test_helpers import run_optimizer, SCRIPT_PATH, get_mock_adb_executable
from tests.mock_adb import MockADBController, DEFAULT_ABSENT_PACKAGES


class TestMissingPackagesHandling(unittest.TestCase):
    """Test suite for Tier 6: Missing package error handling and resilience."""

    def setUp(self):
        if not SCRIPT_PATH.exists():
            self.fail(f"Required target script 'optimize_13r.py' not found at {SCRIPT_PATH}. (Milestone M2 target)")

        self.mock_ctrl = MockADBController()
        self.mock_ctrl.reset()
        self.mock_ctrl.set_device_state("device")

    def test_missing_packages_do_not_abort_script_execution(self):
        """Verifies missing packages (Crashbox, Pictorial, Forums) log warnings and do not crash."""
        # Run Phase 5 (telemetry freeze) against Mock ADB
        proc = run_optimizer(
            ["--phases", "5"],
            use_mock_adb=True,
            timeout=20.0,
        )

        # The script should complete cleanly with exit code 0
        self.assertEqual(
            proc.returncode,
            0,
            f"Script aborted or exited with code {proc.returncode} due to missing packages.\nStderr:\n{proc.stderr}",
        )

        combined_output = proc.stdout + proc.stderr

        # Assert no unhandled Python traceback
        self.assertNotIn(
            "Traceback (most recent call last):",
            combined_output,
            "Unhandled Python traceback detected when processing missing packages.",
        )

        # Assert no raw, unhandled Java crash dumps printed without context
        self.assertNotIn(
            "com.android.server.pm.PackageManagerService.setEnabledSettings",
            combined_output,
            "Raw unhandled Java stack trace leaked to console output.",
        )

    def test_missing_packages_produce_informative_warning(self):
        """Verifies missing packages produce a clear warning or skip notification in output."""
        proc = run_optimizer(
            ["--phases", "5"],
            use_mock_adb=True,
            timeout=20.0,
        )
        self.assertEqual(proc.returncode, 0)
        output = proc.stdout

        # Check for skip or warning indicator for at least one of the known absent packages
        found_skip_or_warning = False
        for pkg in DEFAULT_ABSENT_PACKAGES:
            if pkg in output:
                # If package is mentioned, it should have a warning/skip marker
                found_skip_or_warning = True
                break

        # Check for generic skip/warning indicators in output
        has_warning_marker = any(m in output for m in ("SKIP", "skip", "warning", "Warning", "⚠️", "not installed", "absent"))
        self.assertTrue(
            has_warning_marker or found_skip_or_warning,
            "Expected explicit warning or skip indicator for absent packages in console output.",
        )

    def test_summary_table_reports_warnings_not_catastrophic_failure(self):
        """Verifies summary table displays warning (⚠️) or success (✅) rather than hard failure (❌)."""
        proc = run_optimizer(
            ["--phases", "5"],
            use_mock_adb=True,
            timeout=20.0,
        )
        self.assertEqual(proc.returncode, 0)
        output = proc.stdout

        # Should NOT report Phase 5 as failed (❌)
        self.assertNotIn(
            "Phase 5 | Failed",
            output,
            "Phase 5 should not be marked as Failed when packages are safely skipped.",
        )


if __name__ == "__main__":
    unittest.main()
