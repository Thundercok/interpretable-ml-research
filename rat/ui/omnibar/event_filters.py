"""
rat.ui.omnibar.event_filters — Keyboard event filters for Omnibar inputs and result lists.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from PyQt6.QtCore import QEvent, QObject, Qt
from PyQt6.QtGui import QKeyEvent

if TYPE_CHECKING:
    from .window import OmnibarWindow


def handle_omnibar_escape(window: "OmnibarWindow") -> bool:
    """Standard escape dismissal hierarchy: reader -> collapse detail -> hide omnibar."""
    if getattr(window, "is_reading_reply", False):
        window.set_reply_reader_open(False)
        return True
    if getattr(window, "is_expanded", False):
        window.set_expanded(False)
        return True
    window.hide()
    return True


def handle_item_reveal_or_terminal(window: "OmnibarWindow", is_cmd: bool, is_alt: bool) -> bool:
    """Shared shortcut dispatch for revealing file in Finder or opening in Terminal."""
    if is_cmd:
        window._reveal_current_in_finder()
        return True
    if is_alt:
        window._open_current_in_terminal()
        return True
    return False


class OmnibarInputFilter(QObject):
    """Keyboard-first event filter for Omnibar input."""

    def __init__(self, window: "OmnibarWindow") -> None:
        super().__init__(window)
        self.window = window

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.KeyPress:
            key_event: QKeyEvent = event
            key = key_event.key()
            mod = key_event.modifiers()
            is_cmd = bool(mod & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier))
            is_alt = bool(mod & Qt.KeyboardModifier.AltModifier)

            if watched.property("conversation_navigation"):
                if key == Qt.Key.Key_Escape:
                    if self.window.is_expanded:
                        self.window.set_expanded(False)
                    else:
                        self.window.hide()
                    return True
                if not (is_cmd and key in (Qt.Key.Key_L, Qt.Key.Key_N, Qt.Key.Key_W)):
                    return False  # Native selection, scroll and button activation.

            reader = getattr(self.window, "reply_reader", None)
            if reader and watched in (reader.body, reader.copy_button, reader.close_button):
                if key == Qt.Key.Key_Escape:
                    self.window.set_reply_reader_open(False)
                    return True
                if not (is_cmd and key in (Qt.Key.Key_L, Qt.Key.Key_N, Qt.Key.Key_W)):
                    return False  # Selection, copying and scrolling belong to the reader.

            # Preserve native text-editing shortcuts in the dedicated chat composer.
            if watched is getattr(self.window, "chat_composer_input", None) and is_cmd and key in (
                Qt.Key.Key_A, Qt.Key.Key_C, Qt.Key.Key_V, Qt.Key.Key_X, Qt.Key.Key_Z,
            ):
                return super().eventFilter(watched, event)

            # Chip Button Keyboard Navigation
            chips = getattr(self.window, "chip_buttons", [])
            if chips and watched in chips:
                idx = chips.index(watched)
                if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
                    watched.click()
                    return True
                elif key in (Qt.Key.Key_Right, Qt.Key.Key_Tab):
                    chips[(idx + 1) % len(chips)].setFocus()
                    return True
                elif key in (Qt.Key.Key_Left, Qt.Key.Key_Backtab):
                    if idx > 0:
                        chips[idx - 1].setFocus()
                    else:
                        self.window.chat_composer_input.setFocus()
                    return True
                elif key == Qt.Key.Key_Up:
                    self.window.chat_composer_input.setFocus()
                    return True
                elif key == Qt.Key.Key_Escape:
                    self.window.hide()
                    return True
                elif key_event.text() and not is_cmd:
                    self.window.chat_composer_input.setFocus()
                    self.window.chat_composer_input.setText(key_event.text())
                    return True

            # When typing in chat composer, Down or Tab (if empty) drops focus to suggestion chips
            if watched is getattr(self.window, "chat_composer_input", None):
                composer = self.window.chat_composer_input
                if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and (
                    composer.text().strip() or composer.is_composing or mod & Qt.KeyboardModifier.ShiftModifier
                ):
                    # The editor owns send/newline/IME, not the file-activation shortcuts.
                    return False
                if key in (Qt.Key.Key_Up, Qt.Key.Key_Down, Qt.Key.Key_PageUp, Qt.Key.Key_PageDown) and composer.text():
                    return False
                if key == Qt.Key.Key_Down or (key == Qt.Key.Key_Tab and not composer.text()):
                    results = getattr(self.window, "compact_file_list", None)
                    if results is not None and results.isVisible() and results.count():
                        results.setFocus()
                        if results.currentRow() < 0:
                            results.setCurrentRow(0)
                        return True
                    if getattr(self.window, "quick_suggestions", None) and self.window.quick_suggestions.isVisible() and chips:
                        chips[0].setFocus()
                        return True
                if key in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab):
                    return False  # Normal focus navigation, never a tab inserted into the prompt.

            # 1. Navigation Up/Down
            if key == Qt.Key.Key_Down:
                self.window.navigate_active_list(1)
                return True
            elif key == Qt.Key.Key_Up:
                self.window.navigate_active_list(-1)
                return True
            elif key == Qt.Key.Key_PageDown:
                self.window.navigate_active_list(5)
                return True
            elif key == Qt.Key.Key_PageUp:
                self.window.navigate_active_list(-5)
                return True

            # 2. Enter activation
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if handle_item_reveal_or_terminal(self.window, is_cmd, is_alt):
                    return True
                if self.window.current_section_idx == 0:
                    inp_text = self.window.chat_composer_input.text().strip()
                    if inp_text:
                        self.window._submit_chat_prompt(inp_text)
                    elif self.window.compact_file_list.isVisible() and self.window.compact_file_list.count():
                        self.window._activate_current_item()
                    elif hasattr(self.window, "speech_bubble") and self.window.speech_bubble.isVisible() and self.window.speech_bubble.has_reply:
                        self.window.speech_bubble._on_copy_clicked()
                else:
                    self.window._activate_current_item()
                return True

            # 3. Quick Look (Space or Cmd+Y)
            if (key == Qt.Key.Key_Y and is_cmd) or (key == Qt.Key.Key_Space and self.window._is_list_focused()):
                self.window._preview_quick_look()
                return True

            # 4. Copy Path or Content / Copy Answer
            if key == Qt.Key.Key_C and is_cmd:
                if self.window.compact_file_list.isVisible() and self.window.compact_file_list.hasFocus():
                    self.window._copy_current_path()
                    return True
                if self.window.current_section_idx == 0 and not getattr(self.window.chat_composer_input, "hasSelectedText", lambda: False)():
                    if hasattr(self.window, "speech_bubble") and self.window.speech_bubble.isVisible() and self.window.speech_bubble.has_reply:
                        self.window.speech_bubble._on_copy_clicked()
                        return True
                if mod & Qt.KeyboardModifier.ShiftModifier:
                    self.window._copy_current_content()
                else:
                    self.window._copy_current_path()
                return True

            # 5. Tab / Backtab -> Cycle Sections
            if key == Qt.Key.Key_Tab:
                self.window.cycle_section(1)
                return True
            elif key == Qt.Key.Key_Backtab:
                self.window.cycle_section(-1)
                return True

            # 6. Cmd + 1..4 -> Direct Section Jump
            if is_cmd and Qt.Key.Key_1 <= key <= Qt.Key.Key_4:
                idx = key - Qt.Key.Key_1
                self.window.switch_section(idx)
                return True

            # 7. Cmd + K -> Action Menu
            if key == Qt.Key.Key_K and is_cmd:
                self.window._open_action_menu()
                return True

            # 7b. Cmd + N -> New Chat
            if key == Qt.Key.Key_N and is_cmd:
                self.window.request_reset_chat()
                return True

            # 7c. Cmd + L -> Toggle Detail Notebook
            if key == Qt.Key.Key_L and is_cmd:
                self.window.toggle_expand()
                return True

            # 8. Cmd + W -> Hide Omnibar
            if key == Qt.Key.Key_W and is_cmd:
                self.window.hide()
                return True

            # 9. Escape: If expanded, collapse to compact; else hide Omnibar
            if key == Qt.Key.Key_Escape:
                return handle_omnibar_escape(self.window)

        return super().eventFilter(watched, event)


class OmnibarListFilter(QObject):
    """Event filter on list widgets for quick look and forward typing."""

    def __init__(self, window: "OmnibarWindow") -> None:
        super().__init__(window)
        self.window = window

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.KeyPress:
            key_event: QKeyEvent = event
            key = key_event.key()
            mod = key_event.modifiers()
            is_cmd = bool(mod & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier))
            is_alt = bool(mod & Qt.KeyboardModifier.AltModifier)

            if key == Qt.Key.Key_C and is_cmd:
                self.window._copy_current_path()
                return True

            if key == Qt.Key.Key_Space:
                self.window._preview_quick_look()
                return True

            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if handle_item_reveal_or_terminal(self.window, is_cmd, is_alt):
                    return True
                self.window._activate_current_item()
                return True

            if key == Qt.Key.Key_Escape:
                return handle_omnibar_escape(self.window)

            # Forward printable characters back to active input
            text = key_event.text()
            if text and text.isprintable() and not (is_cmd or is_alt):
                active_inp = (
                    getattr(self.window, "chat_composer_input", None)
                    if self.window.current_section_idx == 0
                    else getattr(self.window, "search_input", None)
                )
                if active_inp:
                    active_inp.setFocus()
                    active_inp.setText(active_inp.text() + text)
                    active_inp.setCursorPosition(len(active_inp.text()))
                return True

        return super().eventFilter(watched, event)
