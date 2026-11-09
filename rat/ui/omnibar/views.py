"""
rat.ui.omnibar.views — View builders and presentation rendering for Omnibar sections.
Includes Home (Casual Chat & Agenda), Files (Search & Preview), Schedule (Timetable),
and Club (Group Free Time Matrix).
"""

from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import List, TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from rat.timetable.compositor import availability_to_color, degree_to_style
from rat.timetable.model import DAYS, resolve_room_location
from rat.ui.apple_item_delegate import AppleSpotlightDelegate
from rat.ui.chat_stream import ChatStreamWidget
from rat.ui.preview_panel import PreviewPanel

from .companion import ConversationRibbon
from .event_filters import OmnibarListFilter

if TYPE_CHECKING:
    from .window import OmnibarWindow

logger = logging.getLogger('rat.ui.omnibar.views')

SECTION_TABS = [
    ("home", "Trò chuyện", "Hỏi đáp & lịch hôm nay"),
    ("files", "Tệp tin", "Tìm kiếm tệp & nội dung"),
    ("schedule", "TKB / Lịch", "Thời khóa biểu sinh viên"),
    ("club", "CLB", "Khung giờ rảnh nhóm"),
]

FILTER_CATEGORIES = [
    ("all", "Tất cả", []),
    ("docs", "Văn bản", [".docx", ".doc", ".pdf", ".txt", ".md"]),
    ("sheets", "Bảng tính", [".xlsx", ".xls", ".csv"]),
    ("slides", "Slide", [".pptx", ".ppt"]),
    ("code", "Code", [".py", ".js", ".ts", ".html", ".css", ".json", ".sh", ".sql"]),
    ("images", "Hình ảnh", [".png", ".jpg", ".jpeg", ".webp"]),
]


def build_home_view(window: OmnibarWindow) -> QWidget:
    widget = QWidget()
    root_layout = QVBoxLayout(widget)
    root_layout.setContentsMargins(0, 0, 0, 0)
    root_layout.setSpacing(4)

    first_name = window.current_member.name.split()[-1] if window.current_member.name else "bạn"
    window.conversation_ribbon = ConversationRibbon(widget)
    window.conversation_ribbon.reset_requested.connect(lambda: window.request_reset_chat())
    if hasattr(window, "_conversation"):
        window.conversation_ribbon.set_session_info(
            window._conversation.get_tag_label(),
            len(window._conversation._turns)
        )
    root_layout.addWidget(window.conversation_ribbon, 0)

    window.chat_stream = ChatStreamWidget(user_name=first_name)
    def register_conversation_widget(widget: QWidget) -> None:
        widget.setProperty("conversation_navigation", True)
        widget.installEventFilter(window.input_filter)

    window.chat_stream.navigation_widget_created.connect(register_conversation_widget)
    register_conversation_widget(window.chat_stream)
    register_conversation_widget(window.chat_stream.jump_button)
    window.chat_stream.prompt_clicked.connect(
        lambda prompt: window._submit_chat_prompt(prompt) if prompt == "Hôm nay học gì?" else window._prefill_chat(prompt)
    )
    window.chat_stream.retry_requested.connect(window._retry_chat)
    window.chat_stream.settings_requested.connect(window._open_settings)
    window.chat_stream.show()  # Visible surface with welcome prompts
    root_layout.addWidget(window.chat_stream, 1)

    # Hidden Compatibility Container for Tests
    compat_box = QWidget(widget)
    compat_box.hide()
    compat_layout = QVBoxLayout(compat_box)

    # Micro footer (kept inside compat container so it never becomes a top-level window)
    window.chat_micro_footer = QWidget(compat_box)
    window.chat_micro_footer.hide()
    window.chat_micro_status = QLabel("● Sẵn sàng", window.chat_micro_footer)
    compat_layout.addWidget(window.chat_micro_footer)

    window.today_date_label = QLabel("Hôm nay", compat_box)
    window.profile_badge = QLabel(window.current_member.name, compat_box)
    window.live_countdown_banner = QFrame(compat_box)
    b_layout = QHBoxLayout(window.live_countdown_banner)
    window.live_banner_text = QLabel("Đang kiểm tra lịch học...", window.live_countdown_banner)
    b_layout.addWidget(window.live_banner_text)

    window.agenda_scroll = QScrollArea(compat_box)
    window.agenda_content = QWidget(window.agenda_scroll)
    window.agenda_layout = QVBoxLayout(window.agenda_content)
    window.agenda_scroll.setWidget(window.agenda_content)

    window.recent_list = QListWidget(compat_box)
    window.recent_list_filter = OmnibarListFilter(window)
    window.recent_list.installEventFilter(window.recent_list_filter)

    compat_layout.addWidget(window.today_date_label)
    compat_layout.addWidget(window.profile_badge)
    compat_layout.addWidget(window.live_countdown_banner)
    compat_layout.addWidget(window.agenda_scroll)
    compat_layout.addWidget(window.recent_list)

    root_layout.addWidget(compat_box)
    return widget



