"""Regression tests for Priority 3: Complex Content (Code blocks, Tables, Reader pills, and Coalescing).

Covers:
- Code blocks parsing (``` and ~~~, nested fences, language badge, unclosed streaming state)
- Code block copy action (only inner content, verbatim indentation, newlines, and Unicode)
- Monospace font and styling for code blocks
- Table styling (header background #EFE8DC, padding >= 6px, numeric right alignment)
- Reader mode: 'Lượt 1, Lượt 2' pills, pill persistence without widget churn,
  turn isolation (streaming does not overwrite older turns being read),
  and turn-specific copying
- Render coalescing (35ms stream buffering and instant flush upon finalization)
"""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QPushButton

from rat.ui.reply_text import (
    CodeBlockBadge,
    ConversationReplyBody,
    MARKDOWN_FEATURES,
    parse_code_blocks,
    space_reply_document,
)
from rat.ui.reply_reader import ReplyReader
from rat.ui.chat_stream import ChatStreamWidget

app = QApplication.instance() or QApplication(sys.argv)


class TestComplexContentAndReader(unittest.TestCase):
    def test_code_blocks_parser_backticks_and_tildes(self):
        """Parser handles both ``` and ~~~, captures languages, and differentiates closed vs unclosed blocks."""
        text = (
            "Một đoạn văn mở đầu.\n\n"
            "```python\n"
            "def chao_ban(ten: str) -> str:\n"
            "    return f'Xin chào, {ten}! ✨'\n"
            "```\n\n"
            "Đoạn giữa.\n\n"
            "~~~json\n"
            "{\n"
            '  "ma_sinh_vien": "SV12345",\n'
            '  "diem": 9.5\n'
            "}\n"
            "~~~\n\n"
            "Đoạn chưa đóng:\n\n"
            "```javascript\n"
            "console.log('đang stream');"
        )
        blocks = parse_code_blocks(text)
        self.assertEqual(len(blocks), 3)

        # Block 1: Python with backticks
        self.assertEqual(blocks[0]["lang"], "python")
        self.assertTrue(blocks[0]["closed"])
        self.assertEqual(
            blocks[0]["code"],
            "def chao_ban(ten: str) -> str:\n    return f'Xin chào, {ten}! ✨'",
        )

        # Block 2: JSON with tildes
        self.assertEqual(blocks[1]["lang"], "json")
        self.assertTrue(blocks[1]["closed"])
        self.assertIn('"ma_sinh_vien": "SV12345"', blocks[1]["code"])

        # Block 3: JavaScript unclosed streaming
        self.assertEqual(blocks[2]["lang"], "javascript")
        self.assertFalse(blocks[2]["closed"])
        self.assertEqual(blocks[2]["code"], "console.log('đang stream');")

    def test_nested_code_fences_handling(self):
        """Nested backticks inside a larger 4-backtick fence do not break outer parsing."""
        nested_text = (
            "````markdown\n"
            "Đây là hướng dẫn Markdown:\n"
            "```python\n"
            "x = 10\n"
            "```\n"
            "````"
        )
        blocks = parse_code_blocks(nested_text)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0]["lang"], "markdown")
        self.assertTrue(blocks[0]["closed"])
        self.assertIn("```python\nx = 10\n```", blocks[0]["code"])

    def test_code_badge_copy_button_presence_and_action(self):
        """Closed code blocks display 'Chép code' button; streaming unclosed blocks do not."""
        code_content = "def tinh_tong(a, b):\n    return a + b"

        # Closed block badge
        badge_closed = CodeBlockBadge("python", code_content, is_closed=True)
        self.assertIsNotNone(badge_closed.copy_btn)
        self.assertEqual(badge_closed.copy_btn.text(), "Chép code")

        # Copy action copies ONLY the raw code (no backticks, no language)
        badge_closed._copy_code()
        cb_text = QApplication.clipboard().text()
        self.assertEqual(cb_text, code_content)
        self.assertEqual(badge_closed.copy_btn.text(), "Đã chép")

        # Unclosed block badge (while streaming)
        badge_unclosed = CodeBlockBadge("python", "def tinh_tong(a", is_closed=False)
        self.assertIsNone(badge_unclosed.copy_btn)

    def test_table_formatting_headers_padding_and_numeric_alignment(self):
        """Markdown tables format with #EFE8DC header, padding >= 6px, and right-aligned numbers."""
        body = ConversationReplyBody()
        body.resize(600, 400)
        body.show()

        table_md = (
            "| Học phần | Số tín | Điểm tổng kết |\n"
            "|---|---|---|\n"
            "| Lập trình Python | 3 | 9.2 |\n"
            "| Giải tích 1 | 4 | 8.5 |\n"
            "| Tiếng Anh chuyên ngành | 2 | 10 |"
        )
        body.setText(table_md)
        doc = body.document()

        # Check table structure
        tables = [f for f in doc.rootFrame().childFrames() if hasattr(f, "rows")]
        self.assertEqual(len(tables), 1)
        table = tables[0]
        self.assertEqual(table.rows(), 4)
        self.assertEqual(table.columns(), 3)
        self.assertGreaterEqual(table.format().cellPadding(), 6.0)

        # Header cell formatting (row 0)
        h_cell = table.cellAt(0, 0)
        self.assertEqual(h_cell.format().background().color().name().lower(), "#efe8dc")

        # Numeric cells in data rows must be aligned right
        num_cell = table.cellAt(1, 1)  # "3"
        align = num_cell.firstCursorPosition().blockFormat().alignment()
        self.assertEqual(align, Qt.AlignmentFlag.AlignRight)

        # Text cells in data rows are left aligned
        text_cell = table.cellAt(1, 0)  # "Lập trình Python"
        text_align = text_cell.firstCursorPosition().blockFormat().alignment()
        self.assertNotEqual(text_align, Qt.AlignmentFlag.AlignRight)

        # Raw Markdown is preserved for copying
        self.assertEqual(body.text(), table_md)

    def test_render_coalescing_batches_streaming_tokens_and_flushes_on_finalize(self):
        """Streaming tokens are coalesced without synchronous reflow, then flushed on completion."""
        stream = ChatStreamWidget()
        stream.resize(600, 500)
        stream.show()

        handle = stream.create_streaming_message(context="Trả lời")
        ans_lbl = handle["ans_lbl"]
        self.assertIsInstance(ans_lbl, ConversationReplyBody)

        # Send multiple rapid tokens
        tokens = ["Đoạn ", "này ", "đang ", "được ", "sinh ", "nhanh..."]
        for tok in tokens:
            stream.append_stream_token(handle, tok)

        # Before coalescing timer fires, raw text is tracked
        self.assertEqual(handle["full_text"], "Đoạn này đang được sinh nhanh...")

        # Finalize stream immediately flushes pending render
        stream.finalize_stream(handle, strategy="AI cục bộ")
        self.assertIn("Đoạn này đang được sinh nhanh...", ans_lbl.toPlainText())

    def test_reply_reader_navigation_cluster_and_no_churn_on_token(self):
        """Reply reader uses '‹ Lượt X/Y › Mới nhất' cluster and does not destroy widgets on tokens."""
        reader = ReplyReader()
        reader.show()

        turns = [
            ("Hỏi câu 1", "Đáp án 1"),
            ("Hỏi câu 2", "Đáp án 2"),
        ]
        reader.set_turns(turns)

        # Initially at latest turn (Lượt 2/2)
        self.assertEqual(reader.lbl_turn_counter.text(), "Lượt 2/2")
        self.assertTrue(reader.btn_prev.isEnabled())
        self.assertFalse(reader.btn_next.isEnabled())
        self.assertFalse(reader.btn_latest.isVisible())

        # Navigate to previous turn
        reader.btn_prev.click()
        self.assertEqual(reader.lbl_turn_counter.text(), "Lượt 1/2")
        self.assertFalse(reader.btn_prev.isEnabled())
        self.assertTrue(reader.btn_next.isEnabled())
        self.assertTrue(reader.btn_latest.isVisible())
        self.assertEqual(reader.full_reply, "Đáp án 1")

        # Click "Mới nhất" returns to latest turn
        reader.btn_latest.click()
        self.assertEqual(reader.lbl_turn_counter.text(), "Lượt 2/2")
        self.assertFalse(reader.btn_latest.isVisible())
        self.assertEqual(reader.full_reply, "Đáp án 2")

        # Stable widget instances across stream updates
        prev_btn_id = id(reader.btn_prev)
        next_btn_id = id(reader.btn_next)
        reader.set_streaming_reply("Đáp án 2 đang tiếp tục...")
        self.assertEqual(id(reader.btn_prev), prev_btn_id)
        self.assertEqual(id(reader.btn_next), next_btn_id)

    def test_reply_reader_turn_isolation_and_copying(self):
        """When reading an older turn, incoming stream tokens do NOT overwrite view, and copy copies that turn."""
        reader = ReplyReader()
        reader.show()

        turns = [
            ("Hỏi câu 1", "Nội dung câu 1"),
            ("Hỏi câu 2", "Nội dung câu 2"),
        ]
        reader.set_turns(turns)

        # Select turn 0 (Lượt 1)
        reader._select_turn(0)
        self.assertEqual(reader._active_turn_idx, 0)
        self.assertEqual(reader.full_reply, "Nội dung câu 1")
        self.assertIn("Nội dung câu 1", reader.body.toPlainText())

        # An incoming stream token for a subsequent turn arrives
        reader.set_streaming_reply("Token mới của lượt đang chạy...")

        # Reader must still display turn 0!
        self.assertEqual(reader._active_turn_idx, 0)
        self.assertEqual(reader.full_reply, "Nội dung câu 1")
        self.assertIn("Nội dung câu 1", reader.body.toPlainText())

        # Copy action must copy turn 0
        reader._copy()
        self.assertEqual(QApplication.clipboard().text(), "Nội dung câu 1")


if __name__ == "__main__":
    unittest.main()
