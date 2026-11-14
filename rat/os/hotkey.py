"""
rat.os.hotkey — System-Wide Global Hotkey Listener for macOS.

The default backend is the native Carbon helper (rat/bin/rat-hotkey), which needs no Accessibility
permission. pynput is only a fallback for environments where the helper binary is missing.
"""

from __future__ import annotations

import logging
from pathlib import Path
import sys
import threading
from typing import Callable, List, Optional

from rat.config import config
from rat.os.hotkey_chords import CHORDS, DEFAULT_CHORD
from rat.os.permissions import (
    is_accessibility_trusted, request_accessibility_permission, open_accessibility_settings,
)

logger = logging.getLogger("rat.os.hotkey")

DEFAULT_QUICKLOOK_CHORD = "option_shift_r"

_active_hotkey_manager: Optional[GlobalHotkeyManager] = None


def get_active_hotkey_manager() -> Optional[GlobalHotkeyManager]:
    return _active_hotkey_manager


def restart_global_hotkey() -> bool:
    """Restarts the active global hotkey listener to apply new hotkeys from config."""
    global _active_hotkey_manager
    if _active_hotkey_manager:
        return _active_hotkey_manager.restart()
    return False


def resolve_chord(name: Optional[str], fallback: str) -> str:
    """A supported chord name, or the fallback for anything else (old pynput strings, typos)."""
    name = (name or "").strip()
    if name in CHORDS:
        return name
    if name:
        logger.warning("Unsupported hotkey %r in config; using %s", name, fallback)
    return fallback


def native_helper_available() -> bool:
    if sys.platform != "darwin":
        return False
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
    return (base / "rat/bin/rat-hotkey").is_file()