def build_files_view(window: OmnibarWindow) -> QWidget:
    widget = QWidget()
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)

    # Search Input Header Row for Files
    search_row = QFrame()
    search_row.setObjectName("FileSearchRow")
    search_row.setStyleSheet("background-color: #FFFFFF; border-bottom: 1px solid rgba(43, 38, 31, 0.08); padding: 8px 12px;")
    sr_layout = QHBoxLayout(search_row)
    sr_layout.setContentsMargins(0, 0, 0, 0)
    sr_layout.setSpacing(8)

    window.search_icon = QLabel("🔍")
    window.search_icon.setStyleSheet("font-size: 13px; border: none; background: transparent;")
    sr_layout.addWidget(window.search_icon)

    window.search_input = QLineEdit()
    window.search_input.setObjectName("SearchInput")
    window.search_input.setPlaceholderText("Tìm tên file, nội dung hoặc loại tài liệu…")
    window.search_input.setClearButtonEnabled(True)
    window.search_input.textChanged.connect(window._on_search_text_changed)
    window.search_input.installEventFilter(window.input_filter)
    sr_layout.addWidget(window.search_input, 1)

    window.btn_send = QPushButton("Tìm")
    window.btn_send.setObjectName("SendButton")
    window.btn_send.setProperty("class", "SendButton")
    window.btn_send.setCursor(Qt.CursorShape.PointingHandCursor)
    window.btn_send.clicked.connect(window._execute_search)
    sr_layout.addWidget(window.btn_send)

    layout.addWidget(search_row)

    # Sub-category filter pills for files
    sub_bar = QFrame()
    sub_bar.setStyleSheet("background-color: #FBF9F5; border-bottom: 1px solid rgba(43, 38, 31, 0.06); padding: 4px 14px;")
    sub_layout = QHBoxLayout(sub_bar)
    sub_layout.setContentsMargins(0, 0, 0, 0)
    sub_layout.setSpacing(6)

    window.file_filter_buttons: List[QPushButton] = []
    for idx, (cat_id, label, _) in enumerate(FILTER_CATEGORIES):
        btn = QPushButton(label)
        btn.setProperty("class", "FilterPill")
        btn.setProperty("active", "true" if idx == 0 else "false")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(lambda checked, i=idx: window._select_file_filter(i))
        sub_layout.addWidget(btn)
        window.file_filter_buttons.append(btn)

    sub_layout.addStretch()
    layout.addWidget(sub_bar)

    # Dual Pane Splitter (50/50)
    window.splitter = QSplitter(Qt.Orientation.Horizontal)
    window.splitter.setChildrenCollapsible(False)
    window.splitter.setStyleSheet("QSplitter::handle { background-color: rgba(43, 38, 31, 0.08); width: 1px; }")

    # Left List
    window.result_list = QListWidget()
    window.result_list.setObjectName("ResultList")
    window.result_list.setFrameShape(QFrame.Shape.NoFrame)
    window.result_list.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
    window.result_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    window.result_list.setItemDelegate(AppleSpotlightDelegate(window))
    window.result_list.currentRowChanged.connect(window._on_result_selected)
    window.result_list.itemDoubleClicked.connect(window._on_item_double_clicked)
    window.list_filter = OmnibarListFilter(window)
    window.result_list.installEventFilter(window.list_filter)
    window.splitter.addWidget(window.result_list)

    # Right Inspector Panel
    window.preview_panel = PreviewPanel()
    window.preview_panel.ask_requested.connect(window.qa_worker.ask_document)
    window.qa_worker.qa_finished.connect(window.preview_panel.set_qa_answer)
    window.splitter.addWidget(window.preview_panel)

    window.splitter.setSizes([490, 490])
    layout.addWidget(window.splitter, 1)
    return widget



