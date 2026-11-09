"""Shared, text-only Markdown spacing and a self-sizing conversation body."""

from __future__ import annotations

import math
import re
from typing import Any, Dict, List, Optional

from PyQt6.QtCore import QRectF, QTimer, Qt, pyqtSignal
from PyQt6.QtGui import (
    QColor,
    QDesktopServices,
    QPainter,
    QPen,
    QTextBlockFormat,
    QTextCharFormat,
    QTextCursor,
    QTextDocument,
    QTextFrameFormat,
    QTextOption,
    QTextTable,
    QTextTableCellFormat,
)
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QTextBrowser,
    QWidget,
)

from rat.ui.theme import CHAT_COLORS

MARKDOWN_FEATURES = QTextDocument.MarkdownFeature.MarkdownDialectGitHub | QTextDocument.MarkdownFeature.MarkdownNoHTML


def reply_plain_text(text: str) -> str:
    document = QTextDocument()
    document.setMarkdown(text, MARKDOWN_FEATURES)
    return document.toPlainText()


def parse_code_blocks(text: str) -> List[Dict[str, Any]]:
    """Parse fenced code blocks (``` or ~~~), capturing language, content, and closure status."""
    pattern = re.compile(r"(?m)^([`~]{3,})([a-zA-Z0-9_\-\.\+]*)[ \t]*\r?\n")
    blocks: List[Dict[str, Any]] = []
    pos = 0
    while True:
        m = pattern.search(text, pos)
        if not m:
            break
        fence, lang = m.group(1), m.group(2).strip()
        fence_char = fence[0]
        fence_len = len(fence)
        content_start = m.end()
        close_pat = re.compile(r"(?m)^" + re.escape(fence_char) + r"{" + str(fence_len) + r",}[ \t]*$")
        close_m = close_pat.search(text, content_start)
        if close_m:
            code = text[content_start:close_m.start()]
            if code.endswith("\n"):
                code = code[:-1]
            if code.endswith("\r"):
                code = code[:-1]
            blocks.append({
                "lang": lang,
                "code": code,
                "closed": True,
                "start": m.start(),
                "end": close_m.end(),
            })
            pos = close_m.end()
        else:
            code = text[content_start:]
            blocks.append({
                "lang": lang,
                "code": code,
                "closed": False,
                "start": m.start(),
                "end": len(text),
            })
            break
    return blocks


def space_reply_document(document: QTextDocument) -> None:
    """Use real paragraph spacing, shared by quick reading and full conversation."""
    block = document.begin()
    while block.isValid():
        cursor = QTextCursor(block)
        block_format = block.blockFormat()
        block_format.setLineHeight(140, QTextBlockFormat.LineHeightTypes.ProportionalHeight.value)
        block_format.setNonBreakableLines(False)
        block_format.setTopMargin(8 if block_format.headingLevel() and block.previous().isValid() else 0)
        block_format.setBottomMargin(3 if block.textList() else 8)

        # Code block line styling
        is_code = block_format.hasProperty(4241) or block_format.hasProperty(4240)
        if is_code:
            block_format.setBackground(QColor("#F7F3EC"))
            block_format.setLeftMargin(8.0)
            block_format.setRightMargin(8.0)
            cursor.setBlockFormat(block_format)

            char_fmt = block.charFormat()
            char_fmt.setFontFamilies(["SF Mono", "Menlo", "Consolas", "Courier New", "monospace"])
            char_fmt.setFontPointSize(12.0)
            cursor.select(QTextCursor.SelectionType.BlockUnderCursor)
            cursor.mergeCharFormat(char_fmt)
        else:
            cursor.setBlockFormat(block_format)

        block = block.next()

    # Table styling: header row background #EFE8DC, padding >= 6px, thin border #E9E1D5, numeric right-aligned
    for frame in document.rootFrame().childFrames():
        if isinstance(frame, QTextTable):
            table = frame
            fmt = table.format()
            fmt.setCellPadding(6.0)
            fmt.setCellSpacing(0.0)
            fmt.setBorder(1.0)
            fmt.setBorderStyle(QTextFrameFormat.BorderStyle.BorderStyle_Solid)
            fmt.setBorderBrush(QColor("#E9E1D5"))
            table.setFormat(fmt)

            rows = table.rows()
            cols = table.columns()
            for r in range(rows):
                for c in range(cols):
                    cell = table.cellAt(r, c)
                    cfmt = cell.format().toTableCellFormat()
                    cfmt.setTopPadding(6.0)
                    cfmt.setBottomPadding(6.0)
                    cfmt.setLeftPadding(8.0)
                    cfmt.setRightPadding(8.0)
                    cfmt.setBottomBorder(1.0)
                    cfmt.setBottomBorderStyle(QTextFrameFormat.BorderStyle.BorderStyle_Solid)
                    cfmt.setBottomBorderBrush(QColor("#E9E1D5"))

                    if r == 0:
                        cfmt.setBackground(QColor("#EFE8DC"))
                    else:
                        cfmt.setBackground(QColor("#FFFDFA"))
                    cell.setFormat(cfmt)

                    cur = cell.firstCursorPosition()
                    b = cur.block()
                    text = b.text().strip()
                    clean = text.replace(".", "").replace(",", "").replace("%", "").replace("+", "").replace("-", "")
                    bf = b.blockFormat()
                    if clean.isdigit():
                        bf.setAlignment(Qt.AlignmentFlag.AlignRight)
                    else:
                        bf.setAlignment(Qt.AlignmentFlag.AlignLeft)
                    cur.setBlockFormat(bf)

                    if r == 0:
                        char_cur = cell.firstCursorPosition()
                        char_cur.select(QTextCursor.SelectionType.BlockUnderCursor)
                        char_fmt = char_cur.charFormat()
                        char_fmt.setFontWeight(600)
                        char_cur.mergeCharFormat(char_fmt)


