#!/usr/bin/env python3
"""
Tier 7 Test Suite: Mock ADB Harness and State Machine.

Tests the mock ADB harness itself and ADB integration features:
- Mock ADB CLI commands (version, start-server, kill-server)
- Device status reporting and long-format parsing
- Progressive authorization handshake simulation ('authorizing' -> 'device')
- Hardware property retrieval (CPH2691 / CPH2691IN / Android 16)
- Package manager inspection (pm list packages, missing package exception simulation)
- Optimizer integration: upfront persistent server start, retry on 'authorizing', model verification
"""

import sys
import os
import subprocess
import unittest
from pathlib import Path

from tests.test_helpers import (
    run_optimizer,
    SCRIPT_PATH,
    get_mock_adb_executable,
    MOCK_ADB_PY,
)
from tests.mock_adb import (
    MockADBController,
    MockADBState,
    handle_adb_command,
    DEFAULT_INSTALLED_PACKAGES,
    DEFAULT_ABSENT_PACKAGES,
)


class TestMockADBHarness(unittest.TestCase):
    """Unit tests for Mock ADB simulator and state machine."""

    def setUp(self):
        self.ctrl = MockADBController()
        self.ctrl.reset()

    def test_mock_adb_version_output(self):
        """Verifies mock_adb version command reports standard Android Debug Bridge headers."""
        adb_exec = get_mock_adb_executable()
        res = subprocess.run([adb_exec, "version"], capture_output=True, text=True, timeout=5)
        self.assertEqual(res.returncode, 0)
        self.assertIn("Android Debug Bridge version", res.stdout)
        self.assertIn("36.0.1", res.stdout)

    def test_mock_adb_start_server_lifecycle(self):
        """Verifies start-server marks server as running."""
        adb_exec = get_mock_adb_executable()
        res = subprocess.run([adb_exec, "start-server"], capture_output=True, text=True, timeout=5)
        self.assertEqual(res.returncode, 0)
        self.assertTrue(self.ctrl.is_server_running())

    def test_mock_adb_devices_listing(self):
        """Verifies devices -l returns expected device format for OnePlus 13R."""
        adb_exec = get_mock_adb_executable()
        res = subprocess.run([adb_exec, "devices", "-l"], capture_output=True, text=True, timeout=5)
        self.assertEqual(res.returncode, 0)
        self.assertIn("device", res.stdout)
        self.assertIn("CPH2691", res.stdout)
        self.assertIn("OP5D3BL1", res.stdout)

    def test_mock_adb_authorizing_to_device_transition(self):
        """Verifies state machine transitions from 'authorizing' to 'device' after N checks."""
        self.ctrl.configure_auth_transition(authorizing_steps=2)

        adb_exec = get_mock_adb_executable()

        # Step 1: should be authorizing
        res1 = subprocess.run([adb_exec, "devices"], capture_output=True, text=True, timeout=5)
        self.assertIn("authorizing", res1.stdout)

        # Step 2: should still be authorizing
        res2 = subprocess.run([adb_exec, "devices"], capture_output=True, text=True, timeout=5)
        self.assertIn("authorizing", res2.stdout)

        # Step 3: should transition to device
        res3 = subprocess.run([adb_exec, "devices"], capture_output=True, text=True, timeout=5)
        self.assertIn("device", res3.stdout)
        self.assertNotIn("authorizing", res3.stdout)

    def test_mock_adb_getprop_ro_product_model(self):
        """Verifies getprop ro.product.model returns CPH2691."""
        adb_exec = get_mock_adb_executable()
        res = subprocess.run(
            [adb_exec, "shell", "getprop", "ro.product.model"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        self.assertEqual(res.returncode, 0)
        self.assertEqual(res.stdout.strip(), "CPH2691")

    def test_mock_adb_pm_list_packages_accuracy(self):
        """Verifies pm list packages -u contains installed packages and omits absent ones."""
        adb_exec = get_mock_adb_executable()
        res = subprocess.run(
            [adb_exec, "shell", "pm", "list", "packages", "-u"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        self.assertEqual(res.returncode, 0)
        output = res.stdout

        # Verify installed packages are present
        self.assertIn("package:com.oplus.postmanservice", output)
        self.assertIn("package:com.oplus.camera", output)

        # Verify absent packages are NOT present
        for absent in DEFAULT_ABSENT_PACKAGES:
            self.assertNotIn(f"package:{absent}", output, f"Absent package {absent} should not be in package list.")

    def test_mock_adb_missing_package_throws_java_exception(self):
        """Verifies pm disable-user on a missing package returns exit code 1 with Java stack trace."""
        adb_exec = get_mock_adb_executable()
        res = subprocess.run(
            [adb_exec, "shell", "pm", "disable-user", "--user", "0", "com.oplus.crashbox"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        self.assertEqual(res.returncode, 1)
        self.assertIn("java.lang.IllegalArgumentException: Unknown package: com.oplus.crashbox", res.stderr)

    def test_mock_adb_settings_put_and_get(self):
        """Verifies settings put and get work for global namespace."""
        adb_exec = get_mock_adb_executable()
        put_res = subprocess.run(
            [adb_exec, "shell", "settings", "put", "global", "test_key", "test_val"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        self.assertEqual(put_res.returncode, 0)

        get_res = subprocess.run(
            [adb_exec, "shell", "settings", "get", "global", "test_key"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        self.assertEqual(get_res.returncode, 0)
        self.assertEqual(get_res.stdout.strip(), "test_val")


class TestOptimizerADBIntegration(unittest.TestCase):
    """Integration tests between optimize_13r.py and ADB harness."""

    def setUp(self):
        if not SCRIPT_PATH.exists():
            self.fail(f"Required target script 'optimize_13r.py' not found at {SCRIPT_PATH}. (Milestone M2 target)")

        self.ctrl = MockADBController()
        self.ctrl.reset()

    def test_optimizer_honors_custom_adb_path(self):
        """Verifies optimize_13r.py uses the path specified by --adb-path."""
        adb_exec = get_mock_adb_executable()
        proc = run_optimizer(["--adb-path", adb_exec, "--phases", "2"], timeout=15.0)
        self.assertEqual(proc.returncode, 0, f"Failed with custom adb path.\nStderr: {proc.stderr}")

        # Check mock history to verify the mock ADB binary was actually called
        history = self.ctrl.get_command_history()
        self.assertTrue(len(history) > 0, "No commands were logged by mock ADB.")

    def test_optimizer_authorizing_retry_handshake(self):
        """Verifies optimize_13r.py polls through 'authorizing' state until 'device' is reached."""
        # Require 2 checks in 'authorizing' before becoming 'device'
        self.ctrl.configure_auth_transition(authorizing_steps=2)

        proc = run_optimizer(
            ["--phases", "2"],
            use_mock_adb=True,
            timeout=25.0,
        )
        self.assertEqual(
            proc.returncode,
            0,
            f"Optimizer failed to negotiate authorization handshake retry.\nStderr: {proc.stderr}",
        )


if __name__ == "__main__":
    unittest.main()
