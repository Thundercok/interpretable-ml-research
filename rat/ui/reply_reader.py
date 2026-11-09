"""The latest answer, readable in place without opening the entire conversation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QDesktopServices, QTextCursor, QTextOption
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from rat.ui.reply_text import MARKDOWN_FEATURES, ReplyTextBrowser, reply_plain_text, space_reply_document


@dataclass
class ReaderItem:
    turn_id: str
    query: str
    answer: str
    is_live: bool = False
    is_error: bool = False


class ReplyReader(QFrame):
    close_requested = pyqtSignal()
    copied = pyqtSignal()
    PANEL_HEIGHT = 252

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.full_reply = ""
        self._rendered_reply = ""
        self._current_query_text = ""

        # Items and state management
        self._completed_items: list[ReaderItem] = []
        self._live_item: Optional[ReaderItem] = None
        self._active_index: int = -1
        self._following_latest: bool = True

        self.setObjectName("ReplyReader")
        self.setFixedHeight(self.PANEL_HEIGHT)
        self.setStyleSheet("""
            QFrame#ReplyReader { background: transparent; border: none; }
            QPushButton { background: transparent; border: none; border-radius: 4px;
                color: #6B6258; font-size: 11px; padding: 3px 6px; }
            QPushButton:hover { background: #F0E8DA; color: #302B24; }
            QPushButton:disabled { color: #C4BAAC; background: transparent; }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 6)
        layout.setSpacing(4)

        # Header bar
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(6)

        self.title = QLabel("Chuột · Câu trả lời")
        self.title.setStyleSheet("color: #6F6456; font-size: 11px; font-weight: 600;")
        header.addWidget(self.title)

        self.tag_label = QLabel()
        self.tag_label.setStyleSheet(
            "color: #7B6E5F; font-size: 10px; font-weight: 500; background: #F0E8DC; border-radius: 4px; padding: 1px 6px;"
        )
        self.tag_label.hide()
        header.addWidget(self.tag_label)

        # Navigation cluster: ‹  Lượt 2/3  ›       Mới nhất
        self.nav_container = QWidget()
        nav_layout = QHBoxLayout(self.nav_container)
        nav_layout.setContentsMargins(2, 0, 2, 0)
        nav_layout.setSpacing(3)

        self.btn_prev = QPushButton("‹")
        self.btn_prev.setToolTip("Lượt trước")
        self.btn_prev.setAccessibleName("Lượt trước")
        self.btn_prev.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_prev.setStyleSheet("""
            QPushButton {
                font-size: 13px; font-weight: bold; padding: 1px 6px; min-width: 18px;
            }
        """)
        self.btn_prev.clicked.connect(self._go_prev)
        nav_layout.addWidget(self.btn_prev)

        self.lbl_turn_counter = QLabel("Lượt 1/1")
        self.lbl_turn_counter.setStyleSheet(
            "color: #6F6456; font-size: 11px; font-weight: 600; padding: 0 4px;"
        )
        nav_layout.addWidget(self.lbl_turn_counter)

        self.btn_next = QPushButton("›")
        self.btn_next.setToolTip("Lượt sau")
        self.btn_next.setAccessibleName("Lượt sau")
        self.btn_next.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_next.setStyleSheet("""
            QPushButton {
                font-size: 13px; font-weight: bold; padding: 1px 6px; min-width: 18px;
            }
        """)
        self.btn_next.clicked.connect(self._go_next)
        nav_layout.addWidget(self.btn_next)

        self.btn_latest = QPushButton("Mới nhất")
        self.btn_latest.setToolTip("Xem câu trả lời mới nhất")
        self.btn_latest.setAccessibleName("Về câu trả lời mới nhất")
        self.btn_latest.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_latest.setStyleSheet("""
            QPushButton {
                background: #EFE6D8; border: 1px solid #DCD1BF; border-radius: 4px;
                color: #554A3E; font-size: 10px; font-weight: 600; padding: 1px 6px; margin-left: 4px;
            }
            QPushButton:hover { background: #E4D8C4; color: #2E2821; }
        """)
        self.btn_latest.clicked.connect(self._go_latest)
        self.btn_latest.hide()
        nav_layout.addWidget(self.btn_latest)

        self.nav_container.hide()
        header.addWidget(self.nav_container)

        # Backwards compatibility handles
        self.turn_strip = self.nav_container
        self.turn_layout = nav_layout

        header.addStretch()

        self.copy_button = QPushButton("Sao chép")
        self.copy_button.setToolTip("Sao chép toàn bộ câu trả lời, giữ nguyên định dạng gốc")
        self.copy_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.copy_button.clicked.connect(self._copy)
        header.addWidget(self.copy_button)

        self.close_button = QPushButton("Thu gọn")
        self.close_button.setToolTip("Quay lại gọi nhanh (Esc)")
        self.close_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_button.clicked.connect(self.close_requested)
        header.addWidget(self.close_button)

        layout.addLayout(header)

        # Subtitle: Question line (UI requirement 2)
        # Displays e.g. "Câu hỏi · Tìm slide về tích phân…"
        self.query_label = QLabel()
        self.query_label.setObjectName("ReplyReaderQueryLabel")
        self.query_label.setStyleSheet(
            "color: #7D7264; font-size: 11px; font-weight: 500; background: transparent; padding: 0 2px;"
        )
        self.query_label.hide()
        layout.addWidget(self.query_label)

        # Body area
        self.body = ReplyTextBrowser()
        self.body.setObjectName("ReplyReaderBody")
        self.body.setAccessibleName("Câu trả lời đầy đủ của Chuột")
        self.body.setFrameShape(QFrame.Shape.NoFrame)
        self.body.setReadOnly(True)
        self.body.setWordWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        font = self.body.font()
        font.setPixelSize(14)
        self.body.setFont(font)
        self.body.setOpenLinks(False)
        self.body.setOpenExternalLinks(False)
        self.body.anchorClicked.connect(self._open_link)
        self.body.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.body.setStyleSheet("""
            QTextBrowser#ReplyReaderBody { border: none; background: transparent;
                color: #302B24; font-size: 14px; selection-background-color: #E8DABC; }
        """)
        self.body.document().setDocumentMargin(0)
        layout.addWidget(self.body, 1)

        self._copy_timer = QTimer(self)
        self._copy_timer.setSingleShot(True)
        self._copy_timer.timeout.connect(lambda: self.copy_button.setText("Sao chép"))

    @property
    def _active_turn_idx(self) -> int:
        return self._active_index

    @_active_turn_idx.setter
    def _active_turn_idx(self, val: int) -> None:
        self._active_index = val

    @property
    def _turns(self) -> list[tuple[str, str]]:
        return [(it.query, it.answer) for it in self._get_items()]

    @_turns.setter
    def _turns(self, val: list[tuple[str, str]]) -> None:
        self.set_turns(val)

    def _get_items(self) -> list[ReaderItem]:
        items = list(self._completed_items)
        if self._live_item is not None:
            if not any(it.turn_id and it.turn_id == self._live_item.turn_id for it in items):
                items.append(self._live_item)
        return items

    def has_content(self) -> bool:
        items = self._get_items()
        return bool(self.full_reply.strip() or any(it.answer.strip() for it in items))

    def _sync_active_view(self) -> None:
        items = self._get_items()
        if not items:
            self._active_index = -1
            self.set_reply("")
            self._current_query_text = ""
            self._update_query_label()
            self._update_nav_ui()
            return

        if self._following_latest or self._active_index < 0 or self._active_index >= len(items):
            self._active_index = len(items) - 1

        curr_item = items[self._active_index]
        self.set_reply(curr_item.answer)
        self._current_query_text = curr_item.query
        self._update_query_label()
        self._update_nav_ui()

    def _update_nav_ui(self) -> None:
        items = self._get_items()
        total = len(items)
        if total > 1:
            self.title.setText("Chuột")
            self.nav_container.show()
            self.lbl_turn_counter.setText(f"Lượt {self._active_index + 1}/{total}")
            self.btn_prev.setEnabled(self._active_index > 0)
            self.btn_next.setEnabled(self._active_index < total - 1)
            is_viewing_older = (self._active_index < total - 1)
            self.btn_latest.setVisible(is_viewing_older)
        else:
            self.title.setText("Chuột · Câu trả lời")
            self.nav_container.hide()
            self.btn_latest.hide()

    def _update_query_label(self) -> None:
        q_raw = self._current_query_text
        if not q_raw or not q_raw.strip():
            self.query_label.hide()
            self.query_label.setText("")
            self.query_label.setToolTip("")
            return

        # Raw query text is preserved in tooltip (including newlines and full text)
        self.query_label.setToolTip(q_raw.strip())

        # For single-line preview: collapse internal newlines/spaces
        preview_text = " ".join(q_raw.strip().split())
        full_text = f"Câu hỏi · {preview_text}"

        fm = self.query_label.fontMetrics()
        w = self.query_label.width()
        if w <= 20:
            w = max(self.width() - 24, 200)

        elided = fm.elidedText(full_text, Qt.TextElideMode.ElideRight, w)
        self.query_label.setText(elided)
        self.query_label.show()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._current_query_text and self._current_query_text.strip():
            self._update_query_label()

    def _go_prev(self) -> None:
        if self._active_index > 0:
            self._following_latest = False
            self._select_turn(self._active_index - 1)

    def _go_next(self) -> None:
        items = self._get_items()
        if self._active_index < len(items) - 1:
            target_idx = self._active_index + 1
            if target_idx == len(items) - 1:
                self._following_latest = True
            else:
                self._following_latest = False
            self._select_turn(target_idx)

    def _go_latest(self) -> None:
        items = self._get_items()
        if items:
            self._following_latest = True
            self._select_turn(len(items) - 1)

    def _select_turn(self, idx: int) -> None:
        items = self._get_items()
        if 0 <= idx < len(items):
            self._active_index = idx
            self._following_latest = (idx == len(items) - 1)
            curr = items[idx]
            self.set_reply(curr.answer)
            self._current_query_text = curr.query
            self._update_query_label()
            self._update_nav_ui()

    def start_live_turn(self, turn_id: str, query: str) -> None:
        """Start a new live response turn."""
        if self._live_item is not None:
            if not any(it.turn_id == self._live_item.turn_id for it in self._completed_items):
                self._completed_items.append(self._live_item)
            self._live_item = None

        self._live_item = ReaderItem(
            turn_id=turn_id,
            query=query,
            answer="",
            is_live=True,
            is_error=False,
        )
        if self._following_latest:
            items = self._get_items()
            self._active_index = len(items) - 1
            self.set_reply("")
            self._current_query_text = query
            self._update_query_label()
        self._update_nav_ui()

    def update_live_turn(self, answer: str, query: Optional[str] = None) -> None:
        """Stream an update to the live response turn."""
        if self._live_item is None:
            self._live_item = ReaderItem(
                turn_id="live_turn",
                query=query or "",
                answer=answer,
                is_live=True,
                is_error=False,
            )
        else:
            self._live_item.answer = answer
            if query is not None:
                self._live_item.query = query

        if self._following_latest:
            items = self._get_items()
            self._active_index = len(items) - 1
            self.set_reply(answer)
            if self._live_item.query:
                self._current_query_text = self._live_item.query
                self._update_query_label()
        self._update_nav_ui()

    def finalize_live_turn(self, answer: str, is_error: bool = False, query: Optional[str] = None) -> None:
        """Finalize the live response turn and transition into completed items."""
        if self._live_item is not None:
            self._live_item.answer = answer
            self._live_item.is_live = False
            self._live_item.is_error = is_error
            if query is not None:
                self._live_item.query = query
            live = self._live_item
            self._live_item = None
            if not any(it.turn_id == live.turn_id for it in self._completed_items):
                self._completed_items.append(live)
        else:
            if not self._completed_items or self._completed_items[-1].answer != answer:
                self._completed_items.append(
                    ReaderItem(
                        turn_id=f"item_{len(self._completed_items)}",
                        query=query or "",
                        answer=answer,
                        is_live=False,
                        is_error=is_error,
                    )
                )

        if self._following_latest:
            self._active_index = len(self._completed_items) - 1
            if 0 <= self._active_index < len(self._completed_items):
                curr = self._completed_items[self._active_index]
                self.set_reply(curr.answer)
                self._current_query_text = curr.query
                self._update_query_label()
        self._update_nav_ui()

    def sync_history(self, turns: list[tuple[str, str]]) -> None:
        """Sync completed turns from conversation history without clearing or overwriting live stream."""
        turns_list = list(turns)
        new_completed: list[ReaderItem] = []
        for i, (q, a) in enumerate(turns_list):
            tid = f"hist_{i}"
            matched = None
            for item in self._completed_items:
                if item.turn_id == tid or (item.query == q and item.answer == a):
                    matched = item
                    break
            if matched:
                new_completed.append(matched)
            else:
                new_completed.append(ReaderItem(turn_id=tid, query=q, answer=a))

        # Preserve error/interrupted items that aren't stored in conversation history
        for item in self._completed_items:
            if item.is_error and item not in new_completed:
                new_completed.append(item)

        self._completed_items = new_completed

        # If live item duplicate exists in completed items, deduplicate
        if self._live_item and self._completed_items:
            last = self._completed_items[-1]
            if (self._live_item.turn_id == last.turn_id) or (
                self._live_item.query == last.query and self._live_item.answer == last.answer
            ):
                self._live_item = None

        if self._following_latest:
            items = self._get_items()
            self._active_index = len(items) - 1 if items else -1
            self._sync_active_view()
        else:
            self._update_nav_ui()

    def set_turns(self, turns: list[tuple[str, str]]) -> None:
        """Set history turns for backwards compatibility."""
        turns_list = list(turns)
        existing_tuples = [(it.query, it.answer) for it in self._completed_items]
        if turns_list == existing_tuples and not self._live_item:
            if self._following_latest:
                self._sync_active_view()
            return

        prev_idx = self._active_index
        prev_total = len(self._get_items())

        self._completed_items = [
            ReaderItem(turn_id=f"hist_{i}", query=q, answer=a)
            for i, (q, a) in enumerate(turns_list)
        ]

        total = len(self._get_items())
        if 0 <= prev_idx < prev_total - 1 and prev_idx < total:
            self._active_index = prev_idx
            self._following_latest = False
        else:
            self._active_index = total - 1 if total > 0 else -1
            self._following_latest = True

        self._sync_active_view()

    def set_streaming_reply(self, answer: str) -> None:
        """Streaming update for the reply reader: delegates to update_live_turn."""
        self.update_live_turn(answer)

    def clear_all(self) -> None:
        """Reset reader state on session clear."""
        self._completed_items.clear()
        self._live_item = None
        self._active_index = -1
        self._following_latest = True
        self._current_query_text = ""
        self.set_reply("")
        self._update_query_label()
        self._update_nav_ui()

    def set_session_tag(self, tag: str) -> None:
        if tag:
            self.tag_label.setText(tag)
            self.tag_label.show()
        else:
            self.tag_label.hide()

    def set_reply(self, answer: str) -> None:
        if answer == self.full_reply and self.body.toPlainText():
            return
        self.full_reply = answer
        self.copy_button.setEnabled(bool(answer.strip()))
        self._copy_timer.stop()
        self.copy_button.setText("Sao chép")
        if not answer:
            self.body.clear()
            self._rendered_reply = ""
        elif self.isVisible():
            self._render_latest_reply()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._render_latest_reply()
        if self._current_query_text and self._current_query_text.strip():
            self._update_query_label()

    def _render_latest_reply(self) -> None:
        answer = self.full_reply
        previous = self._rendered_reply
        if answer == previous:
            return
        scrollbar = self.body.verticalScrollBar()
        scroll_value = scrollbar.value()
        is_at_bottom = scroll_value >= (scrollbar.maximum() - 4)
        cursor = self.body.textCursor()
        selection = (cursor.anchor(), cursor.position())
        has_selection = (selection[0] != selection[1])

        self.body.document().setMarkdown(answer, MARKDOWN_FEATURES)
        self._rendered_reply = answer
        space_reply_document(self.body.document())

        if previous and answer.startswith(previous):
            if has_selection:
                cursor = self.body.textCursor()
                end = self.body.document().characterCount() - 1
                cursor.setPosition(min(selection[0], end))
                cursor.setPosition(min(selection[1], end), QTextCursor.MoveMode.KeepAnchor)
                self.body.setTextCursor(cursor)
                scrollbar.setValue(scroll_value)
            elif is_at_bottom:
                scrollbar.setValue(scrollbar.maximum())
            else:
                scrollbar.setValue(scroll_value)
        else:
            cursor = self.body.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.Start)
            self.body.setTextCursor(cursor)
            scrollbar.setValue(0)

    def _copy(self) -> None:
        if self.full_reply.strip():
            QApplication.clipboard().setText(self.full_reply)
            self.copy_button.setText("Đã sao chép")
            self._copy_timer.start(1500)
            self.copied.emit()

    @staticmethod
    def _open_link(url) -> None:
        if url.scheme().lower() in ("https", "http"):
            QDesktopServices.openUrl(url)
