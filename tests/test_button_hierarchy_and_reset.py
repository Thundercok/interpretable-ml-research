"""Regression tests for Priority 2: Button Hierarchy, Expand/Collapse, and Reset Confirmation.

Covers:
- Button sizing (36x36 for expand and send, >=28px for actions)
- Dynamic tooltip and accessibleName for expand/collapse across Quick, Reader, and Full modes
- Esc hierarchical collapse (Reader -> Quick, Full -> Quick, Quick -> Hide)
- Reset confirmation dialog (confirm when history/draft present, instant reset when empty)
- ⌘N and /clear triggering confirmation
- Ribbon reset button wiring and accessible metadata
"""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QDialog, QPushButton

from rat.ui.omnibar import OmnibarWindow, ResetConfirmationDialog

app = QApplication.instance() or QApplication(sys.argv)


class TestButtonHierarchyAndReset(unittest.TestCase):
    def setUp(self):
        with patch("rat.ui.omnibar.Database") as mock_db, \
             patch("rat.ui.omnibar.SearchEngine") as mock_engine, \
             patch("rat.ui.feedback.FeedbackLog"):
            mock_db_inst = MagicMock()
            mock_db_inst.get_stats.return_value = {"total_files": 10}
            mock_db_inst.get_recent_documents.return_value = []
            mock_db.return_value = mock_db_inst

            mock_eng_inst = MagicMock()
            mock_eng_inst.search.return_value = {"results": [], "latency_ms": 5, "reasoning_trace": None, "plan": None}
            mock_engine.return_value = mock_eng_inst

            self.window = OmnibarWindow()
            try:
                self.window.worker.search_completed.disconnect(self.window._on_search_completed)
            except Exception:
                pass

    def tearDown(self):
        if hasattr(self, "window") and self.window is not None:
            self.window.shutdown()
            self.window.close()
            self.window.deleteLater()
            app.processEvents()

    def test_composer_buttons_geometry_and_accessibility(self):
        """Send and Expand buttons must have 36x36 footprint and proper accessible names."""
        self.window.show()
        btn_expand = self.window.btn_expand
        btn_send = self.window.chat_composer_send

        self.assertEqual(btn_expand.width(), 36)
        self.assertEqual(btn_expand.height(), 36)
        self.assertEqual(btn_expand.accessibleName(), "Mở hội thoại")

        self.assertEqual(btn_send.width(), 36)
        self.assertEqual(btn_send.height(), 36)
        self.assertEqual(btn_send.accessibleName(), "Gửi câu hỏi")
        self.assertFalse(btn_send.isEnabled())

        # Typing in composer enables send
        self.window.chat_composer_input.setText("Hỏi nhanh")
        self.assertTrue(btn_send.isEnabled())

    def test_dynamic_expand_tooltips_across_modes(self):
        """Expand button changes icon, tooltip, and accessible name between Quick, Reader, and Full."""
        self.window.show()
        btn = self.window.btn_expand

        # 1. Quick mode
        self.assertFalse(self.window.is_expanded)
        self.assertFalse(self.window.is_reading_reply)
        self.assertEqual(btn.text(), "⤢")
        self.assertIn("Mở hội thoại · ⌘L", btn.toolTip())
        self.assertEqual(btn.accessibleName(), "Mở hội thoại")

        # 2. Reader mode
        self.window.reply_reader.set_reply("Câu trả lời rất dài...")
        self.window.set_reply_reader_open(True)
        self.assertTrue(self.window.is_reading_reply)
        self.assertEqual(btn.text(), "⤢")
        self.assertIn("Mở toàn bộ hội thoại · ⌘L", btn.toolTip())
        self.assertEqual(btn.accessibleName(), "Mở toàn bộ hội thoại")

        # 3. Full mode
        self.window.set_expanded(True)
        self.assertTrue(self.window.is_expanded)
        self.assertFalse(self.window.is_reading_reply)
        self.assertEqual(btn.text(), "⤡")
        self.assertIn("Thu gọn hội thoại · ⌘L", btn.toolTip())
        self.assertEqual(btn.accessibleName(), "Thu gọn hội thoại")

        # 4. Collapse back to Quick mode
        self.window.set_expanded(False)
        self.assertFalse(self.window.is_expanded)
        self.assertEqual(btn.text(), "⤢")
        self.assertIn("Mở hội thoại · ⌘L", btn.toolTip())

    def test_esc_hierarchical_dismissal(self):
        """Esc dismisses Reader -> Quick, Full -> Quick, Quick -> Hide."""
        self.window.show()
        self.assertFalse(self.window.isHidden())

        # 1. Reader -> Quick
        self.window.reply_reader.set_reply("Câu trả lời dài...")
        self.window.set_reply_reader_open(True)
        self.assertTrue(self.window.is_reading_reply)
        self.window.input_filter.eventFilter(
            self.window,
            MagicMock(type=lambda: 6, key=lambda: Qt.Key.Key_Escape, modifiers=lambda: Qt.KeyboardModifier.NoModifier)
        )
        self.assertFalse(self.window.is_reading_reply)
        self.assertFalse(self.window.isHidden())

        # 2. Full -> Quick
        self.window.set_expanded(True)
        self.assertTrue(self.window.is_expanded)
        self.window.input_filter.eventFilter(
            self.window,
            MagicMock(type=lambda: 6, key=lambda: Qt.Key.Key_Escape, modifiers=lambda: Qt.KeyboardModifier.NoModifier)
        )
        self.assertFalse(self.window.is_expanded)
        self.assertFalse(self.window.isHidden())

        # 3. Quick -> Hide
        self.window.input_filter.eventFilter(
            self.window,
            MagicMock(type=lambda: 6, key=lambda: Qt.Key.Key_Escape, modifiers=lambda: Qt.KeyboardModifier.NoModifier)
        )
        self.assertTrue(self.window.isHidden())

    def test_reset_confirmation_when_conversation_has_history(self):
        """When history exists, request_reset_chat prompts confirmation. Canceling retains history."""
        self.window.show()
        self.window._conversation.add_turn("Chào chuột", "Chào bạn")
        self.assertEqual(len(self.window._conversation._turns), 1)

        # Mock ResetConfirmationDialog.exec to simulate User pressing Esc / Cancel (Rejected)
        with patch.object(ResetConfirmationDialog, "exec", return_value=QDialog.DialogCode.Rejected) as mock_exec:
            self.window.request_reset_chat()
            self.assertTrue(mock_exec.called)
            # History retained
            self.assertEqual(len(self.window._conversation._turns), 1)

        # Mock ResetConfirmationDialog.exec to simulate User confirming (Accepted)
        with patch.object(ResetConfirmationDialog, "exec", return_value=QDialog.DialogCode.Accepted) as mock_exec:
            self.window.request_reset_chat()
            self.assertTrue(mock_exec.called)
            # History cleared
            self.assertEqual(len(self.window._conversation._turns), 0)

    def test_reset_confirmation_when_composer_has_draft(self):
        """When composer has unsubmitted draft, request_reset_chat prompts confirmation."""
        self.window.show()
        self.window.chat_composer_input.setText("Bản nháp quan trọng")
        self.assertEqual(len(self.window._conversation._turns), 0)

        with patch.object(ResetConfirmationDialog, "exec", return_value=QDialog.DialogCode.Rejected) as mock_exec:
            self.window.request_reset_chat()
            self.assertTrue(mock_exec.called)
            self.assertEqual(self.window.chat_composer_input.text(), "Bản nháp quan trọng")

        with patch.object(ResetConfirmationDialog, "exec", return_value=QDialog.DialogCode.Accepted) as mock_exec:
            self.window.request_reset_chat()
            self.assertTrue(mock_exec.called)
            self.assertEqual(self.window.chat_composer_input.text(), "")

    def test_reset_instant_when_empty_session(self):
        """When session is empty and draft is empty, reset executes instantly without modal."""
        self.window.show()
        self.assertEqual(len(self.window._conversation._turns), 0)
        self.assertEqual(self.window.chat_composer_input.text(), "")

        with patch.object(ResetConfirmationDialog, "exec") as mock_exec:
            self.window.request_reset_chat()
            self.assertFalse(mock_exec.called)

    def test_ribbon_reset_button_and_shortcuts(self):
        """Ribbon clear button and Cmd+N shortcut invoke request_reset_chat."""
        self.window.show()
        ribbon_btn = self.window.conversation_ribbon.clear_btn
        self.assertIn("⌘N hoặc /clear", ribbon_btn.toolTip())
        self.assertEqual(ribbon_btn.accessibleName(), "Xoá phiên cuộc trò chuyện")

        with patch.object(self.window, "request_reset_chat") as mock_reset:
            ribbon_btn.click()
            self.assertTrue(mock_reset.called)

        # ⌘N shortcut
        with patch.object(self.window, "request_reset_chat") as mock_reset:
            self.window.input_filter.eventFilter(
                self.window,
                MagicMock(type=lambda: 6, key=lambda: Qt.Key.Key_N, modifiers=lambda: Qt.KeyboardModifier.ControlModifier)
            )
            self.assertTrue(mock_reset.called)

        # Slash command /clear
        with patch.object(self.window, "request_reset_chat") as mock_reset:
            self.window._submit_chat_prompt("/clear")
            self.assertTrue(mock_reset.called)

    def test_footer_has_no_duplicate_reset_action(self):
        self.window.show()
        self.window.set_expanded(True)
        QTest.qWait(200)
        buttons = self.window.compact_footer.findChildren(QPushButton)
        self.assertNotIn("Chat mới", [button.text() for button in buttons])
        self.assertFalse(hasattr(self.window, "compact_new_chat"))
        self.assertTrue(self.window.conversation_ribbon.clear_btn.isVisible())
        with patch.object(self.window, "request_reset_chat") as request:
            self.window.btn_new_chat.click()
            request.assert_called_once_with()

    def test_first_pending_turn_cancel_keeps_request_and_partial_reply(self):
        self.window.show()
        with patch("rat.ui.omnibar.StreamReasoningWorker") as worker:
            self.window._submit_chat_prompt("Một câu hỏi đang chờ")
            handle = self.window._current_stream_handle
            self.window._on_reasoning_token(handle, "Một phần đáp án đang viết")
            session = self.window._conversation.session_id
            generation = self.window._chat_generation
            self.assertEqual(self.window._conversation.messages(), [])
            self.assertEqual(self.window.chat_composer_input.text(), "")
            with patch.object(ResetConfirmationDialog, "exec", return_value=QDialog.DialogCode.Rejected) as confirm:
                self.window.request_reset_chat()
                confirm.assert_called_once_with()
            self.assertEqual(self.window._conversation.session_id, session)
            self.assertEqual(self.window._chat_generation, generation)
            self.assertEqual(self.window._pending_chat_query, "Một câu hỏi đang chờ")
            self.assertEqual(handle["full_text"], "Một phần đáp án đang viết")
            self.assertFalse(self.window.chat_stream.is_empty())
            worker.return_value.requestInterruption.assert_not_called()

    def test_first_failed_turn_cancel_preserves_content_without_completed_history(self):
        for strategy in ("AI chưa sẵn sàng", "Phản hồi bị ngắt"):
            with self.subTest(strategy=strategy):
                self.window._reset_chat()
                with patch("rat.ui.omnibar.StreamReasoningWorker"):
                    self.window._submit_chat_prompt("Một câu hỏi chưa hoàn tất")
                    handle = self.window._current_stream_handle
                    self.window._on_reasoning_finished(handle, "Nội dung cần giữ", [], 5, strategy, "mẫu")
                session = self.window._conversation.session_id
                self.assertEqual(self.window._conversation.messages(), [])
                self.assertIsNone(self.window._pending_chat_query)
                with patch.object(ResetConfirmationDialog, "exec", return_value=QDialog.DialogCode.Rejected) as confirm:
                    self.window.request_reset_chat()
                    confirm.assert_called_once_with()
                self.assertEqual(self.window._conversation.session_id, session)
                self.assertEqual(handle["full_text"], "Nội dung cần giữ")
                self.assertFalse(self.window.chat_stream.is_empty())

    def test_confirmed_pending_reset_invalidates_old_callbacks_once(self):
        with patch("rat.ui.omnibar.StreamReasoningWorker") as worker:
            self.window._submit_chat_prompt("Một câu hỏi đang chờ")
            handle = self.window._current_stream_handle
            generation = self.window._chat_generation
            with patch.object(ResetConfirmationDialog, "exec", return_value=QDialog.DialogCode.Accepted) as confirm:
                self.window.request_reset_chat()
                confirm.assert_called_once_with()
            self.assertEqual(self.window._chat_generation, generation + 1)
            worker.return_value.requestInterruption.assert_called_once_with()
            self.window._on_reasoning_token(handle, "Token cũ")
            self.window._on_reasoning_finished(handle, "Đáp án cũ", [], 5, "AI cục bộ", "mẫu")
            self.assertTrue(self.window.chat_stream.is_empty())
            self.assertIsNone(self.window._pending_chat_query)
            self.assertEqual(self.window._presentation_state.phase, "idle")

    def test_confirmation_keeps_parent_open_and_avoids_nested_reset(self):
        self.window.show()
        self.window.chat_composer_input.setText("Bản nháp cần giữ")

        def reject_while_active():
            self.assertTrue(self.window._dialog_active)
            self.window._was_activated = True
            self.window._is_opening = False
            with patch.object(self.window, "isActiveWindow", return_value=False):
                self.window.changeEvent(QEvent(QEvent.Type.ActivationChange))
            self.assertFalse(self.window.isHidden())
            self.window.request_reset_chat()
            return QDialog.DialogCode.Rejected

        with patch.object(ResetConfirmationDialog, "exec", side_effect=reject_while_active) as confirm:
            self.window.request_reset_chat()
            confirm.assert_called_once()
        self.assertFalse(self.window._dialog_active)
        self.assertEqual(self.window.chat_composer_input.text(), "Bản nháp cần giữ")

    def test_reset_dialog_keyboard_defaults_to_keep_and_allows_explicit_clear(self):
        for action in ("return", "escape", "clear"):
            with self.subTest(action=action):
                dialog = ResetConfirmationDialog(self.window)
                dialog.show()
                QTest.qWait(20)
                self.assertTrue(dialog.btn_keep.isDefault())
                self.assertTrue(dialog.btn_keep.hasFocus())
                if action == "clear":
                    dialog.btn_clear.setFocus()
                    QTest.keyClick(dialog.btn_clear, Qt.Key.Key_Space)
                else:
                    key = Qt.Key.Key_Return if action == "return" else Qt.Key.Key_Escape
                    QTest.keyClick(dialog.btn_keep, key)
                self.assertTrue(dialog.isHidden())
                expected = QDialog.DialogCode.Accepted if action == "clear" else QDialog.DialogCode.Rejected
                self.assertEqual(dialog.result(), expected)
                dialog.deleteLater()


if __name__ == "__main__":
    unittest.main()
