"""Regression tests for ReplyReader navigation cluster, question line, and live turn separation.

Covers:
1. Turn navigation cluster: '‹  Lượt 2/3  ›       Mới nhất'
   - Prev/Next buttons step through turns
   - Boundary disabling (‹ disabled at first turn, › disabled at last turn)
   - 'Mới nhất' button only visible when viewing older turn
   - Clicking 'Mới nhất' jumps to latest turn and re-enables following live updates
2. Question preview line:
   - Matches displayed turn (both completed and live streaming)
   - Elided to available width with 'Câu hỏi · ' prefix
   - Preserves complete original query (including newlines and Vietnamese) in plain text tooltip
   - Hidden when query is empty
3. Bug regression: Live turn separation from history:
   - Completed turn A -> Submit question B -> Stream tokens -> Open Reader ("Đọc hết")
   - Reader displays question B and live answer B (NOT question A)
   - Selecting older turn keeps older turn during active stream of new turn
   - Finalizing stream turns live into completed without duplication
   - Copy action copies currently viewed turn's raw text
   - Session reset clears reader completely
   - PANEL_HEIGHT fixed at 252
"""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

from rat.ui.reply_reader import ReplyReader, ReaderItem
from rat.ui.omnibar import OmnibarWindow

app = QApplication.instance() or QApplication(sys.argv)


