"""Regression tests for Priority 1: Reliable Response States (Trạng thái phản hồi đáng tin).

Covers state mapping across Quick/Reader/Full mode, transitions from waiting to writing,
idempotent completion, error/interrupted recovery, retry preserving composer drafts,
and stale callback isolation upon reset.
"""

import os
import sys
import time
import unittest
from unittest.mock import MagicMock, patch

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QLabel, QPushButton

from rat.ui.omnibar import OmnibarWindow

app = QApplication.instance() or QApplication(sys.argv)


class TestResponseState(unittest.TestCase):
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

    def test_full_mode_displays_busy_state_in_footer(self):
        """In Full mode, footer must display 'Đang chờ phản hồi…' and 'Đang viết…' instead of key hints."""
        self.window.show()
        self.window.set_expanded(True)

        with patch("rat.ui.omnibar.StreamReasoningWorker") as mock_worker:
            self.window._submit_chat_prompt("Giải thích quy tắc giao dịch")
            # In waiting phase
            self.assertEqual(self.window._presentation_state.phase, "waiting")
            self.assertEqual(self.window.compact_hint.text(), "Đang chờ phản hồi…")

            # First token arrives -> transitions to writing
            handle = self.window._current_stream_handle
            self.assertIsNotNone(handle)
            self.window._on_reasoning_token(handle, "Quy tắc 1: ")
            self.assertEqual(self.window._presentation_state.phase, "writing")
            self.assertEqual(self.window.compact_hint.text(), "Đang viết…")
            self.assertTrue(handle["status_lbl"].isHidden())
            self.assertFalse(handle["ans_lbl"].isHidden())
            self.assertIn("Quy tắc 1: ", handle["ans_lbl"].text())

    def test_non_streaming_direct_reply_transitions_to_completed(self):
        """Non-streaming replies transition cleanly to completed status."""
        self.window.show()
        self.window._submit_chat_prompt("chào chuột")
        self.assertEqual(self.window._presentation_state.phase, "completed")
        self.assertIn("Đã trả lời", self.window.compact_hint.text())
        self.assertEqual(len(self.window._conversation._turns), 1)

    def test_interrupted_response_keeps_partial_tokens_and_retry_action(self):
        """Interrupted streams keep partial content, show 'Phản hồi bị ngắt' and offer retry."""
        self.window.show()
        self.window.set_expanded(True)

        with patch("rat.ui.omnibar.StreamReasoningWorker") as mock_worker:
            self.window._submit_chat_prompt("Viết bài luận ngắn")
            handle = self.window._current_stream_handle
            self.window._on_reasoning_token(handle, "Phần mở bài đã viết xong...")

            # Abrupt interruption
            self.window._on_reasoning_finished(
                handle,
                handle["full_text"],
                [],
                120.0,
                "Phản hồi bị ngắt",
                "Qwen",
            )

            self.assertEqual(self.window._presentation_state.phase, "interrupted")
            self.assertTrue(self.window._presentation_state.retry_available)
            self.assertEqual(self.window.compact_hint.text(), "Phản hồi bị ngắt")
            self.assertIn("Phản hồi bị ngắt", handle["context_label"].text())

            # Partial text must be readable and copyable
            self.assertIn("Phần mở bài đã viết xong...", handle["ans_lbl"].text())
            self.assertTrue(handle["copy_button"].isEnabled())

            # Interrupted responses are NOT saved into completed history turns
            self.assertEqual(len(self.window._conversation._turns), 0)

            # Retry button is displayed on the card and in compact footer
            self.assertIn("retry_button", handle)
            self.assertFalse(handle["retry_button"].isHidden())
            self.assertFalse(self.window.compact_retry_btn.isHidden())

    def test_connection_error_displays_error_actions_and_no_completed_turn(self):
        """Connection errors are displayed with recovery actions and not stored as model answers."""
        self.window.show()

        with patch("rat.ui.omnibar.StreamReasoningWorker") as mock_worker:
            self.window._submit_chat_prompt("Hỏi một điều khó")
            handle = self.window._current_stream_handle

            self.window._on_reasoning_finished(
                handle,
                "Không thể kết nối đến Ollama.",
                [],
                15.0,
                "AI chưa sẵn sàng",
                "Chưa kết nối",
            )

            self.assertEqual(self.window._presentation_state.phase, "error")
            self.assertTrue(self.window._presentation_state.retry_available)
            self.assertEqual(self.window.compact_hint.text(), "Chưa nhận được phản hồi")
            self.assertIn("Chưa nhận được phản hồi", handle["context_label"].text())
            self.assertIn("settings_button", handle)
            self.assertFalse(handle["settings_button"].isHidden())
            self.assertEqual(self.window._conversation.messages(), [])

    def test_retry_preserves_composer_draft_and_resubmits_original_query(self):
        """Retry uses original query, keeps composer draft intact, and does not create new session ID."""
        self.window.show()
        original_session = self.window._conversation.session_id

        with patch("rat.ui.omnibar.StreamReasoningWorker") as mock_worker:
            self.window._submit_chat_prompt("Câu hỏi ban đầu")
            handle = self.window._current_stream_handle

            self.window._on_reasoning_finished(
                handle,
                "Lỗi mạng",
                [],
                10.0,
                "AI chưa sẵn sàng",
                "Chưa kết nối",
            )

            # User is typing their next draft while seeing the retry button
            draft_text = "Bản nháp đang gõ dở\nkhông được mất!"
            self.window.chat_composer_input.setText(draft_text)

            # Click retry
            with patch.object(self.window, "chat_stream") as mock_stream:
                # Trigger retry
                self.window._retry_chat()

            # Composer draft is strictly preserved
            self.assertEqual(self.window.chat_composer_input.text(), draft_text)
            # Session ID is unchanged
            self.assertEqual(self.window._conversation.session_id, original_session)
            # Retry available is now False to prevent duplicate triggers
            self.assertFalse(self.window._presentation_state.retry_available)
            # Presentation query is the original query
            self.assertEqual(self.window._presentation_state.query, "Câu hỏi ban đầu")

    def test_reset_invalidates_stale_callbacks(self):
        """Resetting cancels running queries and discards any late worker callbacks."""
        self.window.show()

        with patch("rat.ui.omnibar.StreamReasoningWorker") as mock_worker:
            self.window._submit_chat_prompt("Câu hỏi 1")
            old_handle = self.window._current_stream_handle

            # Reset chat
            self.window._reset_chat()
            self.assertEqual(self.window._presentation_state.phase, "idle")
            self.assertEqual(self.window.speech_bubble.text(), "Nghe đây. Cần gì?")

            # Late callback arrives for old_handle
            self.window._on_reasoning_token(old_handle, "Token muộn")
            self.window._on_reasoning_finished(
                old_handle,
                "Đáp án muộn",
                [],
                50.0,
                "AI cục bộ",
                "Qwen",
            )

            # Old callback must not resurrect conversation or update presentation state
            self.assertEqual(self.window._presentation_state.phase, "idle")
            self.assertEqual(len(self.window._conversation._turns), 0)
