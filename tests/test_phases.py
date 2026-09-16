#!/usr/bin/env python3
"""
Tier 3 Test Suite: Phase Selection and Filtering.

Tests granular phase execution controls:
- Selective execution via --phases (e.g. --phases 1,2,3)
- Phase skipping via --skip (e.g. --skip 5,7)
- Combined filtering (--phases 1,2,3 --skip 2)
- Single phase isolation (--phases 2)
- Edge cases: whitespace in lists, duplicate phase entries, out-of-range phases
"""

import sys
import os
import unittest
from pathlib import Path

from tests.test_helpers import run_optimizer, SCRIPT_PATH


class TestPhaseSelection(unittest.TestCase):
    """Test suite for Tier 3: Phase selection and filtering."""

    def setUp(self):
        if not SCRIPT_PATH.exists():
            self.fail(f"Required target script 'optimize_13r.py' not found at {SCRIPT_PATH}. (Milestone M2 target)")

    def test_single_phase_isolation(self):
        """Verifies --phases 2 executes Phase 2 (Animations) and excludes other phases."""
        proc = run_optimizer(["--dry-run", "--phases", "2"])
        self.assertEqual(proc.returncode, 0)
        output = proc.stdout

        # Phase 2 commands should be present
        self.assertIn("window_animation_scale", output)
        self.assertIn("0.5", output)

        # Other phases must NOT be present
        self.assertNotIn("sm fstrim", output)
        self.assertNotIn("pm trim-caches", output)
        self.assertNotIn("svc nfc", output)
        self.assertNotIn("game_driver_all_apps", output)

    def test_multiple_phases_selection(self):
        """Verifies --phases 1,2 executes only phases 1 and 2."""
        proc = run_optimizer(["--dry-run", "--phases", "1,2"])
        self.assertEqual(proc.returncode, 0)
        output = proc.stdout

        # Phase 1 and 2 must be present
        self.assertTrue("fstrim" in output or "trim-caches" in output)
        self.assertIn("window_animation_scale", output)

        # Other phases must not be present
        self.assertNotIn("deviceidle whitelist", output)
        self.assertNotIn("package compile", output)

    def test_skip_flag_excludes_specified_phases(self):
        """Verifies --skip 5,7 executes all phases EXCEPT phases 5 and 7."""
        proc = run_optimizer(["--dry-run", "--skip", "5,7"])
        self.assertEqual(proc.returncode, 0)
        output = proc.stdout

        # Phase 2 animations should run
        self.assertIn("window_animation_scale", output)

        # Phase 5 (telemetry freeze) must NOT run
        self.assertNotIn("pm disable-user", output)

        # Phase 7 (Wallet/NFC) must NOT run
        self.assertNotIn("quick_access_wallet_enabled", output)

    def test_combined_phases_and_skip(self):
        """Verifies combining --phases 1,2,3 with --skip 2 runs only 1 and 3."""
        proc = run_optimizer(["--dry-run", "--phases", "1,2,3", "--skip", "2"])
        self.assertEqual(proc.returncode, 0)
        output = proc.stdout

        # Phase 1 (storage trim) must run
        self.assertTrue("fstrim" in output or "trim-caches" in output)

        # Phase 2 (animations) was skipped!
        self.assertNotIn("window_animation_scale", output)

        # Phase 3 (battery/radios) must run
        self.assertTrue("wifi_scan_always_enabled" in output or "mobile_data_always_on" in output)

    def test_phases_with_whitespace_and_duplicates(self):
        """Verifies lists with spaces like ' 1, 2 , 1 ' are parsed cleanly without errors."""
        proc = run_optimizer(["--dry-run", "--phases", " 1, 2 , 1 "])
        self.assertEqual(proc.returncode, 0)
        output = proc.stdout
        self.assertIn("window_animation_scale", output)

    def test_invalid_phase_identifier_reports_clean_error(self):
        """Verifies out-of-range or non-numeric phases produce a clear error message."""
        proc = run_optimizer(["--dry-run", "--phases", "999,xyz"])
        # Should exit with non-zero code or cleanly warn
        if proc.returncode != 0:
            self.assertIn(proc.returncode, (1, 2))
        else:
            # If exit 0, it must explicitly warn about invalid phase identifier
            combined = proc.stdout + proc.stderr
            self.assertTrue(
                "invalid" in combined.lower() or "unknown" in combined.lower() or "skip" in combined.lower(),
                "Invalid phase must be warned or rejected.",
            )


if __name__ == "__main__":
    unittest.main()