class CodeBlockBadge(QFrame):
    """Header badge for a code block: shows language tag and 'Chép code' button for closed blocks."""
    copied = pyqtSignal()

    def __init__(self, language: str, code: str, is_closed: bool, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.code = code
        self.is_closed = is_closed
        self.setObjectName("CodeBlockBadge")
        self.setStyleSheet("""
            QFrame#CodeBlockBadge {
                background: rgba(247, 243, 236, 0.94);
                border: 1px solid #E9E1D5;
                border-radius: 4px;
            }
            QLabel {
                color: #8C8275;
                font-size: 10px;
                font-weight: 600;
                background: transparent;
                border: none;
                padding-right: 2px;
            }
            QPushButton {
                background: transparent;
                border: 1px solid transparent;
                border-radius: 3px;
                color: #6B6258;
                font-size: 10px;
                font-weight: 500;
                padding: 1px 6px;
            }
            QPushButton:hover {
                background: #E8E0D2;
                color: #1F1A16;
            }
        """)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 2, 5, 2)
        layout.setSpacing(4)

        if language:
            lbl_lang = QLabel(language.lower())
            layout.addWidget(lbl_lang)

        if is_closed:
            self.copy_btn = QPushButton("Chép code")
            self.copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.copy_btn.setToolTip("Sao chép đoạn mã này")
            self.copy_btn.clicked.connect(self._copy_code)
            layout.addWidget(self.copy_btn)

            self._reset_timer = QTimer(self)
            self._reset_timer.setSingleShot(True)
            self._reset_timer.timeout.connect(lambda: self.copy_btn.setText("Chép code"))
        else:
            self.copy_btn = None

    def _copy_code(self) -> None:
        if not self.code:
            return
        QApplication.clipboard().setText(self.code)
        if self.copy_btn:
            self.copy_btn.setText("Đã chép")
            self._reset_timer.start(1500)
        self.copied.emit()
        win = self.window()
        if hasattr(win, "show_toast"):
            win.show_toast("Đã sao chép đoạn mã")


class ReplyTextBrowser(QTextBrowser):
    def loadResource(self, resource_type, name):
        # Model output is text, not permission to fetch an image or read a file.
        return None


