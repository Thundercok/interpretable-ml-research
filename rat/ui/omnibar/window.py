"""
rat.ui.omnibar — Unified Casual Surface (Omnibar).
One Surface, Zero Modes.
Collapses Spotlight search, recent files, live academic agenda, full timetable,
campus room guidance, and instant calculations into a single macOS-native HUD.
"""

from __future__ import annotations

import logging
import os
import re
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from PyQt6.QtCore import (
    QAbstractAnimation,
    QEasingCurve,
    QEvent,
    QObject,
    QParallelAnimationGroup,
    QPoint,
    QPointF,
    QPropertyAnimation,
    QRect,
    QRectF,
    QSize,
    Qt,
    QThread,
    QTimer,
    pyqtProperty,
    pyqtSignal,
    pyqtSlot,
)
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QCursor,
    QFont,
    QGuiApplication,
    QKeyEvent,
    QLinearGradient,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from rat.config import config
from rat.crawler.db import Database
from rat.engine.hybrid_search import SearchEngine
from rat.engine.reranker import SearchResultItem, sort_search_results
from rat.ui.feedback import SearchFeedback
from rat.timetable.compositor import TimetableCompositor, availability_to_color, degree_to_style
from rat.timetable.data import load_club_members
from rat.timetable.model import (
    DAYS,
    SHIFTS,
    ClassSession,
    MemberSchedule,
    resolve_room_location,
)
from rat.ui.action_menu import ActionMenuDialog
from rat.ui.apple_item_delegate import AppleSpotlightDelegate
from rat.ui.finder_window import AsyncQAWorker
from rat.ui.preview_panel import (
    PreviewPanel,
    open_file_default,
    open_in_terminal,
    reveal_in_finder,
    trigger_quicklook,
)
from rat.ui.chat_stream import ChatStreamWidget, get_mascot_pixmap
from rat.ui.chat_composer import ChatComposer
from rat.ui.compact_results import CompactFileRow, ElidedLabel
from rat.ui.reply_reader import ReplyReader, reply_plain_text
from rat.ui.chat_session import (
    CHAT_SYSTEM_PROMPT,
    ConversationHistory,
    build_chat_prompt,
    extract_arithmetic_request,
    normalize_chat_request,
)
from rat.ui.settings_dialog import SettingsDialog
from rat.ui.theme import (
    CHAT_ACTION_QSS,
    CHAT_COLORS,
    CONVERSATION_RIBBON_QSS,
    RAYCAST_QSS,
    get_ext_badge_info,
)

from dataclasses import dataclass

logger = logging.getLogger("rat.ui.omnibar")


from .chat_controller import ChatPresentationState


