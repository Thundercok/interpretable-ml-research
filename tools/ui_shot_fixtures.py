"""Deterministic fixtures and stubs for shooting live UI states headless."""
from __future__ import annotations

from pathlib import Path
from PyQt6.QtCore import QObject, pyqtProperty, pyqtSignal

from rat.ui.quick_pdf_controller import QuickPDFController

LIVE_STATES = ("answer", "page", "search", "finder", "apps", "reading", "busy", "error")
LIVE_WIDTHS = (520, 700)


class FakeSelection:
    """Minimal selection object providing path and page_count for PDF-bound views."""
    def __init__(self, path: Path | str, page_count: int = 24):
        self.path = Path(path)
        self.page_count = page_count


class FakeWorker:
    """Stands in for an active background worker thread."""
    pass


class MiniStub(QObject):
    """Deterministic stub for MiniDesk with complete state and zero network/model dependencies."""
    changed = pyqtSignal()
    settingsRequested = pyqtSignal()
    helpRequested = pyqtSignal()

    @pyqtProperty("QVariantMap", notify=changed)
    def snapshot(self):
        return {
            "surface": "result",
            "view": "translation",
            "busy": False,
            "text": "Xin chào thế giới — đây là bản dịch mẫu để kiểm tra giao diện.",
            "draftText": "",
            "translationDirection": "Anh → Việt",
            "hasWorkbench": True,
            "bubbleCollapsed": False,
            "interactionExtent": "expanded",
            "composerVisible": True,
            "finderHits": [],
            "phase": "idle",
            "canRetryTranslation": False,
            "canPasteText": False,
            "canPasteImage": False,
            "translationSettingsSuggested": False,
            "selectionNeedsPermission": False,
            "unsupportedLanguage": False,
            "status": "",
        }

    @pyqtProperty("QVariantMap", notify=changed)
    def preferences(self):
        return {
            "roots": ["/Users/thundercock2/Documents"],
            "target_language": "vi",
            "hotkey_chord": "option_shift_space",
        }