def build_schedule_view(window: OmnibarWindow) -> QWidget:
    widget = QWidget()
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(12, 10, 12, 10)
    layout.setSpacing(8)

    # Toolbar: Member Selector, Degree Level, Day Picker
    toolbar = QFrame()
    toolbar.setStyleSheet("background-color: #FFFFFF; border: 1px solid rgba(43, 38, 31, 0.08); border-radius: 8px; padding: 5px 10px;")
    tb_layout = QHBoxLayout(toolbar)
    tb_layout.setContentsMargins(0, 0, 0, 0)
    tb_layout.setSpacing(8)

    combo_style = """
    QComboBox {
        background-color: #F8F5F0;
        color: #26221D;
        border: 1px solid rgba(43, 38, 31, 0.12);
        border-radius: 6px;
        padding: 4px 8px;
        font-size: 11.5px;
    }
    QComboBox:hover {
        background-color: #FFFFFF;
        border-color: #FFB800;
    }
    QComboBox::drop-down {
        border: none;
    }
    QComboBox QAbstractItemView {
        background-color: #FFFFFF;
        color: #26221D;
        border: 1px solid rgba(43, 38, 31, 0.12);
        selection-background-color: #FFF4D4;
        selection-color: #26221D;
    }
    """

    lbl_member = QLabel("Hồ sơ:")
    lbl_member.setStyleSheet("color: #887c70; font-size: 11px;")
    tb_layout.addWidget(lbl_member)
    window.sched_member_combo = QComboBox()
    window.sched_member_combo.setStyleSheet(combo_style)
    for m in window.members:
        suffix = " (Song bằng ĐH+ThS)" if m.is_dual_degree else ""
        window.sched_member_combo.addItem(f"{m.name}{suffix}", m.id)
    window.sched_member_combo.currentIndexChanged.connect(window._on_sched_member_changed)
    tb_layout.addWidget(window.sched_member_combo)

    lbl_degree = QLabel("Bậc học:")
    lbl_degree.setStyleSheet("color: #887c70; font-size: 11px;")
    tb_layout.addWidget(lbl_degree)
    window.sched_degree_combo = QComboBox()
    window.sched_degree_combo.setStyleSheet(combo_style)
    window.sched_degree_combo.addItems(["Tất cả bậc", "Đại học", "Thạc sĩ"])
    window.sched_degree_combo.currentIndexChanged.connect(window._refresh_schedule_view)
    tb_layout.addWidget(window.sched_degree_combo)

    tb_layout.addStretch()

    window.btn_copy_schedule = QPushButton("Sao chép TKB")
    window.btn_copy_schedule.setStyleSheet("""
        QPushButton {
            background-color: #FFFFFF;
            color: #26221D;
            border: 1px solid rgba(43, 38, 31, 0.12);
            border-radius: 6px;
            padding: 4px 10px;
            font-size: 11px;
            font-weight: 600;
        }
        QPushButton:hover {
            background-color: #FFF8E7;
            border-color: #FFB800;
            color: #B27B00;
        }
    """)
    window.btn_copy_schedule.setCursor(Qt.CursorShape.PointingHandCursor)
    window.btn_copy_schedule.clicked.connect(window._copy_current_schedule)
    tb_layout.addWidget(window.btn_copy_schedule)

    layout.addWidget(toolbar)

    # Day selection pills (Hôm nay, T2..CN)
    day_bar = QFrame()
    day_layout = QHBoxLayout(day_bar)
    day_layout.setContentsMargins(0, 0, 0, 0)
    day_layout.setSpacing(4)

    window.day_buttons: List[QPushButton] = []
    days_list = [("TODAY", "Hôm Nay")] + [(d[0], d[1]) for d in DAYS]
    window.selected_day_code = "TODAY"

    for idx, (d_code, d_name) in enumerate(days_list):
        btn = QPushButton(d_name)
        btn.setProperty("class", "FilterPill")
        btn.setProperty("active", "true" if idx == 0 else "false")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(lambda checked, code=d_code, i=idx: window._select_sched_day(code, i))
        day_layout.addWidget(btn)
        window.day_buttons.append(btn)

    day_layout.addStretch()
    layout.addWidget(day_bar)

    # Sessions Content Area
    window.sched_scroll = QScrollArea()
    window.sched_scroll.setWidgetResizable(True)
    window.sched_scroll.setStyleSheet("border: 1px solid rgba(43, 38, 31, 0.08); border-radius: 10px; background-color: #FFFFFF;")
    window.sched_content = QWidget()
    window.sched_layout = QVBoxLayout(window.sched_content)
    window.sched_layout.setContentsMargins(10, 10, 10, 10)
    window.sched_layout.setSpacing(6)
    window.sched_scroll.setWidget(window.sched_content)
    layout.addWidget(window.sched_scroll, 1)

    return widget



