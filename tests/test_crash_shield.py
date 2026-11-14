"""
tests/test_crash_shield.py — Enterprise Crash Shield & Lifecycle Hardening Tests.
Validates sys.excepthook, safe_slot, and the tray rescan worker shutdown.
"""

import os
import sys
import threading
import unittest
from unittest.mock import MagicMock, patch

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtGui import QGuiApplication

app = QGuiApplication.instance()
if app is None:
    app = QGuiApplication(sys.argv)

from rat.os.crash_shield import (
    CRASH_LOG_FILE,
    global_excepthook,
    install_crash_shield,
    safe_slot,
    thread_excepthook,
)


class TestCrashShield(unittest.TestCase):
    """Test suite for crash prevention, exception shielding, and thread shutdown safety."""

    def setUp(self):
        install_crash_shield()

    def test_crash_shield_installation(self):
        """Verify that install_crash_shield sets sys.excepthook and threading.excepthook."""
        self.assertEqual(sys.excepthook, global_excepthook)
        if hasattr(threading, "excepthook"):
            self.assertEqual(threading.excepthook, thread_excepthook)

    def test_safe_slot_catches_exception(self):
        """Verify that @safe_slot absorbs exceptions and returns None instead of crashing."""
        @safe_slot
        def buggy_slot():
            raise ValueError("Simulated slot crash error")

        result = buggy_slot()
        self.assertIsNone(result)

    def test_global_excepthook_keeps_qt_alive_and_logs(self):
        """Verify global_excepthook logs to crash.log without terminating Qt process."""
        try:
            raise RuntimeError("Diagnostic crash test for CrashShield")
        except RuntimeError:
            exc_type, exc_val, exc_tb = sys.exc_info()
            global_excepthook(exc_type, exc_val, exc_tb)

        self.assertTrue(CRASH_LOG_FILE.exists())
        with open(CRASH_LOG_FILE, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("Diagnostic crash test for CrashShield", content)
        self.assertIn("RuntimeError", content)

    def test_system_tray_manager_shutdown(self):
        """Verify SystemTrayManager.shutdown safely terminates any active rescan worker."""
        from rat.os.menu_bar import RescanWorker, SystemTrayManager
        with patch("rat.os.menu_bar.Database") as mock_db:
            mock_db_inst = MagicMock()
            mock_db_inst.get_stats.return_value = {"total_files": 10, "total_size_bytes": 1024}
            mock_db.return_value = mock_db_inst

            tray = SystemTrayManager()
            # Shutdown when worker is None shouldn't crash
            tray.shutdown()
            self.assertIsNone(tray.rescan_worker)

            # Simulate worker
            worker = RescanWorker(mock_db_inst)
            self.assertIsNone(worker.parent())
            tray.rescan_worker = worker
            tray.shutdown()
            self.assertIsNone(tray.rescan_worker)

if __name__ == "__main__":
    unittest.main()