class ConversationReplyBody(ReplyTextBrowser):
    """All content is in the outer stream: no nested scrolling or HTML resources."""
    wheel_scrolled = pyqtSignal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._raw_text = ""
        self._rendered_text = ""
        self.setObjectName("ConversationReplyBody")
        self.setAccessibleName("Câu trả lời của Chuột")
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setReadOnly(True)
        self.setTabChangesFocus(True)
        self.setWordWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setOpenLinks(False)
        self.setOpenExternalLinks(False)
        self.anchorClicked.connect(self._open_link)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.setStyleSheet(f"""
            QTextBrowser#ConversationReplyBody {{ background: transparent; border: none;
                padding: 0; color: {CHAT_COLORS['ink']}; font-size: 13px;
                selection-background-color: #E8DABC; }}
        """)
        font = self.font()
        font.setPixelSize(13)
        self.setFont(font)
        self.document().setDocumentMargin(0)
        self.setFixedHeight(24)
        self._height_timer = QTimer(self)
        self._height_timer.setSingleShot(True)
        self._height_timer.timeout.connect(self._sync_height)
        self.document().documentLayout().documentSizeChanged.connect(self._schedule_height)

        self._code_badges: List[CodeBlockBadge] = []
        self._code_rects: List[QRectF] = []
        self._coalesce_timer = QTimer(self)
        self._coalesce_timer.setSingleShot(True)
        self._coalesce_timer.setInterval(35)
        self._coalesce_timer.timeout.connect(self._flush_render)
        self._pending_raw_text: Optional[str] = None

    def text(self) -> str:
        # Keep the stream handle's raw-text API, including exact copy content.
        return self._raw_text

    def setText(self, text: str) -> None:
        if self._coalesce_timer.isActive():
            self._coalesce_timer.stop()
        self._pending_raw_text = None
        if text == self._raw_text and self._raw_text == self._rendered_text:
            return
        self._raw_text = text
        self._render_text()

    def set_stream_text(self, text: str) -> None:
        """Coalesce streaming tokens into ~35ms intervals to avoid per-token layout reflow."""
        if text == self._raw_text:
            return
        self._raw_text = text
        self._pending_raw_text = text
        if not self._coalesce_timer.isActive():
            self._coalesce_timer.start()

    def flush(self) -> None:
        """Immediately render any buffered streaming content without waiting for timer."""
        if self._coalesce_timer.isActive():
            self._coalesce_timer.stop()
        if self._pending_raw_text is not None or self._raw_text != self._rendered_text:
            self._flush_render()

    def _flush_render(self) -> None:
        self._pending_raw_text = None
        self._render_text()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._render_text()
        self._schedule_height()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._sync_code_badges()
        if hasattr(self, "_height_timer"):
            self._schedule_height()

    def _render_text(self) -> None:
        if self._raw_text == self._rendered_text:
            return
        previous = self._rendered_text
        cursor = self.textCursor()
        selection = (cursor.anchor(), cursor.position())
        self.document().setMarkdown(self._raw_text, MARKDOWN_FEATURES)
        space_reply_document(self.document())
        self._rendered_text = self._raw_text
        cursor = self.textCursor()
        if previous and self._raw_text.startswith(previous):
            end = self.document().characterCount() - 1
            cursor.setPosition(min(selection[0], end))
            cursor.setPosition(min(selection[1], end), QTextCursor.MoveMode.KeepAnchor)
        else:
            cursor.movePosition(QTextCursor.MoveOperation.Start)
        self.setTextCursor(cursor)
        self._sync_code_badges()
        self._schedule_height()

    def _sync_code_badges(self) -> None:
        for badge in self._code_badges:
            badge.deleteLater()
        self._code_badges.clear()
        self._code_rects.clear()

        code_blocks = parse_code_blocks(self._raw_text)
        if not code_blocks:
            self.update()
            return

        doc_layout = self.document().documentLayout()
        viewport_w = self.viewport().width()

        for cb in code_blocks:
            first_line = cb["code"].split("\n")[0] if cb["code"] else ""
            block = self.document().begin()
            start_rect = None
            end_rect = None
            while block.isValid():
                is_code = block.blockFormat().hasProperty(4241) or block.blockFormat().hasProperty(4240)
                if is_code:
                    brect = doc_layout.blockBoundingRect(block)
                    if start_rect is None and (not first_line or first_line in block.text()):
                        start_rect = brect
                    if start_rect is not None:
                        end_rect = brect
                elif start_rect is not None:
                    break
                block = block.next()

            if start_rect is not None and end_rect is not None:
                top = start_rect.top()
                bottom = end_rect.bottom()
                crect = QRectF(4.0, top - 2.0, max(100.0, viewport_w - 8.0), max(24.0, bottom - top + 4.0))
                self._code_rects.append(crect)

                badge = CodeBlockBadge(cb["lang"], cb["code"], cb["closed"], self.viewport())
                badge.adjustSize()
                badge.move(int(viewport_w - badge.width() - 10), int(top + 2))
                badge.show()
                self._code_badges.append(badge)

        self.update()

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        if self._code_rects:
            painter = QPainter(self.viewport())
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            pen = QPen(QColor("#E9E1D5"), 1.0)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            for r in self._code_rects:
                painter.drawRoundedRect(r, 6.0, 6.0)

    def _schedule_height(self, *args) -> None:
        self._height_timer.start(0)

    def _sync_height(self) -> None:
        self.document().setTextWidth(max(1, self.viewport().width()))
        height = max(20, math.ceil(self.document().size().height()) + 2)
        if self.height() != height:
            self.setFixedHeight(height)

    def wheelEvent(self, event) -> None:
        # QAbstractScrollArea does not bubble wheel events through another one.
        # Forward synchronously to the outer stream; never create an inner scroll.
        event.ignore()
        self.wheel_scrolled.emit(event)

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key.Key_PageUp, Qt.Key.Key_PageDown) and not event.modifiers():
            event.ignore()
            return
        super().keyPressEvent(event)

    @staticmethod
    def _open_link(url) -> None:
        if url.scheme().lower() in ("http", "https"):
            QDesktopServices.openUrl(url)