def build_club_view(window: OmnibarWindow) -> QWidget:
    widget = QWidget()
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(12, 10, 12, 10)
    layout.setSpacing(8)

    # Header Info Banner
    banner = QFrame()
    banner.setStyleSheet("background-color: #F0FDF4; border: 1px solid #BBF7D0; border-radius: 8px; padding: 8px 12px;")
    b_layout = QHBoxLayout(banner)
    b_layout.setContentsMargins(0, 0, 0, 0)

    banner_text = QLabel("Khung Giờ Vàng CLB: Các khung giờ có từ 80% đến 100% thành viên rảnh để họp nhóm, làm đồ án.")
    banner_text.setStyleSheet("color: #166534; font-size: 11.5px;")
    banner_text.setWordWrap(True)
    b_layout.addWidget(banner_text)

    btn_copy_club = QPushButton("Sao chép")
    btn_copy_club.setStyleSheet("""
        QPushButton {
            background-color: #FFFFFF;
            color: #166534;
            border: 1px solid #BBF7D0;
            border-radius: 6px;
            padding: 4px 10px;
            font-size: 11px;
            font-weight: 600;
        }
        QPushButton:hover {
            background-color: #DCFCE7;
        }
    """)
    btn_copy_club.setCursor(Qt.CursorShape.PointingHandCursor)
    btn_copy_club.clicked.connect(window._copy_golden_slots)
    b_layout.addWidget(btn_copy_club)

    layout.addWidget(banner)

    # Golden Slots Scroll Area
    window.club_scroll = QScrollArea()
    window.club_scroll.setWidgetResizable(True)
    window.club_scroll.setStyleSheet("border: 1px solid rgba(43, 38, 31, 0.08); border-radius: 10px; background-color: #FFFFFF;")
    window.club_content = QWidget()
    window.club_layout = QVBoxLayout(window.club_content)
    window.club_layout.setContentsMargins(10, 10, 10, 10)
    window.club_layout.setSpacing(6)
    window.club_scroll.setWidget(window.club_content)
    layout.addWidget(window.club_scroll, 1)

    return widget