class GlobalHotkeyManager:
    """Manages system-wide global shortcuts without conflicting with macOS or third-party apps."""

    def __init__(
        self,
        on_trigger: Optional[Callable[[], None]] = None,
        on_quicklook: Optional[Callable[[], None]] = None,
        toggle_chord: Optional[str] = None,
        quicklook_chord: Optional[str] = None,
        backend: Optional[str] = None,
    ) -> None:
        global _active_hotkey_manager
        _active_hotkey_manager = self
        self.on_trigger = on_trigger
        self.on_quicklook = on_quicklook
        self._toggle_override = toggle_chord
        self._quicklook_override = quicklook_chord
        self.toggle_chord = resolve_chord(toggle_chord or config.global_hotkey, DEFAULT_CHORD)
        self.quicklook_chord = resolve_chord(quicklook_chord or config.quicklook_hotkey, DEFAULT_QUICKLOOK_CHORD)
        self.requested_backend = backend
        self.backend: Optional[str] = None
        self._registrations: List = []
        self._listener = None
        self._running = False
        self.status = "stopped"
        self.last_error: Optional[str] = None
        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_monitor_event = threading.Event()

    @property
    def needs_accessibility(self) -> bool:
        """True only when the active or next backend is pynput."""
        backend = self.backend or self.requested_backend
        if backend is None:
            backend = "native" if native_helper_available() else "pynput"
        return backend == "pynput"

    def _start_permission_monitor(self) -> None:
        """Start a background monitor that auto-rebinds hotkeys once Accessibility is granted."""
        if self._monitor_thread and self._monitor_thread.is_alive() and not self._stop_monitor_event.is_set():
            return
        # A stopped monitor keeps its own event while a replacement starts.
        self._stop_monitor_event = threading.Event()
        self._monitor_thread = threading.Thread(
            target=self._monitor_permission_loop,
            args=(self._stop_monitor_event,),
            daemon=True,
            name="rat-hotkey-permission-monitor",
        )
        self._monitor_thread.start()

    def _monitor_permission_loop(self, stop_event) -> None:
        """Polls every 3s to detect when user grants Accessibility permission in System Settings."""
        while not stop_event.wait(3.0):
            if is_accessibility_trusted():
                logger.info("Accessibility permission newly granted! Auto-reconnecting Global Hotkey Manager...")
                self.restart()
                break

    def start(self) -> bool:
        """Start listening for global hotkeys."""
        # Chords come from config again on every start, so restart() applies a changed setting.
        self.toggle_chord = resolve_chord(self._toggle_override or config.global_hotkey, DEFAULT_CHORD)
        self.quicklook_chord = resolve_chord(self._quicklook_override or config.quicklook_hotkey,
                                             DEFAULT_QUICKLOOK_CHORD)
        backend = self.requested_backend or ("native" if native_helper_available() else "pynput")
        self.backend = backend
        if backend == "native":
            return self._start_native()
        return self._start_pynput()

    def _start_native(self) -> bool:
        if not native_helper_available():
            self.status = "unavailable"
            self.last_error = "rat-hotkey helper not found"
            self._running = False
            logger.warning("Native hotkey helper unavailable on this platform or build.")
            return False
        self._close_native()
        try:
            from rat.os.mini_hotkey import HotkeyRegistration
        except Exception as exc:
            self.status = "error"
            self.last_error = f"{type(exc).__name__}: {exc}"
            return False

        wanted = []
        if self.on_trigger:
            wanted.append((self.toggle_chord, self.on_trigger))
        # One helper process holds one chord; a quicklook chord equal to the toggle chord would collide.
        if self.on_quicklook and self.quicklook_chord != self.toggle_chord:
            wanted.append((self.quicklook_chord, self.on_quicklook))

        failures = []
        for chord_name, callback in wanted:
            try:
                self._registrations.append(
                    HotkeyRegistration(callback, on_error=self._native_error, chord_name=chord_name))
            except Exception as exc:
                failures.append(f"{chord_name}: {exc}")
                logger.warning("Native hotkey %s failed: %s", chord_name, exc)
        self._running = bool(self._registrations) and not failures
        if failures:
            self.status = "error"
            self.last_error = "; ".join(failures)
        else:
            self.status = "started"
            self.last_error = None
            logger.info("Global hotkeys registered via native helper: %s",
                        [name for name, _ in wanted])
        return self._running

    def _native_error(self, message: str) -> None:
        self.status = "error"
        self.last_error = message
        self._running = False

    def _close_native(self) -> None:
        for registration in self._registrations:
            try:
                registration.close()
            except Exception as exc:
                logger.warning("Closing native hotkey failed: %s", exc)
        self._registrations = []

    def _start_pynput(self) -> bool:
        """Fallback backend; needs Accessibility."""
        if self._running and is_accessibility_trusted():
            return True

        if not is_accessibility_trusted():
            if self._listener is not None:
                self._listener.stop()
                self._listener = None
            self._running = False
            logger.warning(
                "macOS Accessibility permission not granted! "
                "Global hotkeys require Accessibility in System Settings -> Privacy & Security -> Accessibility."
            )
            outcome = request_accessibility_permission()
            self.status = "permission_error" if outcome.error else "waiting_permission"
            self.last_error = outcome.error
            self._start_permission_monitor()
            # Do not claim a working listener or start an event tap without trust.
            return False
        else:
            self._stop_monitor_event.set()

        try:
            from pynput import keyboard

            def _handle_activate() -> None:
                try:
                    logger.info("Global hotkey triggered!")
                    if self.on_trigger:
                        self.on_trigger()
                except Exception as trigger_err:
                    logger.error(f"Error in global hotkey trigger callback: {trigger_err}", exc_info=True)

            hotkeys = {
                "<cmd>+<shift>+<space>": _handle_activate,
                "<alt>+<shift>+<space>": _handle_activate,
                "<alt>+r": _handle_activate,
            }
            # A pynput-style string saved by an older build is still honoured here.
            primary = (config.global_hotkey or "").strip()
            if "<" in primary and primary not in hotkeys:
                hotkeys[primary] = _handle_activate

            self._listener = keyboard.GlobalHotKeys(hotkeys)
            self._listener.start()
            self._running = True
            self.status = "listener_started"
            self.last_error = None
            logger.info(
                f"Global hotkey listener thread started with shortcuts: {list(hotkeys.keys())} "
                f"(Accessibility trusted: {is_accessibility_trusted()})"
            )
            return True
        except Exception as e:
            if self._listener is not None:
                try:
                    self._listener.stop()
                except Exception:
                    pass
                self._listener = None
            self._running = False
            self.status = "listener_error"
            self.last_error = f"{type(e).__name__}: {e}"
            logger.warning(f"Failed to start GlobalHotKeys listener: {e}")
            self._start_permission_monitor()
            return False

    def stop(self) -> None:
        """Stop listening for global shortcuts."""
        self._stop_monitor_event.set()
        self._close_native()
        if self._listener:
            try:
                self._listener.stop()
            except Exception:
                pass
            self._listener = None
        self._running = False
        self.status = "stopped"
        logger.info("Global Hotkey Manager stopped.")

    def restart(self) -> bool:
        """Restart listener with updated hotkey from config."""
        self.stop()
        return self.start()