def lower_overlay_geometry(available: QRect, width: int, height: int) -> QRect:
    """Compact summon sits low; expanded reading grows upward from the same bottom."""
    width = min(width, available.width())
    height = min(height, available.height())
    margin = min(max(24, round(available.height() * 0.08)), (available.height() - height) // 2)
    return QRect(
        available.x() + (available.width() - width) // 2,
        available.y() + available.height() - margin - height,
        width, height,
    )


def configure_macos_fullscreen_overlay(widget: QWidget) -> None:
    """
    Ensure the overlay window floats on top of all macOS Spaces
    including native full-screen apps (VS Code, Chrome, etc.).
    """
    try:
        import sys
        if sys.platform != "darwin":
            return
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance()
        if app and app.platformName() == "offscreen":
            return
        import objc
        from ctypes import c_void_p
        from AppKit import (
            NSWindowCollectionBehaviorCanJoinAllSpaces,
            NSWindowCollectionBehaviorFullScreenAuxiliary,
            NSFloatingWindowLevel,
        )

        ns_view = objc.objc_object(c_void_p=int(widget.winId()))
        ns_window = ns_view.window() if hasattr(ns_view, "window") else None
        if ns_window:
            behavior = ns_window.collectionBehavior()
            ns_window.setCollectionBehavior_(
                behavior
                | NSWindowCollectionBehaviorCanJoinAllSpaces
                | NSWindowCollectionBehaviorFullScreenAuxiliary
            )
            ns_window.setLevel_(NSFloatingWindowLevel)
    except Exception as e:
        logger.debug(f"macOS fullscreen overlay config error: {e}")


from .search_controller import SearchController
from .chat_controller import ChatController
from .views import (
    FILTER_CATEGORIES,
    SECTION_TABS,
    build_club_view,
    build_files_view,
    build_home_view,
    build_schedule_view,
    refresh_club_view,
    refresh_home_agenda,
    refresh_schedule_view,
)

from .workers import SearchWorker, StreamReasoningWorker
from .event_filters import (
    OmnibarInputFilter,
    OmnibarListFilter,
    handle_item_reveal_or_terminal,
    handle_omnibar_escape,
)


from .companion import (
    ArtisticSpeechBubble,
    CompanionAvatarButton,
    ConversationRibbon,
    PeekingRatMascot,
    RatCompanionStage,
    ResetConfirmationDialog,
)


class OmnibarWindow(QMainWindow):
    """
    Unified Casual Surface (Omnibar).
    Brings together chat, file search, class schedules, and shared free-time windows.
    """

    search_requested = pyqtSignal(int, str, list)

    def __init__(self) -> None:
        super().__init__()
        self.db = Database(config.db_path)
        self.engine = SearchEngine(self.db)
        self.compositor = TimetableCompositor(load_club_members())
        self.members: List[MemberSchedule] = self.compositor.members

        self.current_section_idx = 0
        self.active_file_filter_idx = 0
        self.is_expanded = False
        self.is_reading_reply = False
        self._request_counter = 0
        self._dialog_active = False
        self._is_opening = False
        self._was_activated = False
        self.current_query = ""
        self._conversation = ConversationHistory()
        self._pending_chat_query: Optional[str] = None
        self._chat_generation = 0
        self._current_reasoner: Optional[StreamReasoningWorker] = None
        self._reasoning_workers: set[StreamReasoningWorker] = set()
        self._presentation_state = ChatPresentationState()
        self._chat_request_counter = 0
        self._current_stream_handle: Optional[Dict[str, Any]] = None
        self._complete_status_timer = QTimer(self)
        self._complete_status_timer.setSingleShot(True)
        self._complete_status_timer.timeout.connect(self._on_complete_status_timeout)
        self._chat_file_request: Optional[Dict[str, Any]] = None
        self._toast_timer = QTimer(self)
        self._toast_timer.setSingleShot(True)
        self._toast_timer.timeout.connect(self._restore_toast)
        self._toast_restore: Optional[tuple[str, str, str]] = None

        # Active default member from config
        p_name = (config.default_member_name or "").strip().lower()
        self.current_member = next((m for m in self.members if p_name in m.name.lower()), self.members[0])

        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(180)
        self.search_timer.timeout.connect(self._execute_search)
        self.search_controller = SearchController(self)
        self.chat_controller = ChatController(self)

        self._drag_pos = QPoint()
        self._init_thread()
        self._init_window()
        self._init_ui()
        self.feedback = SearchFeedback(self, "omnibar", [self.result_list, self.recent_list, self.compact_file_list])
        self._load_initial_data()

    def _init_thread(self) -> None:
        self.search_thread = QThread(None)
        self.worker = SearchWorker(self.engine)
        self.worker.moveToThread(self.search_thread)
        self.search_requested.connect(self.worker.do_search)
        self.worker.search_completed.connect(self._on_search_completed)
        self.search_thread.start()

        self.qa_thread = QThread(None)
        self.qa_worker = AsyncQAWorker()
        self.qa_worker.moveToThread(self.qa_thread)
        self.qa_thread.start()


    def _init_window(self) -> None:
        self.setWindowTitle("rat")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet(RAYCAST_QSS)
        self._resize_overlay(652, 238)
        configure_macos_fullscreen_overlay(self)

    def _resize_overlay(self, new_width: int, new_height: int, animated: bool = False) -> None:
        """Keep the overlay low on the active screen, with room to grow upward."""
        # Qt may need a couple more pixels than the nominal compact height.
        # Position using the actual layout minimum so the bottom anchor stays exact.
        minimum = self.minimumSizeHint()
        new_width = max(new_width, minimum.width())
        new_height = max(new_height, minimum.height())
        try:
            cursor_pos = QCursor.pos()
            screen = QGuiApplication.screenAt(cursor_pos) or self.screen() or QGuiApplication.primaryScreen()
            if screen:
                geo = screen.availableGeometry()
                target_rect = lower_overlay_geometry(geo, new_width, new_height)

                if hasattr(self, "_geom_anim"):
                    self._geom_anim.stop()

                if animated and self.isVisible() and os.environ.get("QT_QPA_PLATFORM") != "offscreen":
                    if not hasattr(self, "_geom_anim"):
                        self._geom_anim = QPropertyAnimation(self, b"geometry")
                        self._geom_anim.setDuration(160)
                        self._geom_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
                    self._geom_anim.stop()
                    self._geom_anim.setStartValue(self.geometry())
                    self._geom_anim.setEndValue(target_rect)
                    self._geom_anim.start()
                else:
                    self.setGeometry(target_rect)
                return
        except Exception:
            pass
        self.resize(new_width, new_height)

    def _recenter_window(self) -> None:
        """Position window in the lower half of the active screen."""
        self._resize_overlay(self.width(), self.height())

    def _reset_quick_chat(self) -> None:
        """Start a fresh, clean chat session on every quick mode opening."""
        self.set_expanded(False)
        if hasattr(self, "chat_composer_input"):
            self.chat_composer_input.clear()
            self.chat_composer_input.setFocus()
        self.set_mascot_idle()
        if hasattr(self, "speech_bubble"):
            self.speech_bubble.reset_welcome()

    def showEvent(self, event: Any) -> None:
        super().showEvent(event)
        if hasattr(self, "chat_composer_input"):
            self.chat_composer_input.setFocus()
        self._animate_mascot_peek()

    def _animate_mascot_peek(self) -> None:
        """State-aware mascot transition."""
        if not hasattr(self, "mascot_peeking"):
            return
        if getattr(self.mascot_peeking, "is_speaking", False):
            self.mascot_peeking.pop_out_speaking()
        else:
            self.mascot_peeking.retreat_to_idle()

    def resizeEvent(self, event: Any) -> None:
        super().resizeEvent(event)
        if hasattr(self, "speech_bubble") and hasattr(self, "container"):
            self._position_reply_bubble()
            cx = self.container.x() if self.container.x() > 0 else 16
            cy = self.container.y() if self.container.y() > 20 else 120
            if hasattr(self, "mascot_peeking"):
                self._sync_mascot_anchor(animated=self.isVisible())

    def _sync_mascot_anchor(self, animated: bool = False) -> None:
        if not hasattr(self, "mascot_peeking") or not hasattr(self, "container"):
            return
        self.mascot_peeking.set_anchors(
            self.container.x(), self.container.y(), side=self.is_expanded,
            container_bottom=self.container.y() + self.container.height(), animated=animated,
        )

    def _position_reply_bubble(self) -> None:
        cx = self.container.x() if self.container.x() > 0 else 16
        cy = self.container.y() if self.container.y() > 20 else 120
        by = max(4, cy - self.speech_bubble.height() - 14)
        self.speech_bubble.move(cx + 160, by)
        # Keep the tail near the rat's face while the bubble grows upward.
        self.speech_bubble.tail_y = max(20, min(self.speech_bubble.height() - 28, cy - 44 - by))
        self.speech_bubble.raise_()
        self.speech_bubble.update()

    def set_mascot_speaking(self, text: Optional[str] = None) -> None:
        """Activate SPEAKING state: triggers diagonal pop-out and speech bubble."""
        if text:
            if hasattr(self, "speech_bubble"):
                self.speech_bubble.set_reply(text)
        if hasattr(self, "mascot_peeking"):
            if not self.mascot_peeking.is_speaking:
                if hasattr(self, "speech_bubble"):
                    self.speech_bubble.hide()
                self.mascot_peeking.pop_out_speaking()
            else:
                if hasattr(self, "speech_bubble"):
                    self.speech_bubble.show_bubble()

    def _on_mascot_speaking_popped_out(self) -> None:
        """Speech bubble appears right after mouse finishes diagonal pop-out."""
        if hasattr(self, "speech_bubble") and not self.is_expanded and not self.is_reading_reply:
            self.speech_bubble.show_bubble()

    def set_mascot_idle(self) -> None:
        """Activate IDLE state: hides speech bubble and retreats to peeking paws/eyes."""
        if hasattr(self, "speech_bubble"):
            self.speech_bubble.hide_bubble()
        if hasattr(self, "mascot_peeking"):
            self.mascot_peeking.retreat_to_idle()

    def _on_mascot_idle_retreated(self) -> None:
        pass

    def on_mascot_clicked(self) -> None:
        """Interactive click on mascot toggles speaking/quote or retreats."""
        if not hasattr(self, "mascot_peeking"):
            return
        if not self.mascot_peeking.is_speaking:
            quotes = [
                "Có mặt. Không cần điểm danh lần nữa đâu.",
                "Ừ, tôi đang nghe. Cứ gõ đi.",
                "Đưa câu hỏi đây, mình gỡ từng ý.",
                "Nghe đây. Cần gì?",
            ]
            self._mascot_quote_idx = (getattr(self, "_mascot_quote_idx", 0) + 1) % len(quotes)
            self.set_mascot_speaking(quotes[self._mascot_quote_idx])
            if not hasattr(self, "_mascot_click_timer"):
                self._mascot_click_timer = QTimer(self)
                self._mascot_click_timer.setSingleShot(True)
                self._mascot_click_timer.timeout.connect(self.set_mascot_idle)
            self._mascot_click_timer.start(5000)
        else:
            self.set_mascot_idle()

    def set_mascot_state(self, state: str, text: Optional[str] = None) -> None:
        """Unified state setter for Chuột across all UI widgets."""
        self._mascot_state = state
        if hasattr(self, "companion_avatar_btn"):
            self.companion_avatar_btn.set_state(state)
        if hasattr(self, "mascot_peeking"):
            self.mascot_peeking.set_state(state)
        if hasattr(self, "rat_stage") and self.rat_stage:
            self.rat_stage.set_state(state, text)
        if text:
            if not self.is_expanded:
                self.set_mascot_speaking(text)
            elif hasattr(self, "footer_status"):
                self.footer_status.setText(f"Chuột · {text}")

    def toggle_expand(self) -> None:
        """Toggle between compact HUD overlay and expanded detail notebook."""
        self.set_expanded(not self.is_expanded)

    def read_full_reply(self) -> None:
        """A long answer opens in place; rich tool cards still use the full chat view."""
        if not self.speech_bubble.has_reply:
            return
        if self.speech_bubble._has_details:
            self.set_expanded(True)
        else:
            self.set_reply_reader_open(not self.is_reading_reply)

    def set_reply_reader_open(self, opened: bool) -> None:
        has_content = (
            bool(self.reply_reader.full_reply.strip())
            or (hasattr(self.reply_reader, "has_content") and self.reply_reader.has_content())
        )
        self.is_reading_reply = opened and has_content
        if self.is_reading_reply and self.is_expanded:
            self.set_expanded(False)
            self.is_reading_reply = True
        if self.is_reading_reply:
            if hasattr(self, "_conversation") and hasattr(self.reply_reader, "set_session_tag"):
                self.reply_reader.set_session_tag(self._conversation.get_tag_label())
            if hasattr(self, "_conversation"):
                if hasattr(self.reply_reader, "sync_history"):
                    self.reply_reader.sync_history(self._conversation._turns)
                elif hasattr(self.reply_reader, "set_turns"):
                    self.reply_reader.set_turns(self._conversation._turns)
        self.reply_reader.setVisible(self.is_reading_reply)
        if self.is_reading_reply:
            self.speech_bubble.hide_bubble()
        elif not self.is_expanded and self.speech_bubble.has_reply:
            self.speech_bubble.show_bubble()
        self._sync_compact_surface()
        if not self.is_expanded:
            self._resize_overlay(652, self._compact_height())
        if hasattr(self, "btn_expand") and self.btn_expand:
            if self.is_reading_reply:
                self.btn_expand.setText("⤢")
                self.btn_expand.setToolTip("Mở toàn bộ hội thoại · ⌘L")
                self.btn_expand.setAccessibleName("Mở toàn bộ hội thoại")
            elif not self.is_expanded:
                self.btn_expand.setText("⤢")
                self.btn_expand.setToolTip("Mở hội thoại · ⌘L")
                self.btn_expand.setAccessibleName("Mở hội thoại")
        self.chat_composer_input.setFocus()

    def set_expanded(self, expanded: bool) -> None:
        """Explicitly switch between compact HUD and full notebook mode."""
        self.is_expanded = expanded
        self.is_reading_reply = False
        if hasattr(self, "reply_reader"):
            self.reply_reader.hide()
        if hasattr(self, "speech_bubble"):
            self.speech_bubble.set_expanded_mode(expanded)

        if expanded:
            if hasattr(self, "main_layout"):
                # Keep the 620px paper width, reserve the mascot's own side space.
                self.main_layout.setContentsMargins(152, 16, 16, 16)
            if hasattr(self, "mascot_peeking"):
                self.mascot_peeking.show()
            if hasattr(self, "speech_bubble"):
                self.speech_bubble.hide()
            if getattr(self, "btn_expand", None):
                self.btn_expand.show()
            if hasattr(self, "chat_header_status"):
                self.chat_header_status.hide()
            if hasattr(self, "section_bar"):
                self.section_bar.hide()
            if hasattr(self, "content_stack"):
                self.content_stack.show()
                self.content_stack.setCurrentIndex(getattr(self, "current_section_idx", 0))
            if hasattr(self, "chat_stream"):
                self.chat_stream.show()
            if hasattr(self, "action_footer"):
                self.action_footer.show()
            if hasattr(self, "quick_suggestions"):
                self.quick_suggestions.hide()
            if hasattr(self, "compact_file_list"):
                self.compact_file_list.hide()
                self.compact_footer.hide()
            if hasattr(self, "hairline_divider"):
                self.hairline_divider.hide()
            self._sync_compact_surface()
            self.main_layout.activate()
            self._sync_mascot_anchor(animated=self.isVisible())
            self._resize_overlay(788, 580, animated=True)
            if hasattr(self, "btn_expand") and self.btn_expand:
                self.btn_expand.setText("⤡")
                self.btn_expand.setToolTip("Thu gọn hội thoại · ⌘L")
                self.btn_expand.setAccessibleName("Thu gọn hội thoại")
        else:
            if hasattr(self, "main_layout"):
                self.main_layout.setContentsMargins(16, 120, 16, 16)
            if hasattr(self, "mascot_peeking"):
                self.mascot_peeking.show()
            if hasattr(self, "speech_bubble"):
                if self.speech_bubble.has_reply:
                    self.speech_bubble.show_bubble()
                else:
                    self.speech_bubble.hide()
            if hasattr(self, "chat_header_status"):
                self.chat_header_status.hide()
            if hasattr(self, "companion_avatar_btn"):
                self.companion_avatar_btn.hide()
            if hasattr(self, "btn_expand"):
                self.btn_expand.show()
            if hasattr(self, "return_keycap"):
                self.return_keycap.hide()
            if hasattr(self, "section_bar"):
                self.section_bar.hide()
            if hasattr(self, "content_stack"):
                self.content_stack.hide()
            if hasattr(self, "chat_stream"):
                self.chat_stream.hide()
            if hasattr(self, "action_footer"):
                self.action_footer.hide()
            if hasattr(self, "quick_suggestions"):
                self._sync_compact_surface()
            if hasattr(self, "hairline_divider"):
                self.hairline_divider.hide()
            self.main_layout.activate()
            self._sync_mascot_anchor(animated=self.isVisible())
            self._resize_overlay(652, self._compact_height(), animated=True)
            if hasattr(self, "btn_expand") and self.btn_expand:
                self.btn_expand.setText("⤢")
                if getattr(self, "is_reading_reply", False):
                    self.btn_expand.setToolTip("Mở toàn bộ hội thoại · ⌘L")
                    self.btn_expand.setAccessibleName("Mở toàn bộ hội thoại")
                else:
                    self.btn_expand.setToolTip("Mở hội thoại · ⌘L")
                    self.btn_expand.setAccessibleName("Mở hội thoại")

    def _init_ui(self) -> None:
        self.input_filter = OmnibarInputFilter(self)

        main_widget = QWidget(self)
        main_widget.setObjectName("OmnibarCanvas")
        main_widget.setStyleSheet("QWidget#OmnibarCanvas { background: transparent; border: none; }")
        self.setCentralWidget(main_widget)
        self.main_layout = QVBoxLayout(main_widget)
        self.main_layout.setContentsMargins(16, 120, 16, 16)
        self.main_layout.setSpacing(0)

        # =============================================================
        # SINGLE UNIFIED CONTAINER (Warm Light Glass)
        # =============================================================
        container = QFrame(main_widget)
        container.setObjectName("SpotlightContainer")
        container.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        container.setStyleSheet("""
            QFrame#SpotlightContainer {
                background: #FFFDFA;
                border: 1px solid #DDD7CD;
                border-radius: 16px;
            }
        """)
        cont_shadow = QGraphicsDropShadowEffect(container)
        cont_shadow.setBlurRadius(18)
        cont_shadow.setOffset(0, 4)
        cont_shadow.setColor(QColor(38, 30, 23, 24))
        container.setGraphicsEffect(cont_shadow)

        self.container = container
        self.container_layout = QVBoxLayout(container)
        self.container_layout.setContentsMargins(14, 12, 14, 12)
        self.container_layout.setSpacing(8)

        # -------------------------------------------------------------
        # PEEKING MASCOT (Núp hở mắt/tay & Pop-out xéo)
        # -------------------------------------------------------------
        self.mascot_peeking = PeekingRatMascot(self, main_widget)
        self.mascot_peeking.stackUnder(container)
        self.mascot_peeking.setGeometry(24, 8, 146, 146)
        self.mascot_peeking.set_anchors(16, 120)
        self.mascot_peeking.speaking_popped_out.connect(self._on_mascot_speaking_popped_out)
        self.mascot_peeking.idle_retreated.connect(self._on_mascot_idle_retreated)
        self.mascot_peeking.show()

        # -------------------------------------------------------------
        # ARTISTIC SPEECH BUBBLE (Sitting above container, flush right)
        # -------------------------------------------------------------
        self.speech_bubble = ArtisticSpeechBubble(self, main_widget)
        self.speech_bubble.setGeometry(176, 14, 460, 92)
        self.speech_bubble.hide()

        # Compatibility attributes
        self.rat_avatar = self.mascot_peeking
        self.rat_stage = None
        self.rat_perch = None
        self.rat_speech = self.speech_bubble.dialogue
        self.rat_speech_frame = self.speech_bubble
        self.btn_expand = None
        self.btn_close = None
        self.btn_bubble_expand = None
        self.speech_expand_hint = None
        self.rat_tail = None

        # -------------------------------------------------------------
        # 1. IN-PLACE READER AND INPUT ROW (QuickBar)
        # -------------------------------------------------------------
        # The answer grows above the composer, keeping the next question within reach.
        self.reply_reader = ReplyReader(container)
        self.reply_reader.close_requested.connect(lambda: self.set_reply_reader_open(False))
        self.reply_reader.copied.connect(lambda: self.show_toast("Đã sao chép toàn bộ đáp án"))
        self.reply_reader.body.installEventFilter(self.input_filter)
        self.reply_reader.close_button.installEventFilter(self.input_filter)
        self.reply_reader.copy_button.installEventFilter(self.input_filter)
        if hasattr(self.reply_reader, "btn_prev"):
            self.reply_reader.btn_prev.installEventFilter(self.input_filter)
            self.reply_reader.btn_next.installEventFilter(self.input_filter)
            self.reply_reader.btn_latest.installEventFilter(self.input_filter)
        self.reply_reader.hide()
        self.container_layout.addWidget(self.reply_reader)

        quick_bar = QFrame()
        quick_bar.setObjectName("QuickBar")
        quick_bar.setFixedHeight(36)

        qb_layout = QHBoxLayout(quick_bar)
        qb_layout.setContentsMargins(4, 0, 4, 0)
        qb_layout.setSpacing(6)

        # Companion Avatar Button inside QuickBar (Hidden in clean mode)
        self.companion_avatar_btn = CompanionAvatarButton(self, quick_bar)
        self.companion_avatar_btn.hide()
        qb_layout.addWidget(self.companion_avatar_btn, 0)

        self.chat_composer_input = ChatComposer()
        self.chat_composer_input.setObjectName("ChatComposerInput")
        self.chat_composer_input.setPlaceholderText("Hỏi một điều, tìm một tệp…")
        self.chat_composer_input.setStyleSheet("""
            QPlainTextEdit#ChatComposerInput {
                font-size: 13px;
                font-weight: 400;
                border: none;
                background: transparent;
                color: #302B24;
                padding-left: 2px;
            }
        """)
        self.chat_composer_input.installEventFilter(self.input_filter)
        self.chat_composer_input.submit_requested.connect(lambda: self._submit_chat_prompt(self.chat_composer_input.text()))
        self.chat_composer_input.textChanged.connect(lambda: self._on_composer_text_changed(self.chat_composer_input.text()))
        qb_layout.addWidget(self.chat_composer_input, 1)

        # Minimal model status badge (shown in expanded mode)
        has_slm = False
        try:
            from rat.engine.slm import slm_engine
            has_slm = slm_engine.is_service_running()
        except Exception:
            pass
        status_text = "● Qwen2.5" if has_slm else "● TDTU"
        self.chat_header_status = QLabel(status_text, quick_bar)
        self.chat_header_status.setObjectName("QuickModelBadge")
        self.chat_header_status.hide()
        qb_layout.addWidget(self.chat_header_status)

        self.btn_expand = QPushButton("⤢", quick_bar)
        self.btn_expand.setObjectName("BtnExpand")
        self.btn_expand.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_expand.setToolTip("Mở hội thoại · ⌘L")
        self.btn_expand.setAccessibleName("Mở hội thoại")
        self.btn_expand.clicked.connect(self.toggle_expand)
        self.btn_expand.setFixedSize(36, 36)
        self.btn_expand.setStyleSheet(f"""
            QPushButton#BtnExpand {{
                background: transparent;
                border: 1px solid transparent;
                color: #8C8275;
                font-size: 14px;
                font-weight: bold;
                border-radius: 8px;
            }}
            QPushButton#BtnExpand:hover {{
                background: rgba(43, 38, 31, 0.08);
                border-color: rgba(43, 38, 31, 0.12);
                color: #1F1A16;
            }}
            QPushButton#BtnExpand:focus {{
                border-color: {CHAT_COLORS['focus']};
                outline: none;
            }}
        """)
        self.btn_expand.show()
        qb_layout.addWidget(self.btn_expand, 0, Qt.AlignmentFlag.AlignBottom)

        self.return_keycap = QLabel("↵")
        self.return_keycap.setObjectName("ReturnKeycap")
        self.return_keycap.setToolTip("Nhấn Enter để gửi")
        self.return_keycap.hide()
        qb_layout.addWidget(self.return_keycap)

        self.chat_composer_send = QPushButton("↑", quick_bar)
        self.chat_composer_send.setObjectName("ChatComposerSend")
        self.chat_composer_send.setFixedSize(36, 36)
        self.chat_composer_send.setToolTip("Gửi câu hỏi (Enter)")
        self.chat_composer_send.setAccessibleName("Gửi câu hỏi")
        self.chat_composer_send.setCursor(Qt.CursorShape.PointingHandCursor)
        self.chat_composer_send.setEnabled(False)
        self.chat_composer_send.setStyleSheet(f"""
            QPushButton#ChatComposerSend {{
                background: #ECD6A8;
                color: #4F3C1E;
                border: 1px solid #DFC48F;
                border-radius: 8px;
                font-size: 16px;
                font-weight: 600;
            }}
            QPushButton#ChatComposerSend:hover {{
                background: #E5C88F;
                border-color: #D4B679;
            }}
            QPushButton#ChatComposerSend:focus {{
                border-color: {CHAT_COLORS['focus']};
                outline: none;
            }}
            QPushButton#ChatComposerSend:disabled {{
                background: #F1EDE5;
                color: #9A9184;
                border: 1px solid transparent;
            }}
        """)
        self.chat_composer_send.clicked.connect(lambda: self._submit_chat_prompt(self.chat_composer_input.text()))
        qb_layout.addWidget(self.chat_composer_send, 0, Qt.AlignmentFlag.AlignBottom)

        self.quick_bar = quick_bar
        self.chat_composer_input.height_changed.connect(self._on_composer_height_changed)
        self.container_layout.addWidget(quick_bar, 0)

        # -------------------------------------------------------------
        # 2. HAIRLINE DIVIDER (Hidden in clean compact mode)
        # -------------------------------------------------------------
        self.hairline_divider = QFrame()
        self.hairline_divider.setObjectName("HairlineDivider")
        self.container_layout.addWidget(self.hairline_divider, 0)
        self.hairline_divider.hide()

        # -------------------------------------------------------------
        # 3. QUICK SUGGESTIONS STRIP (Clean suggestion chips)
        # -------------------------------------------------------------
        self.quick_suggestions = QWidget()
        self.quick_suggestions.setObjectName("QuickSuggestionsStrip")
        self.quick_suggestions.setFixedHeight(28)
        qs_layout = QHBoxLayout(self.quick_suggestions)
        qs_layout.setContentsMargins(2, 0, 2, 0)
        qs_layout.setSpacing(6)

        sugg_chips = [
            ("Cùng nghĩ một ý", "Giúp mình nghĩ về ", False),
            ("Tìm tệp…", "tìm file ", False),
            ("Lịch hôm nay", "hôm nay học gì", True),
        ]
        self.chip_buttons: List[QPushButton] = []
        for label, q_text, submit in sugg_chips:
            chip_btn = QPushButton(label)
            chip_btn.setProperty("class", "QuickSuggestionChip")
            chip_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            chip_btn.setStyleSheet("""
                QPushButton {
                    background: #F7F3EC;
                    border: none;
                    border-radius: 7px;
                    padding: 3px 10px;
                    font-size: 11px;
                    color: #6D6356;
                    font-weight: 400;
                }
                QPushButton:hover {
                    background: #EDE5D6;
                    color: #302B24;
                }
            """)
            chip_btn.installEventFilter(self.input_filter)
            chip_btn.clicked.connect(
                lambda checked=False, q=q_text, send=submit: self._submit_chat_prompt(q) if send else self._prefill_chat(q)
            )
            qs_layout.addWidget(chip_btn)
            self.chip_buttons.append(chip_btn)

        self.container_layout.addWidget(self.quick_suggestions, 0)
        self.quick_suggestions.show()

        # File results stay actionable in quick mode rather than behind a chat toggle.
        self.compact_file_list = QListWidget(container)
        self.compact_file_list.setObjectName("CompactFileResults")
        self.compact_file_list.setAccessibleName("Kết quả tìm tệp")
        self.compact_file_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.compact_file_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.compact_file_list.setUniformItemSizes(True)
        self.compact_file_list.setStyleSheet("""
            QListWidget#CompactFileResults { border: none; background: transparent; outline: none; }
            QListWidget#CompactFileResults::item { border: none; border-radius: 8px; }
            QListWidget#CompactFileResults::item:selected { background: #F3ECDf; }
            QListWidget#CompactFileResults::item:hover { background: #F6F1E8; }
        """)
        self.compact_list_filter = OmnibarListFilter(self)
        self.compact_file_list.installEventFilter(self.compact_list_filter)
        self.compact_file_list.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.compact_file_list.hide()
        self.container_layout.addWidget(self.compact_file_list)

        self.compact_footer = QWidget(container)
        compact_footer_layout = QHBoxLayout(self.compact_footer)
        compact_footer_layout.setContentsMargins(4, 0, 2, 0)
        self.compact_hint = ElidedLabel("↵ Hỏi tiếp · ⌘L Đọc hội thoại")
        self.compact_hint.setStyleSheet("font-size: 10px; color: #807668;")
        compact_footer_layout.addWidget(self.compact_hint, 1)
        self.compact_retry_btn = QPushButton("Thử lại", self.compact_footer)
        self.compact_retry_btn.setToolTip("Gửi lại câu hỏi vừa thất bại")
        self.compact_retry_btn.setAccessibleName("Thử lại câu hỏi")
        self.compact_retry_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.compact_retry_btn.setStyleSheet(CHAT_ACTION_QSS)
        self.compact_retry_btn.clicked.connect(self._retry_chat)
        self.compact_retry_btn.hide()
        compact_footer_layout.addWidget(self.compact_retry_btn)
        self.compact_footer.hide()
        self.container_layout.addWidget(self.compact_footer)

        # -------------------------------------------------------------
        # 4. FOLDER TABS (SECTION BAR)
        # -------------------------------------------------------------
        self.section_bar = QFrame()
        self.section_bar.setObjectName("FilterPillsBar")
        section_layout = QHBoxLayout(self.section_bar)
        section_layout.setContentsMargins(0, 0, 0, 0)
        section_layout.setSpacing(4)
        self.section_buttons: List[QPushButton] = []
        for idx, (sec_id, label, tooltip) in enumerate(SECTION_TABS):
            btn = QPushButton(label)
            btn.setProperty("class", "FilterPill")
            btn.setProperty("active", "true" if idx == 0 else "false")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked, i=idx: self.switch_section(i))
            section_layout.addWidget(btn)
            self.section_buttons.append(btn)
        section_layout.addStretch()
        self.container_layout.addWidget(self.section_bar, 0)
        self.section_bar.hide()

        # -------------------------------------------------------------
        # 5. CONTENT STACK
        # -------------------------------------------------------------
        self.content_stack = QStackedWidget()
        # Unselected timetable/club pages must not impose their size on the chat overlay.
        self.content_stack.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.content_stack.setStyleSheet("background: transparent;")

        self.home_view = self._create_home_view()
        self.content_stack.addWidget(self.home_view)

        self.files_view = self._create_files_view()
        self.content_stack.addWidget(self.files_view)

        self.schedule_view = self._create_schedule_view()
        self.content_stack.addWidget(self.schedule_view)

        self.club_view = self._create_club_view()
        self.content_stack.addWidget(self.club_view)

        self.container_layout.addWidget(self.content_stack, 1)
        self.content_stack.hide()

        # Action Footer
        footer = QFrame()
        footer.setObjectName("ActionFooter")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(14, 6, 14, 6)
        footer_layout.setSpacing(10)

        self.footer_status = QLabel("Sẵn sàng")
        self.footer_status.setMinimumWidth(0)
        self.footer_status.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.footer_status.setObjectName("FooterStatus")
        footer_layout.addWidget(self.footer_status)
        footer_layout.addStretch()

        hotkeys = [
            ("Enter", "Mở"),
            ("Space", "Xem nhanh"),
            ("Tab", "Chuyển mục"),
            ("⌘K", "Tác vụ"),
            ("Esc", "Đóng"),
        ]
        self.footer_hotkey_widgets = []
        for key, desc in hotkeys:
            badge = QLabel(key)
            badge.setProperty("class", "HotkeyBadge")
            desc_label = QLabel(desc)
            desc_label.setStyleSheet("color: #887c70; font-size: 10px; margin-right: 2px;")
            footer_layout.addWidget(badge)
            footer_layout.addWidget(desc_label)
            self.footer_hotkey_widgets.extend((badge, desc_label))

        self.action_footer = footer
        self.action_footer.hide()
        self.container_layout.addWidget(self.action_footer)

        # Hidden Compatibility Buttons
        self.btn_new_chat = QPushButton("⌘N", container)
        self.btn_new_chat.clicked.connect(lambda: self.request_reset_chat())
        self.btn_new_chat.hide()
        self.btn_settings = QPushButton("⚙", container)
        self.btn_settings.clicked.connect(self._open_settings)
        self.btn_settings.hide()

        self.main_layout.addWidget(container, 1)

    def _compact_height(self) -> int:
        if not hasattr(self, "container"):
            return 238
        self.container_layout.invalidate()
        self.main_layout.invalidate()
        self.container_layout.activate()
        self.main_layout.activate()
        self.layout().activate()
        return max(238, self.container.minimumSizeHint().height() + 136)

    def _sync_conversation_layout(self, composer_at_bottom: bool) -> None:
        """Only the full conversation moves its composer below the message stream."""
        if getattr(self, "_composer_at_bottom", None) == composer_at_bottom:
            return
        for widget in (self.quick_bar, self.hairline_divider, self.compact_footer):
            self.container_layout.removeWidget(widget)
        if composer_at_bottom:
            index = self.container_layout.indexOf(self.content_stack) + 1
            for widget in (self.hairline_divider, self.quick_bar, self.compact_footer):
                self.container_layout.insertWidget(index, widget)
                index += 1
        else:
            index = self.container_layout.indexOf(self.reply_reader) + 1
            self.container_layout.insertWidget(index, self.quick_bar)
            self.container_layout.insertWidget(index + 1, self.hairline_divider)
            index = self.container_layout.indexOf(self.compact_file_list) + 1
            self.container_layout.insertWidget(index, self.compact_footer)
        self._composer_at_bottom = composer_at_bottom

    def _on_complete_status_timeout(self) -> None:
        self.chat_controller.on_complete_status_timeout()

    def _sync_compact_surface(self) -> None:
        """Keep onboarding, reader and full-chat chrome consistent across states."""
        quick = not self.is_expanded and self.current_section_idx == 0
        expanded_chat = self.is_expanded and self.current_section_idx == 0
        self._sync_conversation_layout(expanded_chat)
        busy = (
            getattr(self, "_presentation_state", None) is not None
            and self._presentation_state.phase in ("waiting", "writing", "searching")
        ) or self._pending_chat_query is not None
        has_files = self.compact_file_list.count() > 0
        started = not self.chat_stream.is_empty()
        self.quick_suggestions.setVisible(quick and not self.is_reading_reply and not started and not busy)
        self.compact_file_list.setVisible(quick and not self.is_reading_reply and has_files)
        self.compact_footer.setVisible(expanded_chat or (quick and (started or busy or has_files)))
        self.hairline_divider.setVisible(expanded_chat)
        # Home uses the small composer hint, not the empty file-action footer.
        self.action_footer.setVisible(self.is_expanded and self.current_section_idx != 0)

        phase = getattr(self, "_presentation_state", None).phase if getattr(self, "_presentation_state", None) else "idle"
        timer_active = getattr(self, "_complete_status_timer", None) is not None and self._complete_status_timer.isActive()

        has_draft = bool(self.chat_composer_input.text().strip())
        if phase == "waiting":
            hint_text = "Đang chờ phản hồi…"
        elif phase == "writing":
            hint_text = "Đang viết…"
        elif phase == "searching":
            hint_text = "Đang tìm tệp…"
        elif phase == "completed" and timer_active and not has_draft:
            hint_text = self._presentation_state.status_text or "Đã trả lời"
        elif phase == "interrupted":
            hint_text = "Phản hồi bị ngắt"
        elif phase == "error":
            hint_text = "Chưa nhận được phản hồi"
        elif busy and self._chat_file_request:
            hint_text = "Đang tìm tệp…"
        elif busy:
            hint_text = "Đang chờ phản hồi…"
        elif self.is_reading_reply or expanded_chat:
            hint_text = "↵ Gửi · Shift+↵ Xuống dòng · Esc Thu gọn"
        elif has_files:
            hint_text = "↑↓ Chọn · ↵ Mở · Space Xem nhanh"
        else:
            hint_text = "↵ Gửi · Shift+↵ Xuống dòng · ⌘L Hội thoại"

        self.compact_hint.set_full_text(hint_text)

        can_retry = (
            getattr(self, "_presentation_state", None) is not None
            and self._presentation_state.retry_available
            and not busy
        )
        if hasattr(self, "compact_retry_btn"):
            self.compact_retry_btn.setVisible(can_retry)

        self.chat_composer_input.setPlaceholderText("Hỏi tiếp hoặc tìm tệp…" if started else "Hỏi một điều, tìm một tệp…")
        self.chat_composer_send.setEnabled(bool(self.chat_composer_input.text().strip()) and not busy)

    def _prefill_chat(self, text: str) -> None:
        self.chat_controller.prefill_chat(text)

    def _set_compact_files(self, files: Optional[List[SearchResultItem]]) -> None:
        self.compact_file_list.clear()
        for result in (files or [])[:4]:
            list_item = QListWidgetItem()
            list_item.setData(Qt.ItemDataRole.UserRole, result)
            list_item.setData(Qt.ItemDataRole.AccessibleTextRole, result.file_name)
            list_item.setData(Qt.ItemDataRole.AccessibleDescriptionRole, result.file_path)
            list_item.setSizeHint(QSize(1, CompactFileRow.ROW_HEIGHT))
            self.compact_file_list.addItem(list_item)
            row = CompactFileRow(result)
            row.open_requested.connect(lambda item: self.feedback.perform("open", item, open_file_default))
            row.reveal_requested.connect(lambda item: self.feedback.perform("reveal", item, reveal_in_finder))
            row.preview_requested.connect(lambda item: trigger_quicklook(item.file_path))
            self.compact_file_list.setItemWidget(list_item, row)
        count = self.compact_file_list.count()
        self.compact_file_list.setFixedHeight(max(1, count) * CompactFileRow.ROW_HEIGHT + 4)
        if count:
            self.compact_file_list.setCurrentRow(0)
        self._sync_compact_surface()
        if not self.is_expanded:
            self._resize_overlay(652, self._compact_height())

    def _on_composer_text_changed(self, text: str) -> None:
        q = text.strip()
        is_active = bool(q)
        busy = (
            getattr(self, "_presentation_state", None) is not None
            and self._presentation_state.phase in ("waiting", "writing", "searching")
        ) or self._pending_chat_query is not None
        self.chat_composer_send.setEnabled(is_active and not busy)
        self._sync_compact_surface()
        if hasattr(self, "return_keycap"):
            self.return_keycap.setProperty("active", "true" if is_active else "false")
            self.return_keycap.style().unpolish(self.return_keycap)
            self.return_keycap.style().polish(self.return_keycap)

        if not q:
            if getattr(self, "rat_stage", None):
                self.rat_stage.set_state("idle")
            if hasattr(self, "speech_bubble") and hasattr(self, "chat_stream") and self.chat_stream.is_empty():
                self.speech_bubble.reset_welcome()
            return
        if getattr(self, "rat_stage", None):
            self.rat_stage.set_state("listening", "Chuột · Đang nghe")

    def _on_composer_height_changed(self, height: int) -> None:
        self.quick_bar.setFixedHeight(height)
        if hasattr(self, "chat_stream") and not self.is_expanded:
            self._resize_overlay(652, self._compact_height())

    # -----------------------------------------------------------------
    # PAGE 0: CHAT HOME
    # -----------------------------------------------------------------
    def _create_home_view(self) -> QWidget:
        return build_home_view(self)

    def _create_files_view(self) -> QWidget:
        return build_files_view(self)

    def _create_schedule_view(self) -> QWidget:
        return build_schedule_view(self)

    def _create_club_view(self) -> QWidget:
        return build_club_view(self)

    # -----------------------------------------------------------------
    # SECTION NAVIGATION & SWITCHING
    # -----------------------------------------------------------------
    def switch_section(self, idx: int) -> None:
        if idx < 0 or idx >= len(SECTION_TABS):
            return
        if idx != 0 and self._chat_file_request is not None:
            self._chat_file_request = None
            self._pending_chat_query = None
            self._request_counter += 1
        self.current_section_idx = idx
        self.content_stack.setCurrentIndex(idx)
        show_file_search = idx == 1
        self.search_icon.setVisible(show_file_search)
        self.search_input.setVisible(show_file_search)
        self.btn_send.setVisible(show_file_search)
        self.action_footer.setVisible(idx != 0)
        for hotkey_widget in self.footer_hotkey_widgets:
            hotkey_widget.setVisible(idx != 0)

        # Update pill states
        for i, btn in enumerate(self.section_buttons):
            btn.setProperty("active", "true" if i == idx else "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)

        if hasattr(self, "quick_bar"):
            self.quick_bar.setVisible(idx == 0)

        sec_id = SECTION_TABS[idx][0]
        if sec_id == "home":
            if self.is_expanded:
                self.set_expanded(True)
            else:
                self.set_expanded(False)
            self._refresh_home_agenda()
            self._load_recent_files()
            self.footer_status.setText("Chuột đang nghe. Cứ hỏi tự nhiên nha.")
            if hasattr(self, "chat_composer_input"):
                self.chat_composer_input.setFocus()
        else:
            self.set_expanded(True)
            if sec_id == "files":
                self._execute_search()
                self.search_input.setFocus()
            elif sec_id == "schedule":
                self._refresh_schedule_view()
                self.footer_status.setText(f"Thời khóa biểu · {self.current_member.name}")
            elif sec_id == "club":
                self._refresh_club_view()
                self.footer_status.setText("Khung giờ rảnh nhóm & Ma trận CLB")

    def cycle_section(self, delta: int) -> None:
        new_idx = (self.current_section_idx + delta) % len(SECTION_TABS)
        self.switch_section(new_idx)

    # -----------------------------------------------------------------
    # DATA LOADING & REFRESH LOGIC
    # -----------------------------------------------------------------
    def _load_initial_data(self) -> None:
        stats = self.db.get_stats()
        self.footer_status.setText(f"{stats.get('total_files', 0)} tệp trong kho")
        self._refresh_home_agenda()
        self._load_recent_files()
        self.switch_section(0)

    def _load_recent_files(self) -> None:
        try:
            recent_docs = self.db.get_recent_documents(limit=10)
            self.recent_list.clear()

            for doc in recent_docs:
                item = SearchResultItem(
                    file_path=doc.get("file_path", ""),
                    file_name=doc.get("file_name", ""),
                    file_ext=doc.get("file_ext", ""),
                    file_size=doc.get("file_size", 0),
                    modified_at=doc.get("modified_at", time.time()),
                    score=100.0,
                    explanation="Tệp tin gần đây",
                    snippet=f"Đường dẫn: {doc.get('file_path', '')}",
                )
                list_item = QListWidgetItem(self.recent_list)
                list_item.setData(Qt.ItemDataRole.UserRole, item)
                self.recent_list.addItem(list_item)

            if self.recent_list.count() > 0:
                self.recent_list.setCurrentRow(0)
            if hasattr(self, "feedback"):
                self.feedback.refresh(self.recent_list, "")
        except Exception as e:
            logger.debug(f"Error loading recent files: {e}")

    def _refresh_home_agenda(self) -> None:
        refresh_home_agenda(self)

    def _refresh_schedule_view(self) -> None:
        refresh_schedule_view(self)

    def _refresh_club_view(self) -> None:
        refresh_club_view(self)
    # -----------------------------------------------------------------
    # SEARCH & CARD INJECTION LOGIC
    # -----------------------------------------------------------------
    def _on_search_text_changed(self) -> None:
        self.search_controller.on_search_text_changed()

    def _select_file_filter(self, idx: int) -> None:
        self.search_controller.select_file_filter(idx)

    def _execute_search(self) -> None:
        self.search_controller.execute_search()

    @pyqtSlot(int, dict)
    def _on_search_completed(self, request_id: int, response: Dict[str, Any]) -> None:
        self.search_controller.on_search_completed(request_id, response)

    def _on_result_selected(self, row: int) -> None:
        self.search_controller.on_result_selected(row)

    def _on_item_double_clicked(self, item: QListWidgetItem) -> None:
        self.search_controller.on_item_double_clicked(item)

    def _is_list_focused(self) -> bool:
        return self.search_controller.is_list_focused()

    def _active_file_list(self) -> QListWidget:
        return self.search_controller.active_file_list()

    def navigate_active_list(self, delta: int) -> None:
        self.search_controller.navigate_active_list(delta)

    def _activate_current_item(self) -> None:
        self.search_controller.activate_current_item()

    def _reveal_current_in_finder(self) -> None:
        self.search_controller.reveal_current_in_finder()

    def _open_current_in_terminal(self) -> None:
        self.search_controller.open_current_in_terminal()

    def _preview_quick_look(self) -> None:
        self.search_controller.preview_quick_look()

    def _copy_current_path(self) -> None:
        self.search_controller.copy_current_path()

    def _copy_current_content(self) -> None:
        self.search_controller.copy_current_content()
    # -------------------------------------------------------------
    # CHATBOT & QUICK HELPERS
    # -------------------------------------------------------------
    def _complete_chat_turn(self, answer: str) -> None:
        self.chat_controller.complete_chat_turn(answer)

    def _deliver_assistant_reply(
        self,
        answer: str,
        latency_ms: float = 0.0,
        strategy: str = "Direct",
        confidence: float = 1.0,
        reasoning_steps: Optional[List[str]] = None,
        custom_widget: Optional[QWidget] = None,
        strategy_badge: Optional[str] = None,
        inline_files: Optional[List[Any]] = None,
        step_number: Optional[int] = None,
        step_suggestions: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> None:
        self.chat_controller.deliver_assistant_reply(
            answer=answer,
            latency_ms=latency_ms,
            strategy=strategy,
            confidence=confidence,
            reasoning_steps=reasoning_steps,
            custom_widget=custom_widget,
            strategy_badge=strategy_badge,
            inline_files=inline_files,
            step_number=step_number,
            step_suggestions=step_suggestions,
            **kwargs,
        )

    def request_reset_chat(self) -> None:
        self.chat_controller.request_reset_chat()

    def _reset_chat(self) -> None:
        self.chat_controller.reset_chat()

    def _submit_chat_prompt(self, query: str) -> None:
        self.chat_controller.submit_chat_prompt(query)

    def _quick_search(self, query: str) -> None:
        self.search_controller.quick_search(query)

    def _select_sched_day(self, code: str, idx: int) -> None:
        self.selected_day_code = code
        for i, btn in enumerate(self.day_buttons):
            btn.setProperty("active", "true" if i == idx else "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        self._refresh_schedule_view()

    def _on_sched_member_changed(self, idx: int) -> None:
        if 0 <= idx < len(self.members):
            self.current_member = self.members[idx]
            self.profile_badge.setText(self.current_member.name)
            self._refresh_schedule_view()
            self._refresh_home_agenda()

    def _copy_current_schedule(self) -> None:
        m = self.current_member
        lines = [f"=== THỜI KHÓA BIỂU: {m.name} ({m.mssv}) ==="]
        for day_code, day_name, _ in DAYS:
            sessions = m.schedule.get(day_code, [])
            if sessions:
                lines.append(f"\n[{day_name}]")
                for s in sorted(sessions, key=lambda x: x.start_period):
                    deg = "[ThS]" if s.degree_level == "master" else "[ĐH]"
                    lines.append(f"  • Tiết {s.start_period}-{s.end_period}: {deg} {s.course_name} (Phòng {s.room})")
        full_text = "\n".join(lines)
        QApplication.clipboard().setText(full_text)
        self.show_toast("Đã sao chép TKB vào clipboard")

    def _copy_golden_slots(self) -> None:
        slots = self.compositor.find_golden_windows(min_ratio=0.8)
        lines = ["=== KHUNG GIỜ VÀNG CLB (>= 80% RẢNH) ==="]
        for s in slots:
            lines.append(f"• {s.day_name} — Tiết {s.start_period}-{s.end_period} ({s.time_range}): {s.free_count}/{s.total_count} bạn rảnh")
        full_text = "\n".join(lines)
        QApplication.clipboard().setText(full_text)
        self.show_toast("Đã sao chép khung giờ rảnh vào clipboard")

    def show_toast(self, message: str, timeout_ms: int = 2500) -> None:
        self._toast_timer.stop()
        self._restore_toast()
        self._toast_restore = (message, self.footer_status.text(), self.footer_status.styleSheet())
        self.footer_status.setText(message)
        self.footer_status.setStyleSheet("color: #69583D; font-weight: 500;")
        if not self.is_expanded and not self.compact_footer.isHidden():
            self.compact_hint.set_full_text(message)
        self._toast_timer.start(timeout_ms)

    def _restore_toast(self) -> None:
        if self._toast_restore is None:
            return
        message, old_text, old_style = self._toast_restore
        self._toast_restore = None
        # A newer search/reply status wins over an old copy confirmation.
        if self.footer_status.text() == message:
            self.footer_status.setText(old_text)
        self.footer_status.setStyleSheet(old_style)
        if self.compact_hint.full_text == message:
            self._sync_compact_surface()

    def _open_action_menu(self) -> None:
        active_list = self._active_file_list()
        curr_row = active_list.currentRow()
        curr_item = active_list.item(curr_row)
        search_item = curr_item.data(Qt.ItemDataRole.UserRole) if curr_item else None
        self._current_action_item = search_item

        self._dialog_active = True
        try:
            dialog = ActionMenuDialog(search_item, self)
            dialog.action_triggered.connect(self._handle_action)
            pos = self.mapToGlobal(QPoint((self.width() - dialog.width()) // 2, (self.height() - dialog.height()) // 2))
            dialog.move(pos)
            dialog.exec()
        finally:
            self._dialog_active = False
            if self.current_section_idx == 0:
                self.chat_composer_input.setFocus()
            else:
                self.search_input.setFocus()

    def _handle_action(self, action_id: str) -> None:
        item = getattr(self, "_current_action_item", None)
        if action_id == "open":
            self._activate_current_item()
        elif action_id == "quicklook":
            self._preview_quick_look()
        elif action_id == "finder":
            self._reveal_current_in_finder()
        elif action_id == "terminal":
            self._open_current_in_terminal()
        elif action_id == "copy_path":
            self._copy_current_path()
        elif action_id == "copy_content":
            self._copy_current_content()
        elif action_id == "ask_ai":
            if item:
                self.switch_section(0)
                name = getattr(item, "file_name", "tệp")
                self.chat_composer_input.setText(f"Tóm tắt nội dung chính của tệp {name}: ")
                self.chat_composer_input.setFocus()
        elif action_id == "reindex_file":
            fp = getattr(item, "file_path", "")
            if fp and os.path.exists(fp):
                try:
                    from rat.crawler.indexer import Indexer
                    indexer = Indexer(self.db)
                    success = indexer.index_single_file(fp, force=True)
                    if success:
                        self.show_toast(f"Đã cập nhật chỉ mục: {getattr(item, 'file_name', 'tệp')}")
                    else:
                        self.show_toast(f"Chưa thể cập nhật: {getattr(item, 'file_name', 'tệp')}")
                except Exception as e:
                    logger.debug(f"Reindex error: {e}")
                    self.show_toast("Lỗi khi quét lại tệp")
            else:
                self.show_toast("Không tìm thấy tệp để quét lại")
        elif action_id == "schedule":
            self.switch_section(2)
        elif action_id == "widget":
            self.switch_section(0)
        elif action_id == "settings":
            self._open_settings()

    def _open_settings(self) -> None:
        self._dialog_active = True
        try:
            dialog = SettingsDialog(self)
            dialog.exec()
        finally:
            self._dialog_active = False
            if self.current_section_idx == 0:
                self.chat_composer_input.setFocus()
            elif self.current_section_idx == 1:
                self.search_input.setFocus()

    def _present_compact_reply(
        self, answer: str, status: str, *, has_details: bool = False, file_summary: bool = False
    ) -> None:
        if hasattr(self, "reply_reader"):
            curr_q = getattr(self, "_presentation_state", None) and self._presentation_state.query or ""
            if hasattr(self.reply_reader, "update_live_turn"):
                self.reply_reader.update_live_turn(answer, query=curr_q)
            elif hasattr(self.reply_reader, "set_streaming_reply"):
                self.reply_reader.set_streaming_reply(answer)
            else:
                self.reply_reader.set_reply(answer)
            if hasattr(self, "_conversation") and hasattr(self.reply_reader, "set_session_tag"):
                self.reply_reader.set_session_tag(self._conversation.get_tag_label())
        clean = answer.replace("**", "").replace("`", "")
        self.speech_bubble.set_reply(
            clean, status, copy_text=answer, has_details=has_details, file_summary=file_summary
        )
        if self.is_expanded or self.is_reading_reply:
            self.speech_bubble.hide_bubble()
        else:
            self.speech_bubble.show_bubble()
            if not self.mascot_peeking.is_speaking:
                self.mascot_peeking.pop_out_speaking()

    def _on_reasoning_token(self, handle: Dict[str, Any], token: str) -> None:
        self.chat_controller.on_reasoning_token(handle, token)

    def _on_reasoning_finished(
        self,
        handle: Dict[str, Any],
        answer: str,
        steps: List[str],
        latency_ms: float,
        strategy: str,
        badge: str,
    ) -> None:
        self.chat_controller.on_reasoning_finished(
            handle, answer, steps, latency_ms, strategy, badge
        )

    def _on_chat_worker_finished(self, worker: StreamReasoningWorker) -> None:
        self.chat_controller.on_chat_worker_finished(worker)

    def _retry_chat(self) -> None:
        self.chat_controller.retry_chat()

    # -----------------------------------------------------------------
    # LIFECYCLE & WINDOW EVENTS
    # -----------------------------------------------------------------
    def show_omnibar(self, initial_section: int = 0) -> None:
        """Summon Omnibar window instantly (< 16ms) with pre-warmed state."""
        self._is_opening = True
        self._was_activated = False
        try:
            from rat.os.app import activate_macos_app
            activate_macos_app()
        except Exception:
            pass

        was_reading = self.is_reading_reply
        self.switch_section(0)
        self.set_expanded(False)
        if was_reading:
            self.set_reply_reader_open(True)

        # Use the same lower-screen placement for summon, expansion and collapse.
        self._resize_overlay(652, self._compact_height())

        # Configure macOS fullscreen auxiliary overlay so it floats above full-screen apps
        configure_macos_fullscreen_overlay(self)

        self.show()
        self._resize_overlay(self.width(), self.height())
        self.raise_()
        self.activateWindow()
        if hasattr(self, "speech_bubble"):
            if not self.is_reading_reply and (self.speech_bubble.has_reply or self._pending_chat_query is not None):
                self.speech_bubble.show_bubble()
            else:
                self.speech_bubble.hide_bubble()
        if hasattr(self, "mascot_peeking"):
            self.mascot_peeking.show()
            if self.speech_bubble.has_reply:
                self.mascot_peeking.pop_out_speaking()
            else:
                self.mascot_peeking.retreat_to_idle()
        if hasattr(self, "chat_composer_input"):
            self.chat_composer_input.setFocus()
        QTimer.singleShot(500, self._finish_opening)

    def _finish_opening(self) -> None:
        self._is_opening = False
        if self.isActiveWindow():
            self._was_activated = True

    def changeEvent(self, event: QEvent) -> None:
        if event.type() == QEvent.Type.ActivationChange:
            if self.isActiveWindow():
                self._was_activated = True
            elif (
                not getattr(self, "_dialog_active", False)
                and not getattr(self, "_is_opening", False)
                and getattr(self, "_was_activated", False)
            ):
                self.hide()
                self._was_activated = False
        super().changeEvent(event)

    def hideEvent(self, event) -> None:
        self._is_opening = False
        self._was_activated = False
        super().hideEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if event.buttons() == Qt.MouseButton.LeftButton and not self._drag_pos.isNull():
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def shutdown(self) -> None:
        """Graceful zero-crash thread cleanup."""
        self._toast_timer.stop()
        self._toast_restore = None
        self._chat_generation += 1
        self._pending_chat_query = None
        self._current_reasoner = None
        workers = list(self._reasoning_workers)
        for worker in workers:
            worker.requestInterruption()
            # No delayed callback may touch widgets while the window is closing.
            worker.token_received.disconnect()
            worker.reasoning_finished.disconnect()
        for worker in workers:
            if worker.isRunning():
                # Streaming I/O has a 30-second timeout; never terminate an inference thread.
                worker.wait(31000)
        self._reasoning_workers.clear()
        try:
            if hasattr(self, "search_timer") and self.search_timer.isActive():
                self.search_timer.stop()
        except Exception:
            pass

        if hasattr(self, "search_thread") and self.search_thread is not None:
            try:
                if self.search_thread.isRunning():
                    self.search_thread.quit()
                    if not self.search_thread.wait(1500):
                        self.search_thread.terminate()
                        self.search_thread.wait(500)
                self.search_thread.deleteLater()
            except Exception as e:
                logger.debug(f"Omnibar shutdown thread cleanup note: {e}")
            finally:
                self.search_thread = None

        if hasattr(self, "qa_thread") and self.qa_thread is not None:
            try:
                if self.qa_thread.isRunning():
                    self.qa_thread.quit()
                    if not self.qa_thread.wait(1500):
                        self.qa_thread.terminate()
                        self.qa_thread.wait(500)
                self.qa_thread.deleteLater()
            except Exception as e:
                logger.debug(f"Omnibar QA thread cleanup note: {e}")
            finally:
                self.qa_thread = None

    def closeEvent(self, event) -> None:
        app = QApplication.instance()
        if app and not getattr(app, "_is_quitting", False):
            event.ignore()
            self.hide()
            return

        self.shutdown()
        super().closeEvent(event)