def build_live_controller(state: str, db_path: str | Path) -> QuickPDFController:
    """Construct an isolated QuickPDFController populated with deterministic data for a specific state."""
    ctrl = QuickPDFController(db_path=str(db_path), auto_init_finder=False)
    ctrl.ready()

    if state == "answer":
        query = "Điều kiện chuyển tiếp và công nhận tín chỉ tương đương?"
        answer = (
            "## Điều kiện công nhận tín chỉ\n\n"
            "1. **Điểm số tối thiểu**: Học phần đạt từ điểm C trở lên.\n"
            "2. **Tương đương chương trình**: Khối lượng kiến thức và đề cương chi tiết đạt tối thiểu 80% độ tương đồng.\n"
            "3. **Thời hạn bảo lưu**: Không quá 5 năm tính đến thời điểm nộp hồ sơ."
        )
        sources = [
            {
                "path": "/docs/quy_che_2026.pdf",
                "page": 14,
                "section": "Điều 8. Chuyển đổi tín chỉ",
                "title": "Quy chế học vụ 2026.pdf",
                "snippet": "Học phần được xem xét công nhận tín chỉ tương đương khi đạt điểm từ C trở lên.",
            },
            {
                "path": "/docs/quy_che_2026.pdf",
                "page": 19,
                "section": "Điều 12. Thời hạn bảo lưu",
                "title": "Quy chế học vụ 2026.pdf",
                "snippet": "Thời hạn bảo lưu kết quả học tập tối đa không quá 5 năm.",
            },
        ]
        turn = ctrl.conversation.begin_turn(query)
        ctrl._current_turn_id = turn.turn_id
        ctrl._current_execution_id = turn.execution_id
        ctrl._displayed_turn_id = turn.turn_id
        ctrl._current_worker = None
        ctrl._last_user_query = query
        ctrl._last_assistant_answer = answer
        ctrl.conversation.complete_turn(
            turn.turn_id,
            answer,
            execution_id=turn.execution_id,
            source_refs=sources,
            answer_verification_status="PASS",
        )
        ctrl._view = "answer"
        ctrl._expanded = True
        ctrl._status = "Đã trả lời · có thể hỏi tiếp"

    elif state == "page":
        ctrl._selection = FakeSelection("/docs/quy_che_2026.pdf", page_count=24)
        ctrl._last_assistant_answer = "Đoạn trích dẫn từ văn bản gốc."
        ctrl._last_user_query = "Quy định về thời hạn bảo lưu"
        ctrl._page = {
            "page": 14,
            "page_count": 24,
            "page_label": "14",
            "filename": "Quy chế học vụ 2026.pdf",
            "content": (
                "Điều 8. Công nhận tín chỉ tương đương và chuyển đổi điểm\n"
                "1. Sinh viên được xem xét công nhận tín chỉ đối với các học phần đã tích lũy tại "
                "cơ sở đào tạo khác nếu có đề cương chi tiết tương đương từ 80% trở lên và kết quả đánh giá đạt từ điểm C trở lên.\n"
                "2. Hội đồng chuyên môn xem xét từng trường hợp cụ thể và trình Hiệu trưởng phê duyệt."
            ),
            "truncated": False,
        }
        ctrl._page_return_view = "answer"
        ctrl._view = "page"
        ctrl._expanded = True
        ctrl._status = "Đang xem trang 14 · Quy chế học vụ 2026.pdf"

    elif state == "search":
        ctrl._selection = FakeSelection("/docs/quy_che_2026.pdf", page_count=24)
        ctrl._search = {
            "query": "học bổng",
            "matched_pages": 2,
            "page_count": 24,
            "searched_range": (1, 24),
            "items": [
                {
                    "page": 7,
                    "page_label": "7",
                    "snippet": "Chính sách học bổng khuyến khích học tập dành cho sinh viên có kết quả xuất sắc...",
                    "path": "/docs/quy_che_2026.pdf",
                },
                {
                    "page": 11,
                    "page_label": "11",
                    "snippet": "Tiêu chuẩn xét cấp học bổng doanh nghiệp và học bổng hỗ trợ tài chính kỳ 1...",
                    "path": "/docs/quy_che_2026.pdf",
                },
            ],
        }
        ctrl._view = "search"
        ctrl._expanded = True
        ctrl._status = "Tìm thấy 2 trang khớp với 'học bổng'"

    elif state == "finder":
        ctrl._finder_query = "quy chế"
        ctrl._finder_hits = [
            {
                "title": "Quy chế học vụ 2026.pdf",
                "kind": "pdf",
                "is_pdf": True,
                "path": "/docs/quy_che_2026.pdf",
                "display_path": "~/Documents/Quy chế học vụ 2026.pdf",
                "is_first_of_section": True,
                "snippet": "Quy định đào tạo trình độ đại học và đánh giá kết quả học tập...",
            },
            {
                "title": "Quy chế tuyển sinh 2026.pdf",
                "kind": "pdf",
                "is_pdf": True,
                "path": "/docs/tuyen_sinh_2026.pdf",
                "display_path": "~/Documents/Quy chế tuyển sinh 2026.pdf",
                "is_first_of_section": False,
                "snippet": "Chỉ tiêu và phương thức tuyển sinh năm học 2026–2027...",
            },
        ]
        ctrl._view = "finder"
        ctrl._expanded = True
        ctrl._status = "Tìm thấy 2 gợi ý cho 'quy chế'"

    elif state == "apps":
        ctrl._cached_apps_list = [
            {
                "name": "Safari",
                "bundle_id": "com.apple.Safari",
                "path": "/Applications/Safari.app",
                "description": "Trình duyệt web",
            },
            {
                "name": "Terminal",
                "bundle_id": "com.apple.Terminal",
                "path": "/System/Applications/Utilities/Terminal.app",
                "description": "Giao diện dòng lệnh macOS",
            },
            {
                "name": "Notes",
                "bundle_id": "com.apple.Notes",
                "path": "/System/Applications/Notes.app",
                "description": "Ghi chú nhanh",
            },
        ]
        ctrl._view = "apps"
        ctrl._expanded = True
        ctrl._status = "Ứng dụng đã cài đặt (3) · Bấm icon hoặc Enter để mở"

    elif state == "reading":
        ctrl.openReadingDesk()
        ctrl._view = "reading"
        ctrl._expanded = True
        ctrl._status = "Bàn xem · bài và lá số"

    elif state == "busy":
        ctrl._current_worker = FakeWorker()
        ctrl._last_user_query = "Tóm tắt các điểm quan trọng trong học kỳ 1"
        ctrl._status = "Chuột đang đọc tài liệu và chuẩn bị câu trả lời…"
        ctrl._view = "busy"
        ctrl._expanded = True

    elif state == "error":
        ctrl._show_error("not_pdf")
        ctrl._expanded = True

    return ctrl