def refresh_home_agenda(window: OmnibarWindow) -> None:
    # Clear existing
    while window.agenda_layout.count():
        child = window.agenda_layout.takeAt(0)
        if child.widget():
            child.widget().deleteLater()

    now = datetime.now()
    weekday_names = ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ Nhật"]
    day_str = weekday_names[now.weekday()]
    date_str = now.strftime("%d/%m/%Y")
    window.today_date_label.setText(f"{day_str}, {date_str}")

    agenda = window.compositor.get_today_agenda(window.current_member, now)
    if not agenda:
        window.live_countdown_banner.setStyleSheet("background-color: rgba(34, 197, 94, 0.1); border: 1px solid rgba(34, 197, 94, 0.2); border-radius: 8px; padding: 8px 12px;")
        window.live_banner_text.setText("Hôm nay bạn rảnh rồi — không có ca học nào trên lịch.")
        window.live_banner_text.setStyleSheet("color: #22c55e; font-size: 12px; font-weight: 600;")

        empty_lbl = QLabel("Tận hưởng ngày nghỉ hoặc tranh thủ làm đồ án nhé.")
        empty_lbl.setStyleSheet("color: #71717a; font-size: 12px; padding: 16px; qproperty-alignment: AlignCenter;")
        window.agenda_layout.addWidget(empty_lbl)
        window.agenda_layout.addStretch()
        return

    # Check live status
    live_item = next((item for item in agenda if item["status"] == "live"), None)
    upcoming_item = next((item for item in agenda if item["status"] == "upcoming"), None)

    if live_item:
        s = live_item["session"]
        window.live_countdown_banner.setStyleSheet("background-color: rgba(34, 197, 94, 0.1); border: 1.5px solid rgba(34, 197, 94, 0.2); border-radius: 8px; padding: 8px 12px;")
        window.live_banner_text.setText(f"Đang diễn ra: {s.course_name} (Phòng {s.room}) · {live_item['countdown']}")
        window.live_banner_text.setStyleSheet("color: #22c55e; font-size: 12px; font-weight: 700;")
    elif upcoming_item:
        s = upcoming_item["session"]
        deg = "[ThS]" if s.degree_level == "master" else "[ĐH]"
        window.live_countdown_banner.setStyleSheet("background-color: rgba(59, 130, 246, 0.1); border: 1.5px solid rgba(59, 130, 246, 0.2); border-radius: 8px; padding: 8px 12px;")
        window.live_banner_text.setText(f"Ca tiếp theo: [{upcoming_item['start_time']}] {deg} {s.course_name} (Phòng {s.room}) · {upcoming_item['countdown']}")
        window.live_banner_text.setStyleSheet("color: #60a5fa; font-size: 12px; font-weight: 700;")
    else:
        window.live_countdown_banner.setStyleSheet("background-color: #f6f2ec; border: 1px solid #e1d8cc; border-radius: 8px; padding: 6px 10px;")
        window.live_banner_text.setText("Đã hoàn thành các ca học hôm nay.")
        window.live_banner_text.setStyleSheet("color: #6a5e52; font-size: 11.5px; font-weight: 600;")

    # Render list of session cards
    for item in agenda:
        s = item["session"]
        st = degree_to_style(s.degree_level)
        card = QFrame()
        card.setObjectName("AgendaSessionCard")
        card.setStyleSheet(f"""
            QFrame#AgendaSessionCard {{
                background-color: {st['bg']};
                border: 1px solid {st['border']};
                border-radius: 6px;
                padding: 4px 8px;
            }}
            QFrame#AgendaSessionCard:hover {{
                background-color: {st['bg_hover']};
            }}
            QLabel {{
                border: none;
                background: transparent;
            }}
        """)
        c_layout = QHBoxLayout(card)
        c_layout.setContentsMargins(4, 3, 6, 3)
        c_layout.setSpacing(8)

        badge_lbl = QLabel(st["badge"])
        badge_lbl.setFixedSize(26, 17)
        badge_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge_lbl.setStyleSheet(f"background-color: {st['tag_bg']}; color: #ffffff; font-size: 8.5px; font-weight: 700; border-radius: 3px; border: none;")
        c_layout.addWidget(badge_lbl, 0, Qt.AlignmentFlag.AlignVCenter)

        v_info = QVBoxLayout()
        v_info.setSpacing(1)
        title_txt = f"<b>{s.course_name}</b> ({s.course_code})"
        t_lbl = QLabel(title_txt)
        t_lbl.setStyleSheet(f"color: {st['text']}; font-size: 11.5px; font-weight: 600;")
        sub_txt = f"{item['start_time']} - {item['end_time']} • Phòng {s.room} • {s.lecturer or 'Chưa rõ'}"
        s_lbl = QLabel(sub_txt)
        s_lbl.setStyleSheet("color: #81766b; font-size: 10px;")
        v_info.addWidget(t_lbl)
        v_info.addWidget(s_lbl)
        c_layout.addLayout(v_info, 1)

        status_tag = QLabel(item["badge"])
        status_tag.setStyleSheet("color: #887c70; font-size: 9.5px; font-weight: 550;")
        c_layout.addWidget(status_tag)

        window.agenda_layout.addWidget(card)



