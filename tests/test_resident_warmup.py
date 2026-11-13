"""Resident warmup guards; no windows, threads, indexing or model calls."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest


@pytest.mark.parametrize('reason', ['disabled', 'empty', 'quitting', 'running'])
def test_blocked_warmup_does_not_start_worker(monkeypatch, reason):
    from rat.os import app as resident
    from rat.config import config
    from PyQt6 import QtCore

    monkeypatch.setattr(config, 'auto_watch', reason != 'disabled')
    monkeypatch.setattr(config, 'indexed_directories', [] if reason == 'empty' else ['/synthetic/HK242'])
    thread = Mock()
    monkeypatch.setattr(QtCore, 'QThread', thread)
    state = SimpleNamespace(app=SimpleNamespace(_is_quitting=reason == 'quitting'),
                            warmup_thread=Mock(isRunning=lambda: reason == 'running'))
    resident.ResidentApplication._start_semester_warmup(state)
    thread.assert_not_called()


def test_permitted_warmup_starts_one_worker(monkeypatch):
    from rat.os import app as resident
    from rat.crawler import warmup
    from rat.config import config
    from PyQt6 import QtCore

    monkeypatch.setattr(config, 'auto_watch', True)
    monkeypatch.setattr(config, 'indexed_directories', ['/synthetic/HK242'])
    thread = Mock()
    worker = Mock()
    monkeypatch.setattr(QtCore, 'QThread', thread)
    monkeypatch.setattr(warmup, 'SemesterWarmupWorker', worker)
    state = SimpleNamespace(app=SimpleNamespace(_is_quitting=False), warmup_thread=None)
    resident.ResidentApplication._start_semester_warmup(state)
    worker.return_value.moveToThread.assert_called_once_with(thread.return_value)
    thread.return_value.start.assert_called_once()


def _catchup_state(*, quitting=False, running=False):
    tray = Mock()
    return SimpleNamespace(app=SimpleNamespace(_is_quitting=quitting), tray_manager=tray,
                           _index_thread=Mock(isRunning=lambda: running) if running else None,
                           _index_worker=None), tray


@pytest.mark.parametrize('reason', ['empty', 'quitting', 'running'])
def test_blocked_catchup_index_does_not_start_worker(monkeypatch, reason):
    from rat.os import app as resident
    from rat.config import config
    from PyQt6 import QtCore

    monkeypatch.setattr(config, 'indexed_directories', [] if reason == 'empty' else ['/synthetic/HK242'])
    thread = Mock()
    monkeypatch.setattr(QtCore, 'QThread', thread)
    state, _ = _catchup_state(quitting=reason == 'quitting', running=reason == 'running')
    resident.ResidentApplication._start_initial_index(state, announce=False)
    thread.assert_not_called()


@pytest.mark.parametrize('announce', [True, False])
def test_catchup_index_announces_only_when_asked(monkeypatch, announce):
    from rat.os import app as resident
    from rat.config import config
    from PyQt6 import QtCore

    monkeypatch.setattr(config, 'indexed_directories', ['/synthetic/HK242'])
    monkeypatch.setattr(config, 'first_run_completed', True)
    monkeypatch.setattr(QtCore, 'QThread', Mock())
    worker = Mock()
    monkeypatch.setattr(resident, 'InitialIndexWorker', worker)
    state, tray = _catchup_state()
    resident.ResidentApplication._start_initial_index(state, announce=announce)
    on_finished = worker.return_value.finished.connect.call_args[0][0]
    on_finished(3, 120)
    assert tray.tray_icon.showMessage.called is announce


def test_first_catchup_marks_first_run_done(monkeypatch):
    from rat.os import app as resident
    from rat.config import config
    from PyQt6 import QtCore

    monkeypatch.setattr(config, 'indexed_directories', ['/synthetic/HK242'])
    monkeypatch.setattr(config, 'first_run_completed', False)
    save = Mock()
    monkeypatch.setattr(config, 'save', save)
    monkeypatch.setattr(QtCore, 'QThread', Mock())
    worker = Mock()
    monkeypatch.setattr(resident, 'InitialIndexWorker', worker)
    state, _ = _catchup_state()
    resident.ResidentApplication._start_initial_index(state)
    worker.return_value.finished.connect.call_args[0][0](120, 120)
    assert config.first_run_completed is True
    save.assert_called_once()


def test_index_worker_cancel_reaches_indexer():
    from rat.os import app as resident

    worker = resident.InitialIndexWorker()
    worker.cancel()  # before run(): nothing to cancel, must not raise
    worker._indexer = Mock()
    worker.cancel()
    worker._indexer.cancel.assert_called_once()
