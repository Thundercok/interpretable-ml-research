"""
Tests for rat.app.router mode routing and delegation.
"""

from __future__ import annotations

import sys
from unittest.mock import Mock, patch
import pytest

from rat.app.router import route_request, run_resident_app, cli_main


def test_router_diagnostics_dispatch(monkeypatch):
    mock_run_session = Mock(return_value=0)
    monkeypatch.setattr("rat.os.diagnostics.run_session", mock_run_session)

    with pytest.raises(SystemExit) as exc:
        route_request(["--diagnostics", "--json"])
    assert exc.value.code == 0
    mock_run_session.assert_called_once_with(["--json"])


def test_router_cli_subcommands(monkeypatch):
    for subcmd in ("search", "index", "status", "ask", "doctor", "--help"):
        mock_cli = Mock()
        monkeypatch.setattr("rat.app.router.cli_main", mock_cli)
        route_request([subcmd])
        mock_cli.assert_called_once()


def test_router_resident_modes(monkeypatch):
    cases = [
        (["--daemon"], "daemon"),
        (["-d"], "daemon"),
        (["spotlight"], "spotlight"),
        (["widgets"], "spotlight"),
        (["widget"], "widget"),
        (["mini"], "widget"),
        (["schedule"], "schedule"),
        (["finder"], "finder"),
        (["--mode=daemon"], "daemon"),
        (["--mode", "widget"], "widget"),
    ]
    for args, expected_mode in cases:
        mock_resident = Mock()
        monkeypatch.setattr("rat.app.router.run_resident_app", mock_resident)
        route_request(args)
        mock_resident.assert_called_once_with(mode=expected_mode)


def test_router_pdf_dispatch(monkeypatch):
    mock_quick = Mock(return_value=0)
    monkeypatch.setattr("rat.ui.quick_app.main", mock_quick)

    with pytest.raises(SystemExit):
        route_request(["quick-pdf", "report.pdf"])
    mock_quick.assert_called_once_with(["report.pdf"])

    mock_quick.reset_mock()
    with pytest.raises(SystemExit):
        route_request(["report.pdf"])
    mock_quick.assert_called_once_with(["report.pdf"])


def test_router_single_action_math(capsys):
    route_request(["tính", "12", "*", "12"])
    captured = capsys.readouterr()
    assert "144" in captured.out


def test_router_single_action_room(capsys):
    route_request(["B203"])
    captured = capsys.readouterr()
    assert "Phòng B203" in captured.out


def test_router_default_launches_quick_desk(monkeypatch):
    mock_quick = Mock(return_value=0)
    monkeypatch.setattr("rat.ui.quick_app.main", mock_quick)

    with pytest.raises(SystemExit):
        route_request([])
    mock_quick.assert_called_once_with([])