def refresh_schedule_view(window: OmnibarWindow) -> None:
    while window.sched_layout.count():
        child = window.sched_layout.takeAt(0)
        if child.widget():
            child.widget().deleteLater()

    m = window.current_member
    now = datetime.now()
    deg_filter = window.sched_degree_combo.currentText()

    # Day resolution
    if window.selected_day_code == "TODAY":
        weekday_map = {0: "T2", 1: "T3", 2: "T4", 3: "T5", 4: "T6", 5: "T7", 6: "CN"}
        target_day = weekday_map[now.weekday()]
    else:
        target_day = window.selected_day_code

    sessions = m.schedule.get(target_day, [])
    if "Đại học" in deg_filter:
        sessions = [s for s in sessions if s.degree_level == "undergrad"]
    elif "Thạc sĩ" in deg_filter:
        sessions = [s for s in sessions if s.degree_level == "master"]

    sessions = sorted(sessions, key=lambda s: s.start_period)

    day_full_names = {"T2": "Thứ Hai", "T3": "Thứ Ba", "T4": "Thứ Tư", "T5": "Thứ Năm", "T6": "Thứ Sáu", "T7": "Thứ Bảy", "CN": "Chủ Nhật"}
    header_text = f"Lịch học <b>{day_full_names.get(target_day, target_day)}</b> — {len(sessions)} môn học"
    h_lbl = QLabel(header_text)
    h_lbl.setStyleSheet("color: #493f35; font-size: 13.5px; font-weight: 650; padding: 4px 0px;")
    window.sched_layout.addWidget(h_lbl)

    if not sessions:
        no_c = QLabel(f"Không có ca học nào trong ngày {day_full_names.get(target_day, target_day)}.")
        no_c.setStyleSheet("color: #71717a; font-size: 12px; padding: 24px; qproperty-alignment: AlignCenter;")
        window.sched_layout.addWidget(no_c)
        window.sched_layout.addStretch()
        return

    for s in sessions:
        st = degree_to_style(s.degree_level)
        from rat.timetable.model import TDTU_PERIODS
        p_start_str = TDTU_PERIODS.get(s.start_period, ("00:00", "00:00", "", ""))[0]
        p_end_str = TDTU_PERIODS.get(s.end_period, ("23:59", "23:59", "", ""))[1]

        card = QFrame()
        card.setObjectName("SchedSessionCard")
        card.setStyleSheet(f"""
            QFrame#SchedSessionCard {{
                background-color: {st['bg']};
                border: 1px solid {st['border']};
                border-radius: 6px;
                padding: 8px 12px;
            }}
            QLabel {{
                border: none;
                background: transparent;
            }}
        """)
        c_layout = QHBoxLayout(card)
        c_layout.setContentsMargins(0, 0, 0, 0)
        c_layout.setSpacing(10)

        badge_lbl = QLabel(st["badge"])
        badge_lbl.setFixedSize(28, 18)
        badge_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge_lbl.setStyleSheet(f"background-color: {st['tag_bg']}; color: #ffffff; font-size: 9px; font-weight: 700; border-radius: 3px; border: none;")
        c_layout.addWidget(badge_lbl, 0, Qt.AlignmentFlag.AlignVCenter)

        v_info = QVBoxLayout()
        v_info.setSpacing(2)
        c_name = QLabel(f"<b>{s.course_name}</b> ({s.course_code})")
        c_name.setStyleSheet(f"color: {st['text']}; font-size: 13px; font-weight: 600;")
        loc_detail = resolve_room_location(s.room)
        meta = QLabel(f"{p_start_str} - {p_end_str} (Tiết {s.start_period}-{s.end_period}) • Phòng {s.room} ({loc_detail}) • {s.lecturer or 'Chưa rõ'}")
        meta.setStyleSheet("color: #8f9299; font-size: 11px;")
        v_info.addWidget(c_name)
        v_info.addWidget(meta)
        if s.notes:
            n_lbl = QLabel(f"Ghi chú: {s.notes}")
            n_lbl.setStyleSheet("color: #71717a; font-size: 10.5px; font-style: italic;")
            v_info.addWidget(n_lbl)

        c_layout.addLayout(v_info, 1)
        window.sched_layout.addWidget(card)

    window.sched_layout.addStretch()



