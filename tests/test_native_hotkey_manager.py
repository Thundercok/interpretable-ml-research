"""The resident app registers hotkeys through the native helper; no Accessibility prompt on that path."""
from unittest.mock import Mock

import pytest

from rat.config import Config
from rat.os import hotkey


@pytest.fixture
def registrations(monkeypatch):
    """Replace the real helper process with a recorder."""
    created = []

    class FakeRegistration:
        def __init__(self, callback, on_error=None, chord_name=None, **kwargs):
            self.callback, self.on_error, self.chord_name = callback, on_error, chord_name
            self.close = Mock()
            created.append(self)

    monkeypatch.setattr(hotkey, 'native_helper_available', lambda: True)
    monkeypatch.setattr('rat.os.mini_hotkey.HotkeyRegistration', FakeRegistration)
    monkeypatch.setattr(hotkey, 'is_accessibility_trusted', Mock(side_effect=AssertionError('prompted')))
    monkeypatch.setattr(hotkey, 'request_accessibility_permission', Mock(side_effect=AssertionError('prompted')))
    return created


def test_native_backend_registers_both_chords_without_accessibility(registrations):
    toggle, quicklook = Mock(), Mock()
    manager = hotkey.GlobalHotkeyManager(toggle, quicklook, 'option_shift_space', 'option_shift_r')
    assert manager.start() is True
    assert manager.backend == 'native' and manager.status == 'started'
    assert [r.chord_name for r in registrations] == ['option_shift_space', 'option_shift_r']
    assert not manager.needs_accessibility
    registrations[0].callback()
    toggle.assert_called_once()


def test_equal_chords_register_once(registrations):
    manager = hotkey.GlobalHotkeyManager(Mock(), Mock(), 'option_shift_r', 'option_shift_r')
    assert manager.start()
    assert [r.chord_name for r in registrations] == ['option_shift_r']


def test_stop_closes_every_registration(registrations):
    manager = hotkey.GlobalHotkeyManager(Mock(), Mock(), 'option_shift_space', 'option_shift_r')
    manager.start()
    manager.stop()
    assert all(r.close.called for r in registrations)
    assert manager.status == 'stopped' and not manager._running


def test_restart_does_not_leave_a_second_registration_alive(registrations):
    manager = hotkey.GlobalHotkeyManager(Mock(), None, 'option_shift_space')
    manager.start()
    first = registrations[0]
    assert manager.restart()
    first.close.assert_called_once()
    assert len(registrations) == 2


def test_helper_failure_is_reported_not_swallowed(monkeypatch):
    monkeypatch.setattr(hotkey, 'native_helper_available', lambda: True)

    def boom(*args, **kwargs):
        raise OSError('helper did not report READY')

    monkeypatch.setattr('rat.os.mini_hotkey.HotkeyRegistration', boom)
    manager = hotkey.GlobalHotkeyManager(Mock(), None, 'option_shift_space')
    assert manager.start() is False
    assert manager.status == 'error' and 'READY' in manager.last_error


def test_runtime_helper_error_marks_manager_stopped(registrations):
    manager = hotkey.GlobalHotkeyManager(Mock(), None, 'option_shift_space')
    manager.start()
    registrations[0].on_error('helper exited')
    assert manager.status == 'error' and not manager._running and manager.last_error == 'helper exited'


def test_missing_helper_falls_back_to_pynput_which_needs_accessibility(monkeypatch):
    monkeypatch.setattr(hotkey, 'native_helper_available', lambda: False)
    manager = hotkey.GlobalHotkeyManager(Mock())
    assert manager.needs_accessibility


def test_unsupported_saved_chord_falls_back_to_default():
    assert hotkey.resolve_chord('<cmd>+<shift>+<space>', 'option_shift_space') == 'option_shift_space'
    assert hotkey.resolve_chord('control_option_space', 'option_shift_space') == 'control_option_space'
    assert hotkey.resolve_chord(None, 'option_shift_r') == 'option_shift_r'


def test_config_defaults_match_the_plan_and_display_symbols(monkeypatch, tmp_path):
    monkeypatch.delenv('RAT_HOTKEY', raising=False)
    monkeypatch.delenv('RAT_QUICKLOOK_HOTKEY', raising=False)
    monkeypatch.setattr('rat.config.CONFIG_FILE', tmp_path / 'missing.json')
    cfg = Config()
    assert cfg.global_hotkey == 'option_shift_space'
    assert cfg.get_hotkey_display() == '⌥⇧Space'
    assert cfg.get_hotkey_display(cfg.quicklook_hotkey) == '⌥⇧R'
    assert cfg.get_hotkey_display('<cmd>+<shift>+<space>') == '⌘ + ⇧ + Space'


def test_checked_in_helper_matches_the_current_build_id():
    """A stale binary announces an older build, never matches the READY line, and silently kills every hotkey."""
    import sys
    from pathlib import Path
    from rat.engine.mini_version import BUILD
    helper = Path(__file__).resolve().parents[1] / 'rat/bin/rat-hotkey'
    if sys.platform != 'darwin' or not helper.is_file():
        pytest.skip('native helper is macOS only')
    assert BUILD.encode() in helper.read_bytes(), 'rebuild with: zsh tools/build_rat_mini_hotkey.sh'
