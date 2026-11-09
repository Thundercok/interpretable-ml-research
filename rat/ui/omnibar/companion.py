"""
rat.ui.omnibar.companion — Presentation and interaction widgets for the Rat Mascot companion.
Includes ArtisticSpeechBubble, PeekingRatMascot, CompanionAvatarButton,
ConversationRibbon, ResetConfirmationDialog, and RatCompanionStage.
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any, Optional, TYPE_CHECKING

from PyQt6.QtCore import (
    QAbstractAnimation,
    QEasingCurve,
    QParallelAnimationGroup,
    QPoint,
    QPointF,
    QPropertyAnimation,
    QRect,
    QRectF,
    Qt,
    QTimer,
    pyqtProperty,
    pyqtSignal,
)
from PyQt6.QtGui import (
    QColor,
    QFont,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from rat.ui.chat_stream import get_mascot_pixmap
from rat.ui.reply_reader import reply_plain_text
from rat.ui.theme import CHAT_ACTION_QSS, CHAT_COLORS, CONVERSATION_RIBBON_QSS

logger = logging.getLogger('rat.ui.omnibar.companion')

if TYPE_CHECKING:
    from .window import OmnibarWindow


class ArtisticSpeechBubble(QFrame):
    """
    Floating Overlay Speech Bubble Component (Independent Layer).
    - Whimsical comic speech bubble with organic bezier tail locked to Chuột's snout.
    - Quiet header with human status and actions only where they are useful.
    - WordWrap with smooth height adjustment.
    - Opaque warm paper, so desktop content never bleeds through a reply.
    """

    def __init__(self, window: "OmnibarWindow", parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.window = window
        self.setObjectName("RatSpeechBubble")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedWidth(460)
        self.tail_y = 46
        self._bubble_height = 92
        self.setFixedHeight(92)

        self._opacity_effect: Optional[QGraphicsOpacityEffect] = None
        self._height_anim: Optional[QPropertyAnimation] = None
        self._full_reply = ""
        self._copy_text = ""
        self._expanded = False
        self._truncated = False
        self._has_details = False
        self._file_summary = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 10, 16, 10)
        layout.setSpacing(6)

        # 1. Header Meta Row (clean, no distracting buttons)
        header = QHBoxLayout()
        header.setSpacing(6)

        self.dot = QLabel("●")
        self.dot.setStyleSheet("font-size: 8px; color: #F59E0B; margin-top: 1px;")
        header.addWidget(self.dot)

        self.name_tag = QLabel("Chuột")
        self.name_tag.setStyleSheet("font-size: 11px; font-weight: 600; color: #6F6456;")
        header.addWidget(self.name_tag)

        self.context_pill = QLabel("Sẵn sàng")
        self.context_pill.setStyleSheet("font-size: 10px; font-weight: 400; color: #7C7469; padding: 1px 5px;")
        header.addWidget(self.context_pill)

        header.addStretch()
        action_style = """
            QPushButton {
                background: transparent; border: none; border-radius: 4px;
                color: #6B6258; font-size: 10px; padding: 2px 5px;
            }
            QPushButton:hover { background: #F3EFE8; color: #1F1A16; }
        """
        self.btn_copy = QPushButton("Sao chép", self)
        self.btn_copy.setStyleSheet(action_style)
        self.btn_copy.setToolTip("Sao chép toàn bộ đáp án (⌘C)")
        self.btn_copy.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_copy.clicked.connect(self._on_copy_clicked)
        self.btn_copy.hide()
        header.addWidget(self.btn_copy)
        self.btn_hist = QPushButton("Đọc hết", self)
        self.btn_hist.setStyleSheet(action_style)
        self.btn_hist.setToolTip("Mở câu trả lời đầy đủ ngay tại đây")
        self.btn_hist.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_hist.clicked.connect(self.window.read_full_reply)
        self.btn_hist.hide()
        header.addWidget(self.btn_hist)
        layout.addLayout(header)

        # 2. Main Dialogue Text
        self.dialogue = QLabel("Nghe đây. Cần gì?", self)
        self.dialogue.setStyleSheet("font-size: 13px; font-weight: 400; color: #302B24;")
        self.dialogue.setWordWrap(True)
        self.dialogue.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.dialogue)

    @pyqtProperty(int)
    def bubbleHeight(self) -> int:
        return self.height()

    @bubbleHeight.setter
    def bubbleHeight(self, val: int) -> None:
        self.setFixedHeight(val)
        self.update()

    def update_target_height(self, animated: bool = True) -> None:
        """Calculate needed height and smoothly animate size without jitter (100ms - 150ms)."""
        fm = self.dialogue.fontMetrics()
        text = self.dialogue.text()
        rect = fm.boundingRect(QRect(0, 0, 420, 10000), Qt.TextFlag.TextWordWrap, text)
        text_h = max(20, rect.height())
        # Keep the reply inside the existing 120px mascot/bubble headroom.
        target_h = max(76, min(112, text_h + 46))

        if not animated or not self.isVisible():
            self.setFixedHeight(target_h)
            return

        if not self._height_anim:
            self._height_anim = QPropertyAnimation(self, b"bubbleHeight")
            self._height_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        if self.height() != target_h:
            self._height_anim.stop()
            self._height_anim.setDuration(120)
            self._height_anim.setStartValue(self.height())
            self._height_anim.setEndValue(target_h)
            self._height_anim.start()

    @property
    def has_reply(self) -> bool:
        return bool(self._copy_text.strip())

    def _fit_reply(self, text: str) -> str:
        """Fit a preview to the bubble, retaining the full reply separately."""
        fm = self.dialogue.fontMetrics()

        def fits(candidate: str) -> bool:
            rect = fm.boundingRect(QRect(0, 0, 420, 10000), Qt.TextFlag.TextWordWrap, candidate)
            return rect.height() <= fm.lineSpacing() * 3 and rect.width() <= 420

        if fits(text):
            return text
        low, high = 0, len(text)
        while low < high:
            mid = (low + high + 1) // 2
            if fits(text[:mid].rstrip() + "…"):
                low = mid
            else:
                high = mid - 1
        prefix = text[:low].rstrip()
        boundary = prefix.rfind(" ")
        if boundary > len(prefix) * 0.7:
            prefix = prefix[:boundary].rstrip()
        return prefix + "…"

    def set_reply(
        self,
        text: str,
        context_text: Optional[str] = None,
        *,
        copy_text: Optional[str] = None,
        has_details: bool = False,
        file_summary: bool = False,
    ) -> None:
        self._full_reply = text.strip()
        self._copy_text = text if copy_text is None else copy_text
        self._has_details = has_details
        self._file_summary = file_summary
        # Show a few readable lines, not every paragraph flattened into a wall of text.
        preview_source = reply_plain_text(self._full_reply).strip()
        preview_source = re.sub(r"\n[ \t]*\n+", "\n", preview_source)
        preview = self._fit_reply(preview_source)
        structured = bool(re.search(r"(?m)^(?:#{1,6} |[-*+] |\d+[.)] |>|```)", self._copy_text))
        self._truncated = preview != preview_source or structured or "\n\n" in self._full_reply
        self.dialogue.setText(preview)
        self.btn_copy.setVisible(self.has_reply and not file_summary)
        self.btn_hist.setVisible(self.has_reply and not file_summary and (self._truncated or self._has_details or self._expanded))
        self.btn_hist.setText("Thu gọn" if self._expanded else "Xem kết quả" if has_details else "Đọc hết")
        if context_text:
            self.context_pill.setText(context_text)
        self.update_target_height(animated=True)

    def _on_copy_clicked(self) -> None:
        if self.has_reply:
            QApplication.clipboard().setText(self._copy_text)
            self.window.show_toast("Đã sao chép toàn bộ đáp án")

    def setText(self, text: str) -> None:
        self.set_reply(text)

    def text(self) -> str:
        return self._full_reply or self.dialogue.text()

    def stream_token(self, token: str) -> None:
        self.set_reply(self._copy_text + token, "Đang gõ")

    def reset_welcome(self, message: str = "Nghe đây. Cần gì?") -> None:
        self._full_reply = ""
        self._copy_text = ""
        self._truncated = False
        self._has_details = False
        self._file_summary = False
        self.btn_copy.hide()
        self.btn_hist.hide()
        self.dialogue.setText(message)
        self.context_pill.setText("Sẵn sàng")
        self.update_target_height(animated=False)

    def set_expanded_mode(self, is_expanded: bool) -> None:
        self._expanded = is_expanded
        self.btn_hist.setText("Thu gọn" if is_expanded else "Xem kết quả" if self._has_details else "Đọc hết")
        self.btn_hist.setVisible(self.has_reply and not self._file_summary and (self._truncated or self._has_details or is_expanded))

    def show_bubble(self) -> None:
        self.show()
        self.raise_()
        self.update_target_height(animated=False)

    def hide_bubble(self) -> None:
        self.hide()

    def resizeEvent(self, event: Any) -> None:
        super().resizeEvent(event)
        if getattr(self.window, "speech_bubble", None) is self:
            self.window._position_reply_bubble()

    def paintEvent(self, e: Any) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        tail_w = 12
        tail_h = 14
        tail_y = float(getattr(self, "tail_y", 30))

        w = self.width() - 4
        h = self.height() - 4
        r = 14

        path = QPainterPath()
        path.moveTo(2 + tail_w + r, 2)
        path.lineTo(2 + w - r, 2)
        path.quadTo(2 + w, 2, 2 + w, 2 + r)
        path.lineTo(2 + w, 2 + h - r)
        path.quadTo(2 + w, 2 + h, 2 + w - r, 2 + h)
        path.lineTo(2 + tail_w + r, 2 + h)
        path.quadTo(2 + tail_w, 2 + h, 2 + tail_w, 2 + h - r)

        # Organic smooth bezier tail pointing to Chuột
        path.lineTo(2 + tail_w, tail_y + tail_h)
        tip_x = 2.0
        tip_y = tail_y + tail_h * 0.45
        path.quadTo(2 + tail_w * 0.4, tail_y + tail_h * 0.85, tip_x, tip_y)
        path.quadTo(2 + tail_w * 0.35, tail_y + tail_h * 0.15, 2 + tail_w, tail_y)

        path.lineTo(2 + tail_w, 2 + r)
        path.quadTo(2 + tail_w, 2, 2 + tail_w + r, 2)
        path.closeSubpath()

        # One opaque paper surface, without duplicate shadow outlines or text bleed.
        painter.setBrush(QColor("#FFFDFA"))
        painter.setPen(QPen(QColor("#DDD7CD"), 1.0))
        painter.drawPath(path)


ComicSpeechFrame = ArtisticSpeechBubble


class CompanionAvatarButton(QPushButton):
    """
    Tactile Companion Avatar button located right inside the search input / composer bar.
    Renders Chuột's expressive bust with dynamic overhead badges:
    - 'idle': Calm, friendly, ready
    - 'searching': Magnifying glass 🔍
    - 'thinking': Animated spinning loading ring + 💭
    - 'angry': Comic angry vein mark 💢
    """

    def __init__(self, window: "OmnibarWindow", parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.window = window
        self.setFixedSize(34, 34)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Chuột đồng hành · Nhấp để trò chuyện hoặc chọc giận!")
        self.current_state = "idle"
        self._spin_angle = 0
        self._spin_timer = QTimer(self)
        self._spin_timer.timeout.connect(self._on_spin_tick)
        self._click_count = 0
        self._last_click_time = 0.0
        self.clicked.connect(self._on_clicked)

        # Pre-load mascot bust pixmap
        self._bust_pm = get_mascot_pixmap(24, 24, bust_only=True)

    def _on_spin_tick(self) -> None:
        self._spin_angle = (self._spin_angle + 25) % 360
        self.update()

    def set_state(self, state: str) -> None:
        self.current_state = state
        if state == "thinking":
            if not self._spin_timer.isActive():
                self._spin_timer.start(40)
        else:
            if self._spin_timer.isActive():
                self._spin_timer.stop()
        self.update()

    def _on_clicked(self) -> None:
        now = time.time()
        if now - self._last_click_time < 1.5:
            self._click_count += 1
        else:
            self._click_count = 1
        self._last_click_time = now

        if self._click_count >= 3:
            # Angry reaction!
            self.window.set_mascot_state("angry", "Ừ, tôi vẫn ở đây. Ô nhập cũng ở ngay bên cạnh đấy.")
            QTimer.singleShot(4000, lambda: self.window.set_mascot_state("idle"))
        else:
            quotes = [
                "Nghe đây. Cần gì?",
                "Ừ, tôi đang nghe. Cứ gõ đi.",
                "Có mặt. Không cần điểm danh lần nữa đâu.",
                "Đưa câu hỏi đây, mình gỡ từng ý.",
            ]
            q = quotes[self._click_count % len(quotes)]
            self.window.set_mascot_state("speaking" if not self.window.is_expanded else "idle", q)

    def paintEvent(self, event: Any) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        # Background capsule
        p.setBrush(QColor("#F8F5EE"))
        p.setPen(QPen(QColor("#E2D7C7"), 1.5))
        p.drawRoundedRect(1, 1, 32, 32, 16, 16)

        # Mascot face
        if self._bust_pm and not self._bust_pm.isNull():
            fx = (self.width() - self._bust_pm.width()) // 2
            fy = (self.height() - self._bust_pm.height()) // 2 + 1
            p.drawPixmap(fx, fy, self._bust_pm)

        # State badge
        st = self.current_state
        if st == "thinking":
            p.save()
            p.translate(24, 8)
            p.rotate(self._spin_angle)
            pen = QPen(QColor("#F59E0B"), 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
            p.setPen(pen)
            p.drawArc(QRectF(-5, -5, 10, 10), 0, 270 * 16)
            p.restore()
        elif st == "searching":
            p.setFont(QFont("Apple Color Emoji", 11))
            p.drawText(QRectF(17, 0, 16, 16), Qt.AlignmentFlag.AlignCenter, "🔍")
        elif st == "angry":
            p.setFont(QFont("Apple Color Emoji", 12))
            p.drawText(QRectF(17, -1, 16, 16), Qt.AlignmentFlag.AlignCenter, "💢")
        p.end()


class ResetConfirmationDialog(QDialog):
    """Small confirmation modal before clearing conversation history or drafts."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("ResetConfirmationDialog")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setModal(True)
        self.setFixedSize(360, 130)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        card = QFrame(self)
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {CHAT_COLORS['paper']};
                border: 1px solid {CHAT_COLORS['border']};
                border-radius: 12px;
            }}
            QLabel {{
                background: transparent;
                border: none;
                color: {CHAT_COLORS['ink']};
            }}
        """)
        c_layout = QVBoxLayout(card)
        c_layout.setContentsMargins(16, 14, 16, 12)
        c_layout.setSpacing(12)

        title = QLabel("Xoá cuộc trò chuyện và bản nháp này?")
        title.setStyleSheet("font-size: 13px; font-weight: 600; color: #302B24;")
        title.setWordWrap(True)
        c_layout.addWidget(title)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        btn_row.addStretch()

        self.btn_keep = QPushButton("Giữ lại")
        self.btn_keep.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_keep.setStyleSheet(CHAT_ACTION_QSS)
        self.btn_keep.setAutoDefault(True)
        self.btn_keep.setDefault(True)
        self.btn_keep.clicked.connect(self.reject)
        btn_row.addWidget(self.btn_keep)

        self.btn_clear = QPushButton("Xoá phiên")
        self.btn_clear.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_clear.setStyleSheet("""
            QPushButton {
                background: #FEE2E2;
                border: 1px solid #FCA5A5;
                border-radius: 6px;
                color: #991B1B;
                font-size: 11px;
                font-weight: 600;
                min-height: 28px;
                padding: 3px 12px;
            }
            QPushButton:hover {
                background: #FECACA;
                color: #7F1D1D;
            }
            QPushButton:pressed {
                background: #FCA5A5;
            }
            QPushButton:focus {
                border-color: #B49A6B;
            }
        """)
        self.btn_clear.setAutoDefault(True)
        self.btn_clear.clicked.connect(self.accept)
        btn_row.addWidget(self.btn_clear)

        c_layout.addLayout(btn_row)
        layout.addWidget(card)
        self.btn_keep.setFocus()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.reject()
            return
        super().keyPressEvent(event)


class ConversationRibbon(QFrame):
    """
    Tactile, minimalist conversation ribbon.
    Shows the active session tag (#c-xxxx · DD/MM · HH:MM), turn counter,
    and a clean reset button to clear history with a cheeky remark.
    """
    reset_requested = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("ConversationRibbon")
        self.setStyleSheet(CONVERSATION_RIBBON_QSS)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 4, 8, 4)
        layout.setSpacing(8)

        self.tag_label = QLabel("#c-0000 · Hôm nay")
        self.tag_label.setObjectName("RibbonTag")
        layout.addWidget(self.tag_label)

        self.turn_badge = QLabel("Lượt 1")
        self.turn_badge.setObjectName("RibbonTurnBadge")
        self.turn_badge.hide()
        layout.addWidget(self.turn_badge)

        layout.addStretch()

        self.clear_btn = QPushButton("✕ Xoá phiên")
        self.clear_btn.setObjectName("RibbonClearBtn")
        self.clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_btn.setToolTip("Xoá ngữ cảnh cuộc trò chuyện và bắt đầu phiên mới (⌘N hoặc /clear)")
        self.clear_btn.setAccessibleName("Xoá phiên cuộc trò chuyện")
        self.clear_btn.clicked.connect(self.reset_requested)
        layout.addWidget(self.clear_btn)

    def set_session_info(self, tag: str, turn_count: int = 0) -> None:
        self.tag_label.setText(tag)
        if turn_count > 0:
            self.turn_badge.setText(f"{turn_count} lượt")
            self.turn_badge.show()
        else:
            self.turn_badge.hide()


class PeekingRatMascot(QWidget):
    """
    Desktop Mascot Character with 'Núp hở mắt/tay & Pop-out xéo' animation.
    1. Z-INDEX & BÁM GỜ CHATBOX:
       - Layer immediately BEHIND Chatbox card (stackUnder).
       - IDLE (Núp): Tọa độ Y thụt xuống sao cho Chatbox che gần hết,
         CHỈ ĐỂ HỞ: Đôi mắt trố và 2 bàn tay đang bám trên gờ mép Chatbox.
         Góc xoay (Rotation angle): 0 degree.
    2. ANIMATION POP-OUT XÉO (DIAGONAL POP-OUT):
       - Kích hoạt SPEAKING: Animation kết hợp 3 thông số:
         Trượt trục Y (lên trên), Trượt trục X (nhích sang bên 20px),
         và Xoay nghiêng góc (Rotation: +10°).
       - Hiệu ứng nảy nhẹ (QEasingCurve.Type.OutBack, ~350ms duration) khi trượt ra.
       - Toàn thân con chuột được lộ ra trọn vẹn ở góc nghiêng này.
    3. HIỂN THỊ SPEECH BUBBLE:
       - Bong bóng thoại xuất hiện ngay sau khi con chuột hoàn thành animation ló xéo.
       - Đuôi bong bóng thoại chỉ thẳng vào đầu con chuột đang nằm ở vị trí nghiêng đó.
    """
    speaking_popped_out = pyqtSignal()
    idle_retreated = pyqtSignal()

    def __init__(self, window: "OmnibarWindow", parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.window = window
        self.setObjectName("PeekingMascot")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self.current_state = "idle"
        self._spin_angle = 0
        self._spin_timer = QTimer(self)
        self._spin_timer.timeout.connect(self._on_spin_tick)

        self._rotation: float = 0.0
        self.is_speaking: bool = False
        self.side_docked = False

        # Load mascot cutout sprite (scaled to 124x124 inside 146x146 canvas so rotation never clips)
        pm = get_mascot_pixmap(124, 124, bust_only=True)
        self._mascot_bust_pixmap = pm if (pm and not pm.isNull()) else QPixmap()
        full = get_mascot_pixmap(124, 124, bust_only=False)
        self._mascot_full_pixmap = full if (full and not full.isNull()) else self._mascot_bust_pixmap
        self._mascot_pixmap = self._mascot_bust_pixmap

        self.setFixedSize(146, 146)

        # Coordinate anchors (container top rim is at y=120)
        self.x_idle = 24
        self.y_idle = 8           # paws at bottom of bust rest right at y=120 on rim
        self.x_speaking = 44      # +20px per spec
        self.y_speaking = 2       # nhấc lên một chút
        self.rot_idle = 0.0       # 0 degree khi núp
        self.rot_speaking = 10.0  # +10 degree tilt khi nói

        # Parallel animation group for smooth synchronous transform
        self._anim_group = QParallelAnimationGroup(self)

        self._pos_anim = QPropertyAnimation(self, b"pos")
        self._pos_anim.setDuration(350)

        self._rot_anim = QPropertyAnimation(self, b"rotation")
        self._rot_anim.setDuration(350)

        self._anim_group.addAnimation(self._pos_anim)
        self._anim_group.addAnimation(self._rot_anim)
        self._anim_group.finished.connect(self._on_animation_finished)

    @pyqtProperty(float)
    def rotation(self) -> float:
        return self._rotation

    @rotation.setter
    def rotation(self, val: float) -> None:
        self._rotation = val
        self.update()

    def set_anchors(self, container_x: int, container_y: int, *, side: bool = False,
                    container_bottom: Optional[int] = None, animated: bool = False) -> None:
        """Top rim in quick mode; a reserved left gutter in full mode."""
        cx = container_x if container_x > 0 else 16
        cy = container_y if container_y > 20 else 120
        mode_changed = self.side_docked != side
        self.side_docked = side
        # At the rim the bust is partly hidden; at the side show feet and tail.
        self._mascot_pixmap = self._mascot_full_pixmap if side else self._mascot_bust_pixmap
        if side:
            bottom = container_bottom if container_bottom is not None else self.window.height() - 16
            self.x_idle = max(4, cx - self.width() - 4)
            self.y_idle = max(24, bottom - self.height() - 56)
            self.x_speaking = max(4, self.x_idle - 6)
            self.y_speaking = max(16, self.y_idle - 8)
            self.rot_speaking = 4.0
        else:
            self.x_idle = cx + 8
            self.y_idle = max(2, cy - 112)
            self.x_speaking = self.x_idle + 20
            self.y_speaking = max(2, self.y_idle - 6)
            self.rot_speaking = 10.0
        target = QPoint(self.x_speaking, self.y_speaking) if self.is_speaking else QPoint(self.x_idle, self.y_idle)
        rotation = self.rot_speaking if self.is_speaking else self.rot_idle
        if mode_changed and animated:
            self._anim_group.stop()
            for animation in (self._pos_anim, self._rot_anim):
                animation.setDuration(350)
                animation.setEasingCurve(QEasingCurve.Type.OutBack if side else QEasingCurve.Type.OutCubic)
            self._pos_anim.setStartValue(self.pos())
            self._pos_anim.setEndValue(target)
            self._rot_anim.setStartValue(self.rotation)
            self._rot_anim.setEndValue(rotation)
            self._anim_group.start()
        elif self._anim_group.state() == QAbstractAnimation.State.Running:
            # Window geometry animates too: update the destination, not the pose.
            self._pos_anim.setEndValue(target)
            self._rot_anim.setEndValue(rotation)
        else:
            self.move(target)
            self._rotation = rotation
        self.update()

    def pop_out_speaking(self) -> None:
        """Diagonal pop-out animation (~350ms, OutBack easing)."""
        self.is_speaking = True
        self._anim_group.stop()

        self._pos_anim.setDuration(350)
        self._pos_anim.setEasingCurve(QEasingCurve.Type.OutBack)
        self._pos_anim.setStartValue(self.pos())
        self._pos_anim.setEndValue(QPoint(self.x_speaking, self.y_speaking))

        self._rot_anim.setDuration(350)
        self._rot_anim.setEasingCurve(QEasingCurve.Type.OutBack)
        self._rot_anim.setStartValue(self._rotation)
        self._rot_anim.setEndValue(self.rot_speaking)

        self._anim_group.start()

    def retreat_to_idle(self) -> None:
        """Retreat back to hiding/idle position (eyes & paws peeking only, 0 deg)."""
        self.is_speaking = False
        self._anim_group.stop()

        self._pos_anim.setDuration(300)
        self._pos_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._pos_anim.setStartValue(self.pos())
        self._pos_anim.setEndValue(QPoint(self.x_idle, self.y_idle))

        self._rot_anim.setDuration(300)
        self._rot_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._rot_anim.setStartValue(self._rotation)
        self._rot_anim.setEndValue(self.rot_idle)

        self._anim_group.start()

    def _on_animation_finished(self) -> None:
        if self.is_speaking:
            self.speaking_popped_out.emit()
        else:
            self.idle_retreated.emit()

    def _on_spin_tick(self) -> None:
        self._spin_angle = (self._spin_angle + 25) % 360
        self.update()

    def set_state(self, state: str) -> None:
        self.current_state = state
        if state == "thinking":
            if not self._spin_timer.isActive():
                self._spin_timer.start(40)
        else:
            if self._spin_timer.isActive():
                self._spin_timer.stop()
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            if hasattr(self.window, "on_mascot_clicked"):
                self.window.on_mascot_clicked()

    def _draw_ink_glasses(self, p: QPainter, draw_x: int, draw_y: int, pm_w: int, pm_h: int) -> None:
        """Procedural ink spectacles for math, reasoning, and PAL computations."""
        if getattr(self, "side_docked", False):
            # Full-body mascot has smaller head at top of body
            lx = draw_x + int(pm_w * 0.14)
            ly = draw_y + int(pm_h * 0.15)
            lw = int(pm_w * 0.14)
            lh = int(pm_h * 0.22)

            rx = draw_x + int(pm_w * 0.33)
            ry = draw_y + int(pm_h * 0.20)
            rw = int(pm_w * 0.22)
            rh = int(pm_h * 0.22)
            temple_x2 = draw_x + int(pm_w * 0.62)
            temple_y2 = ry + int(rh * 0.20)
            bridge_y = ly + int(lh * 0.60)
            bridge_y2 = ry + int(rh * 0.50)
        else:
            # Peeking bust mascot (zoomed head)
            lx = draw_x + int(pm_w * 0.15)
            ly = draw_y + int(pm_h * 0.24)
            lw = int(pm_w * 0.24)
            lh = int(pm_h * 0.36)

            rx = draw_x + int(pm_w * 0.43)
            ry = draw_y + int(pm_h * 0.30)
            rw = int(pm_w * 0.36)
            rh = int(pm_h * 0.38)
            temple_x2 = draw_x + int(pm_w * 0.88)
            temple_y2 = ry + int(rh * 0.32)
            bridge_y = ly + int(lh * 0.58)
            bridge_y2 = ry + int(rh * 0.52)

        # Frame with ink pen
        pen_frame = QPen(QColor("#1F1A16"), 2.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        p.setPen(pen_frame)
        p.setBrush(QColor(255, 255, 255, 40))
        p.drawEllipse(QRectF(lx, ly, lw, lh))
        p.drawEllipse(QRectF(rx, ry, rw, rh))

        # Bridge
        p.drawLine(QPointF(lx + lw, bridge_y), QPointF(rx + 1, bridge_y2))

        # Temple
        p.drawLine(QPointF(rx + rw, ry + int(rh * 0.44)), QPointF(temple_x2, temple_y2))

        # White sheens //
        pen_sheen = QPen(QColor(255, 255, 255, 220), 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        p.setPen(pen_sheen)
        p.drawLine(QPointF(rx + rw * 0.44, ry + rh * 0.22), QPointF(rx + rw * 0.28, ry + rh * 0.56))
        p.drawLine(QPointF(rx + rw * 0.60, ry + rh * 0.22), QPointF(rx + rw * 0.44, ry + rh * 0.56))

    def paintEvent(self, event: Any) -> None:
        if self._mascot_pixmap.isNull():
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        pm_w = self._mascot_pixmap.width()
        pm_h = self._mascot_pixmap.height()

        draw_x = (self.width() - pm_w) // 2
        draw_y = (self.height() - pm_h) // 2

        pivot_x = draw_x + pm_w / 2
        pivot_y = draw_y + pm_h * 0.95

        p.save()
        p.translate(pivot_x, pivot_y)
        p.rotate(self._rotation)
        p.translate(-pivot_x, -pivot_y)

        p.drawPixmap(draw_x, draw_y, self._mascot_pixmap)

        # Procedural ink glasses on eyes during thinking / reasoning / PAL
        st = self.current_state
        if st in ("thinking", "reasoning", "pal") or getattr(self, "show_glasses", False):
            self._draw_ink_glasses(p, draw_x, draw_y, pm_w, pm_h)

        p.restore()

        # Draw expressive overhead badge if active
        st = self.current_state
        head_cx = draw_x + int(pm_w * 0.36)
        head_cy = draw_y + 16

        if st == "thinking":
            p.save()
            p.translate(head_cx + 16, head_cy - 12)
            p.rotate(self._spin_angle)
            pen = QPen(QColor("#F59E0B"), 2.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
            p.setPen(pen)
            p.drawArc(QRectF(-8, -8, 16, 16), 0, 270 * 16)
            p.restore()
            p.setFont(QFont("Apple Color Emoji", 12))
            p.drawText(QRectF(head_cx + 26, head_cy - 22, 18, 18), Qt.AlignmentFlag.AlignCenter, "💭")
        elif st == "searching":
            p.setFont(QFont("Apple Color Emoji", 18))
            p.drawText(QRectF(head_cx + 10, head_cy - 20, 24, 24), Qt.AlignmentFlag.AlignCenter, "🔍")
        elif st == "angry":
            p.setFont(QFont("Apple Color Emoji", 18))
            p.drawText(QRectF(head_cx - 4, head_cy - 10, 22, 22), Qt.AlignmentFlag.AlignCenter, "💢")

        p.end()


class RatCompanionStage(QWidget):
    """
    Desktop Game Companion Character Stage.
    A dedicated visual stage for the mascot character standing beside the interaction console.
    Supports emotional/operational states:
    - 'idle': Sẵn sàng (Clean, no tryhard AI badge)
    - 'listening': Đang nghe
    - 'thinking': Đang suy nghĩ...
    - 'searching': Đang bới tệp...
    - 'found': Đã tìm thấy!
    - 'happy': Vui vẻ!
    - 'sleepy': Nghỉ ngơi
    """

    def __init__(self, window: "OmnibarWindow", parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.window = window
        self.setObjectName("RatStage")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedWidth(150)
        self.current_state = "idle"
        self._quote_idx = 0
        self._quotes = [
            "Nghe đây. Cần gì?",
            "Đưa câu hỏi đây, mình gỡ từng ý.",
            "Có mặt. Không cần điểm danh lần nữa đâu.",
            "Ừ, tôi đang nghe. Cứ gõ đi.",
            "Nhấp đúp để mở phần trao đổi đầy đủ.",
        ]
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)

        # Mascot Avatar (Clean crisp sprite without blurry gray shadow box)
        self.mascot_lbl = QLabel(self)
        self.mascot_lbl.setObjectName("RatAvatar")
        self.mascot_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.mascot_lbl.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mascot_lbl.mousePressEvent = self._on_mascot_pressed

        layout.addWidget(self.mascot_lbl, 0, Qt.AlignmentFlag.AlignCenter)

        # Character Mood / Status Pill (Clean: Hidden by default when idle, appears only during active states)
        self.mood_pill = QLabel("", self)
        self.mood_pill.setObjectName("RatMoodPill")
        self.mood_pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.mood_pill.setFixedHeight(24)
        self.mood_pill.hide()
        layout.addWidget(self.mood_pill, 0, Qt.AlignmentFlag.AlignCenter)

        # Subtitle hint (kept hidden for clean aesthetic)
        self.hint_lbl = QLabel("", self)
        self.hint_lbl.hide()

        self.update_mascot_size(155)

    def update_mascot_size(self, target_h: int) -> None:
        target_w = int(target_h * (419 / 445))
        pm = get_mascot_pixmap(target_w, target_h)
        if pm and not pm.isNull():
            self.mascot_lbl.setPixmap(pm)
            self.mascot_lbl.setFixedSize(target_w, target_h)
        else:
            self.mascot_lbl.setText("🧀")
            self.mascot_lbl.setStyleSheet("font-size: 48px;")

    def set_state(self, state: str, custom_text: Optional[str] = None) -> None:
        self.current_state = state
        if state == "idle":
            self.mood_pill.hide()
            return

        state_configs = {
            "listening": ("✨ Chuột · Đang nghe", "#EFF8F2", "#1D6B3E", "#A3D9B5"),
            "thinking": ("💭 Chuột · Đang suy nghĩ...", "#EFF6FF", "#1E40AF", "#BFDBFE"),
            "searching": ("🔍 Chuột · Đang bới tệp...", "#FFF2EB", "#9A3412", "#FED7AA"),
            "found": ("📁 Chuột · Đã tìm thấy!", "#F0FDF4", "#166534", "#BBF7D0"),
            "happy": ("🎉 Chuột · Vui vẻ!", "#FFF6DD", "#7A5800", "#E5C470"),
            "sleepy": ("💤 Chuột · Nghỉ ngơi", "#F4F0EA", "#615547", "#D6CDC1"),
        }
        cfg = state_configs.get(state, ("🧀 Chuột", "#FFF6DD", "#7A5800", "#E5C470"))
        text = custom_text or cfg[0]
        bg, col, bd = cfg[1], cfg[2], cfg[3]
        self.mood_pill.setText(text)
        self.mood_pill.setStyleSheet(f"""
            QLabel#RatMoodPill {{
                background-color: {bg};
                color: {col};
                border: 1px solid {bd};
                border-radius: 12px;
                padding: 3px 12px;
                font-size: 11px;
                font-weight: 750;
            }}
        """)
        self.mood_pill.show()

    def _on_mascot_pressed(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._quote_idx = (self._quote_idx + 1) % len(self._quotes)
            q = self._quotes[self._quote_idx]
            if hasattr(self.window, "rat_speech"):
                self.window.rat_speech.setText(q)
            self.set_state("happy", "🎉 Chuột · Vui vẻ!")
            QTimer.singleShot(2500, lambda: self.set_state("idle"))

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        self.window.toggle_expand()


