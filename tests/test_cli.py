#!/usr/bin/env python3
"""
Tier 1 Test Suite: CLI Arguments and Help Text.

Tests command-line interface behavior for optimize_13r.py:
- --help and -h exit codes and documentation completeness
- --dry-run execution without device
- Invalid flags rejection and standard error messages
- Exit code compliance (0 for success/help/dry-run, 1 for runtime failure, 2 for CLI/config error)
- Non-existent config path error handling
- --no-color output cleanliness
"""

import sys
import os
import unittest
from pathlib import Path

from tests.test_helpers import run_optimizer, SCRIPT_PATH


class TestCLIArguments(unittest.TestCase):
    """Test suite for Tier 1: CLI arguments, flags, and help text."""

    def setUp(self):
        if not SCRIPT_PATH.exists():
            self.fail(f"Required target script 'optimize_13r.py' not found at {SCRIPT_PATH}. (Milestone M2 target)")

    def test_help_flag_returns_exit_zero_and_documents_all_options(self):
        """Verifies --help exits 0 and documents all mandatory CLI flags."""
        proc = run_optimizer(["--help"])
        self.assertEqual(proc.returncode, 0, f"Expected exit code 0 for --help, got {proc.returncode}")

        output = proc.stdout
        # Mandatory flags per PROJECT.md interface contract
        mandatory_flags = [
            "--dry-run",
            "--undo",
            "--phases",
            "--skip",
            "--config",
            "--adb-path",
        ]
        for flag in mandatory_flags:
            self.assertIn(
                flag,
                output,
                f"Mandatory flag '{flag}' must be documented in --help output.\nOutput:\n{output}",
            )

        # Should document target device OnePlus 13R or CPH2691
        self.assertTrue(
            "13R" in output or "CPH2691" in output,
            "Help output should reference OnePlus 13R or CPH2691.",
        )

    def test_short_help_flag_returns_exit_zero(self):
        """Verifies -h exits 0 identically to --help."""
        proc = run_optimizer(["-h"])
        self.assertEqual(proc.returncode, 0, f"Expected exit code 0 for -h, got {proc.returncode}")
        self.assertIn("--dry-run", proc.stdout)

    def test_dry_run_flag_exits_zero_without_device(self):
        """Verifies --dry-run simulates execution and exits 0 even without any device."""
        proc = run_optimizer(["--dry-run"])
        self.assertEqual(
            proc.returncode,
            0,
            f"Expected exit code 0 for --dry-run, got {proc.returncode}.\nStderr: {proc.stderr}",
        )
        # Should indicate simulation or dry run
        combined_output = proc.stdout + proc.stderr
        self.assertTrue(
            "dry" in combined_output.lower() or "simulat" in combined_output.lower() or "preview" in combined_output.lower(),
            "Output of --dry-run should indicate dry-run/simulation mode.",
        )

    def test_invalid_flag_returns_nonzero_exit_code(self):
        """Verifies unrecognized arguments result in exit code 2 (or non-zero)."""
        proc = run_optimizer(["--totally-invalid-flag-xyz"])
        self.assertNotEqual(
            proc.returncode,
            0,
            "Script must exit with non-zero exit code when given invalid flags.",
        )
        # In Python argparse, invalid args produce exit code 2
        self.assertEqual(
            proc.returncode,
            2,
            f"Expected exit code 2 for CLI parse error, got {proc.returncode}",
        )
        err = proc.stderr.lower() + proc.stdout.lower()
        self.assertTrue(
            "unrecognized" in err or "invalid" in err or "error" in err,
            f"Expected error message indicating unrecognized flag.\nOutput: {proc.stderr}",
        )

    def test_nonexistent_config_file_returns_error_exit_code(self):
        """Verifies providing a non-existent configuration file returns exit code 2."""
        proc = run_optimizer(["--config", "nonexistent_config_987654321.json", "--dry-run"])
        self.assertNotEqual(
            proc.returncode,
            0,
            "Script must exit with non-zero code when specified config file does not exist.",
        )
        self.assertIn(
            proc.returncode,
            (1, 2),
            f"Expected exit code 1 or 2 for missing config, got {proc.returncode}",
        )

    def test_no_color_flag_suppresses_ansi_escape_sequences(self):
        """Verifies --no-color flag strips or omits ANSI escape sequences."""
        proc = run_optimizer(["--dry-run", "--no-color"])
        self.assertEqual(proc.returncode, 0)
        output = proc.stdout
        # Check for standard ANSI escape CSI prefix
        self.assertNotIn("\033[", output, "ANSI escape code '\033[' found despite --no-color flag.")
        self.assertNotIn("\x1b[", output, "ANSI escape code '\x1b[' found despite --no-color flag.")


if __name__ == "__main__":
    unittest.main()
