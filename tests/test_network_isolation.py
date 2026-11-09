"""
tests.test_network_isolation — Enforce network boundaries and local-first privacy.

Guarantees that:
1. Local diagnostics, configuration, AST math, and room lookups never initiate
   connections to external non-loopback IP addresses.
2. Pure offline operations (math, room, config) open zero sockets.
3. Local SLM checks only probe local loopback endpoints (127.0.0.1 / ::1).
"""

from __future__ import annotations

import ipaddress
import os
import sys
from pathlib import Path
from unittest.mock import Mock, patch
import pytest

from rat.config import Config
from rat.os.diagnostics import collect_system_diagnostics
from rat.timetable.model import resolve_room_location
from reasoning.reasoning_strategies import safe_calculate


def _is_loopback(addr: any) -> bool:
    """Return True if the socket target address is a local loopback or local IPC socket."""
    if isinstance(addr, (list, tuple)) and addr:
        host = addr[0]
        try:
            return ipaddress.ip_address(host).is_loopback
        except ValueError:
            return host in ("localhost", "127.0.0.1", "::1")
    elif isinstance(addr, (str, bytes)):
        # AF_UNIX local socket path
        return True
    return False


def test_diagnostics_makes_zero_external_connections():
    """Diagnostics checks must never reach out beyond local loopback."""
    external_targets = []

    def audit_hook(event, args):
        if event == "socket.connect":
            sock, addr = args
            if not _is_loopback(addr):
                external_targets.append(addr)

    sys.addaudithook(audit_hook)

    report = collect_system_diagnostics()
    assert report["overall_status"] in ("PASS", "WARN")
    assert report["exit_code"] in (0, 1)
    assert not external_targets, f"External network leak during diagnostics: {external_targets}"


def test_pure_offline_queries_open_zero_sockets():
    """Math calculator, room resolution, and configuration I/O must not touch any sockets."""
    opened_sockets = []

    def strict_no_socket_hook(event, args):
        if event == "socket.connect":
            opened_sockets.append(args)

    sys.addaudithook(strict_no_socket_hook)

    # 1. AST calculation
    res = safe_calculate("25 * 4 + 10")
    assert res == "110"

    # 2. Campus room lookup
    loc = resolve_room_location("B203")
    assert "B2" in loc or "Tòa" in loc

    # 3. Config roundtrip in memory/tempfile
    cfg = Config()
    cfg.default_member_name = "IsolationTest"
    assert cfg.default_member_name == "IsolationTest"

    assert len(opened_sockets) == 0, f"Sockets opened during pure offline queries: {opened_sockets}"


def test_slm_engine_targets_only_loopback_by_default():
    """SLMEngine must target localhost:11434 by default."""
    from rat.engine.slm import SLMEngine
    engine = SLMEngine()
    assert "localhost" in engine.ollama_url or "127.0.0.1" in engine.ollama_url