def refresh_club_view(window: OmnibarWindow) -> None:
    while window.club_layout.count():
        child = window.club_layout.takeAt(0)
        if child.widget():
            child.widget().deleteLater()

    golden_slots = window.compositor.find_golden_windows(min_ratio=0.8)
    if not golden_slots:
        empty_lbl = QLabel("Chưa tìm thấy khung giờ vàng trên 80% rảnh tuần này.")
        empty_lbl.setStyleSheet("color: #71717a; font-size: 12px; padding: 20px; qproperty-alignment: AlignCenter;")
        window.club_layout.addWidget(empty_lbl)
        window.club_layout.addStretch()
        return

    for slot in golden_slots:
        av = availability_to_color(slot.ratio)
        card = QFrame()
        card.setObjectName("ClubSlotCard")
        card.setStyleSheet(f"""
            QFrame#ClubSlotCard {{
                background-color: {av['bg']};
                border: 1px solid {av['border']};
                border-radius: 6px;
            }}
            QLabel {{
                border: none;
                background: transparent;
            }}
        """)
        c_layout = QHBoxLayout(card)
        c_layout.setContentsMargins(10, 8, 10, 8)
        c_layout.setSpacing(10)

        ratio_badge = QLabel(f"{int(slot.ratio * 100)}%")
        ratio_badge.setFixedSize(38, 20)
        ratio_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ratio_badge.setStyleSheet(f"background-color: rgba(52, 211, 153, 0.15); color: {av['text']}; border: 1px solid {av['border']}; font-size: 10px; font-weight: 700; border-radius: 4px;")
        c_layout.addWidget(ratio_badge, 0, Qt.AlignmentFlag.AlignVCenter)

        card.setMinimumHeight(48)
        v_info = QVBoxLayout()
        v_info.setContentsMargins(0, 0, 0, 0)
        v_info.setSpacing(3)
        title = QLabel(f"<b>{slot.day_name}</b> — Tiết {slot.start_period}-{slot.end_period} ({slot.time_range})")
        title.setStyleSheet(f"color: {av['text']}; font-size: 12px; font-weight: 600; font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Text', sans-serif;")
        free_names = ", ".join(slot.free_members) if slot.free_members else "Không có ai"
        desc = QLabel(f"{slot.free_count} trên {slot.total_count} bạn rảnh: {free_names}")
        desc.setStyleSheet("color: #81766b; font-size: 10.5px; font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Text', sans-serif;")
        desc.setWordWrap(True)
        v_info.addWidget(title)
        v_info.addWidget(desc)
        c_layout.addLayout(v_info, 1)

        window.club_layout.addWidget(card)

    window.club_layout.addStretch()