class TestReaderTurnNavigationAndQuery(unittest.TestCase):
    def test_navigation_cluster_states_and_boundaries(self):
        """Navigation cluster manages prev/next disabled states and 'Mới nhất' visibility."""
        reader = ReplyReader()
        reader.show()

        # Single turn: nav_container hidden, title is "Chuột · Câu trả lời"
        reader.set_turns([("Câu 1", "Trả lời 1")])
        self.assertFalse(reader.nav_container.isVisible())
        self.assertEqual(reader.title.text(), "Chuột · Câu trả lời")
        self.assertFalse(reader.btn_latest.isVisible())

        # Multiple turns (3 turns)
        turns = [
            ("Câu hỏi số 1", "Đáp án 1"),
            ("Câu hỏi số 2", "Đáp án 2"),
            ("Câu hỏi số 3", "Đáp án 3"),
        ]
        reader.set_turns(turns)

        self.assertTrue(reader.nav_container.isVisible())
        self.assertEqual(reader.title.text(), "Chuột")
        # Initially at latest turn (Lượt 3/3)
        self.assertEqual(reader.lbl_turn_counter.text(), "Lượt 3/3")
        self.assertTrue(reader.btn_prev.isEnabled())
        self.assertFalse(reader.btn_next.isEnabled())
        self.assertFalse(reader.btn_latest.isVisible())
        self.assertEqual(reader.full_reply, "Đáp án 3")

        # Step back to turn 2
        reader.btn_prev.click()
        self.assertEqual(reader.lbl_turn_counter.text(), "Lượt 2/3")
        self.assertTrue(reader.btn_prev.isEnabled())
        self.assertTrue(reader.btn_next.isEnabled())
        self.assertTrue(reader.btn_latest.isVisible())
        self.assertEqual(reader.full_reply, "Đáp án 2")

        # Step back to turn 1 (first turn)
        reader.btn_prev.click()
        self.assertEqual(reader.lbl_turn_counter.text(), "Lượt 1/3")
        self.assertFalse(reader.btn_prev.isEnabled())  # disabled at start
        self.assertTrue(reader.btn_next.isEnabled())
        self.assertTrue(reader.btn_latest.isVisible())
        self.assertEqual(reader.full_reply, "Đáp án 1")

        # Step forward to turn 2
        reader.btn_next.click()
        self.assertEqual(reader.lbl_turn_counter.text(), "Lượt 2/3")
        self.assertTrue(reader.btn_prev.isEnabled())
        self.assertTrue(reader.btn_next.isEnabled())
        self.assertTrue(reader.btn_latest.isVisible())

        # Click "Mới nhất" jumps straight to turn 3
        reader.btn_latest.click()
        self.assertEqual(reader.lbl_turn_counter.text(), "Lượt 3/3")
        self.assertTrue(reader.btn_prev.isEnabled())
        self.assertFalse(reader.btn_next.isEnabled())
        self.assertFalse(reader.btn_latest.isVisible())
        self.assertEqual(reader.full_reply, "Đáp án 3")

    def test_question_preview_line_elision_tooltip_and_empty(self):
        """Question preview line matches current turn, elides long queries, and retains raw text in tooltip."""
        reader = ReplyReader()
        reader.resize(500, 252)
        reader.show()

        # 1. Multi-line long Vietnamese query
        long_query = (
            "Tìm slide về tích phân đường loại 2\n"
            "trong thư mục Giải tích 2 kỳ trước\n"
            "và tóm tắt định lý Green giúp mình"
        )
        reader.start_live_turn("turn_1", long_query)
        reader.update_live_turn("Đang tính tích phân...")

        self.assertTrue(reader.query_label.isVisible())
        # Tooltip keeps all original newlines and content
        self.assertEqual(reader.query_label.toolTip(), long_query.strip())

        # Preview text starts with "Câu hỏi · " and collapses internal newlines
        preview_text = reader.query_label.text()
        self.assertTrue(preview_text.startswith("Câu hỏi · "))
        self.assertNotIn("\n", preview_text)
        # Check elision
        fm = reader.query_label.fontMetrics()
        self.assertLessEqual(fm.horizontalAdvance(preview_text), reader.width())
        reader.finalize_live_turn("Đáp án 1", query=long_query)

        # 2. Empty query hides query_label
        reader.start_live_turn("turn_2", "")
        self.assertFalse(reader.query_label.isVisible())

        # 3. Switching between turns updates query_label accordingly
        reader.finalize_live_turn("Đáp án 2", query="")
        reader.start_live_turn("turn_3", "Câu hỏi ngắn")
        reader.finalize_live_turn("Đáp án 3", query="Câu hỏi ngắn")

        # At turn 3
        self.assertTrue(reader.query_label.isVisible())
        self.assertEqual(reader.query_label.toolTip(), "Câu hỏi ngắn")
        self.assertIn("Câu hỏi · Câu hỏi ngắn", reader.query_label.text())

        # Back to turn 2 (empty query)
        reader._select_turn(1)
        self.assertFalse(reader.query_label.isVisible())

        # Back to turn 1 (long query)
        reader._select_turn(0)
        self.assertTrue(reader.query_label.isVisible())
        self.assertEqual(reader.query_label.toolTip(), long_query.strip())

    def test_live_stream_isolated_from_history_bug_reproduction(self):
        """Bug reproduction fix: Completing turn A, then streaming turn B does NOT show turn A when opening reader."""
        reader = ReplyReader()
        reader.show()

        # Step 1: Turn A completed
        reader.set_turns([("Câu hỏi A", "Đáp án đầy đủ của câu hỏi A")])
        self.assertEqual(reader.full_reply, "Đáp án đầy đủ của câu hỏi A")
        self.assertEqual(len(reader._get_items()), 1)

        # Step 2: User asks question B, streaming starts
        reader.start_live_turn("gen_1_req_2", "Câu hỏi B")
        reader.update_live_turn("Token 1 B ")
        reader.update_live_turn("Token 1 B Token 2 B")

        # Step 3: History sync (conversation history still only has turn A!)
        # In the buggy code, this overwrote live answer with Turn A
        history_still_only_turn_a = [("Câu hỏi A", "Đáp án đầy đủ của câu hỏi A")]
        reader.sync_history(history_still_only_turn_a)

        # Step 4: Open Reader -> MUST show Question B and streaming answer B!
        self.assertEqual(reader.lbl_turn_counter.text(), "Lượt 2/2")
        self.assertEqual(reader.full_reply, "Token 1 B Token 2 B")
        self.assertEqual(reader._current_query_text, "Câu hỏi B")
        self.assertIn("Token 1 B Token 2 B", reader.body.toPlainText())

        # Step 5: Finalizing turn B transitions it to completed without duplicate
        reader.finalize_live_turn("Token 1 B Token 2 B hoàn tất", is_error=False, query="Câu hỏi B")
        self.assertEqual(len(reader._get_items()), 2)
        self.assertEqual(reader.lbl_turn_counter.text(), "Lượt 2/2")
        self.assertEqual(reader.full_reply, "Token 1 B Token 2 B hoàn tất")

    def test_reading_older_turn_isolation_during_stream(self):
        """When reading an older turn, new stream tokens do not hijack view or selection."""
        reader = ReplyReader()
        reader.show()

        turns = [
            ("Câu A", "Nội dung A rất dài để đọc."),
            ("Câu B", "Nội dung B."),
        ]
        reader.set_turns(turns)

        # User intentionally steps back to turn A
        reader.btn_prev.click()
        self.assertEqual(reader.lbl_turn_counter.text(), "Lượt 1/2")
        self.assertEqual(reader.full_reply, "Nội dung A rất dài để đọc.")

        # Simulate user selecting text in turn A
        cursor = reader.body.textCursor()
        cursor.setPosition(0)
        cursor.setPosition(len("Nội dung"), cursor.MoveMode.KeepAnchor)
        reader.body.setTextCursor(cursor)
        self.assertEqual(reader.body.textCursor().selectedText(), "Nội dung")

        # New stream starts for question C
        reader.start_live_turn("gen_1_req_3", "Câu C")
        reader.update_live_turn("Token 1 của C...")
        reader.update_live_turn("Token 1 của C... Token 2 của C...")

        # Reader must STAY on turn A!
        self.assertEqual(reader.lbl_turn_counter.text(), "Lượt 1/3")
        self.assertEqual(reader.full_reply, "Nội dung A rất dài để đọc.")
        self.assertEqual(reader._current_query_text, "Câu A")
        self.assertEqual(reader.body.textCursor().selectedText(), "Nội dung")

        # Copying copies turn A, not turn C!
        reader._copy()
        self.assertEqual(QApplication.clipboard().text(), "Nội dung A rất dài để đọc.")

        # User clicks "Mới nhất": now jumps to turn C and follows live updates
        reader.btn_latest.click()
        self.assertEqual(reader.lbl_turn_counter.text(), "Lượt 3/3")
        self.assertEqual(reader.full_reply, "Token 1 của C... Token 2 của C...")
        self.assertEqual(reader._current_query_text, "Câu C")

        # Further tokens for turn C now update the view
        reader.update_live_turn("Token 1 của C... Token 2 của C... Token 3!")
        self.assertEqual(reader.full_reply, "Token 1 của C... Token 2 của C... Token 3!")

    def test_error_and_interrupted_turn_readable_in_reader(self):
        """Interrupted/error turns can be read in Reader without being added to model context history."""
        reader = ReplyReader()
        reader.show()

        reader.start_live_turn("gen_1_req_1", "Câu hỏi bị đứt mạng")
        reader.update_live_turn("Đang kết nối...")
        reader.finalize_live_turn(
            "Chưa nhận được phản hồi từ AI. Kiểm tra mô hình trong Cài đặt rồi thử lại nhé.",
            is_error=True,
            query="Câu hỏi bị đứt mạng",
        )

        # Reader displays it
        self.assertEqual(len(reader._get_items()), 1)
        self.assertEqual(
            reader.full_reply,
            "Chưa nhận được phản hồi từ AI. Kiểm tra mô hình trong Cài đặt rồi thử lại nhé.",
        )
        self.assertEqual(reader._current_query_text, "Câu hỏi bị đứt mạng")

        # Syncing history (which is empty because error wasn't added to conversation history)
        reader.sync_history([])
        # Error turn is preserved in reader!
        self.assertEqual(len(reader._get_items()), 1)
        self.assertTrue(reader._get_items()[0].is_error)

    def test_reader_height_strictly_252(self):
        """Reader strictly adheres to PANEL_HEIGHT = 252 with query label visible or hidden."""
        reader = ReplyReader()
        self.assertEqual(reader.height(), 252)
        self.assertEqual(reader.PANEL_HEIGHT, 252)

        reader.start_live_turn("t1", "Câu hỏi rất dài hiển thị label câu hỏi")
        reader.update_live_turn("Đáp án")
        self.assertEqual(reader.height(), 252)

        reader.clear_all()
        self.assertEqual(reader.height(), 252)


if __name__ == "__main__":
    unittest.main()
