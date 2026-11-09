"""
tests/test_resident_lifecycle.py — Verification of ResidentApplication lifecycle and graceful shutdown.
"""
from __future__ import annotations

import sys
from unittest.mock import MagicMock, Mock, patch

import pytest
from PyQt6.QtCore import QEvent, QObject, QThread
from PyQt6.QtGui import QGuiApplication

from rat.os.app import ResidentApplication


@pytest.fixture(scope="module")
def qapp():
    app = QGuiApplication.instance()
    if app is None:
        app = QGuiApplication([sys.argv[0], "-platform", "offscreen"])
    return app


def test_resident_initial_state(qapp):
    resident = ResidentApplication(mode="daemon")
    assert resident._shutdown_state == "idle"
    assert resident.is_quitting is False
    assert resident.all_workers_finished() is True
    assert resident.get_active_workers() == []


def test_resident_request_quit_clean_shutdown(qapp):
    resident = ResidentApplication(mode="daemon")
    mock_view = Mock()
    mock_ctrl = Mock()
    mock_ctrl.close.return_value = True
    resident.desk_view = mock_view
    resident.desk_controller = mock_ctrl

    callback_results = []
    resident.request_quit(timeout=1.0, on_finished=lambda clean: callback_results.append(clean))

    assert mock_view.hide.called
    assert mock_ctrl.cancel.called
    assert resident._shutdown_state == "terminated"
    assert callback_results == [True]


def test_resident_request_quit_duplicate_call_ignored(qapp):
    resident = ResidentApplication(mode="daemon")
    resident._shutdown_state = "quitting"

    # Should not re-enter or fail
    resident.request_quit()
    assert resident._shutdown_state == "quitting"


def test_resident_event_filter_intercepts_quit(qapp):
    resident = ResidentApplication(mode="daemon")
    resident.request_quit = Mock()

    event = QEvent(QEvent.Type.Quit)
    handled = resident.eventFilter(resident.app, event)

    assert handled is True
    resident.request_quit.assert_called_once()


def test_single_instance_command_routes_to_quit(qapp):
    resident = ResidentApplication(mode="daemon")
    resident.request_quit = Mock()

    resident._on_single_instance_command("quit")
    resident.request_quit.assert_called_once()


def test_get_active_workers_reports_running_threads(qapp):
    resident = ResidentApplication(mode="daemon")

    fake_thread = Mock(spec=QThread)
    fake_thread.isRunning.return_value = True
    resident.warmup_thread = fake_thread

    active = resident.get_active_workers()
    assert "SemesterWarmupWorker" in active
    assert resident.all_workers_finished() is False
