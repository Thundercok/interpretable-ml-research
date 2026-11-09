"""
rat.ui.omnibar.search_controller — Search execution, debouncing, card injection, and file actions.
"""

from __future__ import annotations

import logging
import re
import sys
import time
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtWidgets import QApplication, QListWidget, QListWidgetItem

from rat.engine.reranker import SearchResultItem, sort_search_results
from rat.timetable.model import resolve_room_location
from rat.ui.preview_panel import (
    open_file_default,
    open_in_terminal,
    reveal_in_finder,
    trigger_quicklook,
)
from .views import FILTER_CATEGORIES

if TYPE_CHECKING:
    from .window import OmnibarWindow

logger = logging.getLogger('rat.ui.omnibar.search_controller')


def _resolve_hook(name: str, fallback: Any) -> Any:
    mod = sys.modules.get("rat.ui.omnibar")
    if mod and hasattr(mod, name):
        return getattr(mod, name)
    return fallback


class SearchController:
    """Controller managing search queries, card injections, list navigation, and file actions."""

    def __init__(self, window: OmnibarWindow) -> None:
        self.window = window

    def on_search_text_changed(self) -> None:
        w = self.window
        q = w.search_input.text().strip()

        # If user cleared input in another section, auto-return to Home (Chatbot)
        if not q and w.current_section_idx != 0:
            w.switch_section(0)
            return

        # If user is in Files view, trigger search debounce
        if w.current_section_idx == 1:
            w.search_timer.start()



    def select_file_filter(self, idx: int) -> None:
        w = self.window
        w.active_file_filter_idx = idx
        for i, btn in enumerate(w.file_filter_buttons):
            btn.setProperty("active", "true" if i == idx else "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        w._execute_search()



    def execute_search(self) -> None:
        w = self.window
        w.search_timer.stop()
        query = w.search_input.text().strip()
        w.current_query = query
        _, _, exts = FILTER_CATEGORIES[w.active_file_filter_idx]

        w._request_counter += 1
        req_id = w._request_counter
        w.footer_status.setText("Đang tìm...")
        w.search_requested.emit(req_id, query, list(exts) if exts else [])

    @pyqtSlot(int, dict)


    def on_search_completed(self, request_id: int, response: Dict[str, Any]) -> None:
        w = self.window
        if w._chat_file_request is not None and request_id == w._chat_file_request["request_id"]:
            request = w._chat_file_request
            w._chat_file_request = None
            if request["generation"] != w._chat_generation:
                return
            files = response.get("results", [])[:4]
            latency = response.get("latency_ms", (time.time() - request["started_at"]) * 1000.0)
            answer = (
                f"{len(files)} tệp khớp ‘{request['target']}’."
                if files else "Chưa thấy tệp khớp trong chỉ mục. Thử một phần tên hoặc từ khóa khác nhé."
            )
            if response.get("error"):
                answer = "Tìm kiếm chưa hoàn tất. Thử lại sau một chút nhé."
            w.feedback.queries[w.compact_file_list] = request["target"]
            w._deliver_assistant_reply(answer, latency_ms=latency, strategy="Search", inline_files=files)
            w.footer_status.setText(f"{len(files)} tệp")
            return
        try:
            if request_id != w._request_counter:
                return

            results: List[SearchResultItem] = response.get("results", [])
            latency = response.get("latency_ms", 0)
            results = sort_search_results(results, "score")

            q_text = getattr(w, "current_query", "") or w.search_input.text().strip()
            q_lower = q_text.lower()

            # 1. Quick Math Card (safe_calculate)
            calc_expr = None
            if re.search(r"\d", q_text) and any(op in q_text for op in ["+", "*", "/", "%", "^", " - "]):
                calc_expr = re.sub(r"^(?:tính|tinh|calc|calculate|\=)\s*", "", q_text, flags=re.I).strip()
            elif re.match(r"^(?:tính|tinh|calc)\s+([0-9\.\+\-\*\/\(\)\s\^]+)$", q_text, flags=re.I):
                m = re.match(r"^(?:tính|tinh|calc)\s+([0-9\.\+\-\*\/\(\)\s\^]+)$", q_text, flags=re.I)
                if m:
                    calc_expr = m.group(1).strip()

            if calc_expr:
                try:
                    try:
                        from rat.engine.meta_reasoner import safe_calculate
                    except ImportError:
                        from reasoning_strategies import safe_calculate
                    res_str = safe_calculate(calc_expr)
                    if res_str and "Lỗi" not in res_str and res_str != "None":
                        calc_item = SearchResultItem(
                            file_path=f"rat://calc_copy/{res_str}",
                            file_name=f"Kết quả tính toán: {res_str}",
                            file_ext=".calc",
                            file_size=0,
                            modified_at=time.time(),
                            score=2000.0,
                            explanation="Tính toán tức thì • Nhấn ↵ để sao chép kết quả",
                            snippet=f"Biểu thức: {calc_expr} = {res_str}\nNhấn Enter để sao chép số này vào clipboard.",
                        )
                        results.insert(0, calc_item)
                except Exception as e:
                    logger.debug(f"Calc card error: {e}")

            # 2. Campus Room Guide Card (TDTU Tân Phong)
            room_match = re.search(r"\b([A-Fa-fCcFf]\d{3}|TRET-NTD-2)\b", q_text)
            if room_match:
                try:
                    rm = room_match.group(1).upper()
                    loc = resolve_room_location(rm)
                    room_item = SearchResultItem(
                        file_path=f"rat://room_location/{rm}",
                        file_name=f"Vị trí phòng {rm}: {loc}",
                        file_ext=".map",
                        file_size=0,
                        modified_at=time.time(),
                        score=1800.0,
                        explanation="Cơ sở Tân Phong, ĐH Tôn Đức Thắng • Nhấn ↵ để xem lịch học",
                        snippet=f"Phòng {rm} tọa lạc tại {loc}.\nNhấn Enter để chuyển sang xem lịch học chi tiết.",
                    )
                    results.insert(0, room_item)
                except Exception as e:
                    logger.debug(f"Room card error: {e}")

            # 3. Live Agenda / Today's Schedule Card
            agenda_kw = ["hôm nay", "hom nay", "chiều nay", "chieu nay", "sáng nay", "sang nay", "tối nay", "toi nay", "tiết sau", "lịch học", "lich hoc", "tkb"]
            if any(k in q_lower for k in agenda_kw):
                try:
                    agenda = w.compositor.get_today_agenda(w.current_member)
                    c_count = len(agenda)
                    if c_count > 0:
                        first_c = agenda[0]
                        first_s = first_c["session"]
                        deg = "[ThS]" if first_s.degree_level == "master" else "[ĐH]"
                        ag_snip = f"Hôm nay ({w.current_member.name}) có {c_count} ca học: [{first_c['start_time']} - {first_c['end_time']}] {deg} {first_s.course_name} (Phòng {first_s.room}) • {first_c['countdown']}"
                    else:
                        ag_snip = f"Hôm nay ({w.current_member.name}) không có ca học nào trên TKB. Bạn đang hoàn toàn rảnh!"

                    ag_item = SearchResultItem(
                        file_path="rat://goto_schedule",
                        file_name=f"Lịch học hôm nay: {c_count} ca học ({w.current_member.name})",
                        file_ext=".app",
                        file_size=0,
                        modified_at=time.time(),
                        score=1500.0,
                        explanation="Nhấn ↵ để xem chi tiết trên thẻ Thời khóa biểu",
                        snippet=ag_snip,
                    )
                    results.insert(0, ag_item)
                except Exception as e:
                    logger.debug(f"Agenda card error: {e}")

            # 4. Club Golden Slot Card
            if any(k in q_lower for k in ["ai rảnh", "ai ranh", "clb", "golden slot", "họp nhóm"]):
                club_item = SearchResultItem(
                    file_path="rat://goto_club",
                    file_name="Khung Giờ Vàng CLB & Ai Đang Rảnh",
                    file_ext=".app",
                    file_size=0,
                    modified_at=time.time(),
                    score=1400.0,
                    explanation="Nhấn ↵ để mở ma trận giờ rảnh CLB",
                    snippet="Tìm khung giờ vàng họp nhóm và kiểm tra ai rảnh theo từng ca học.",
                )
                results.insert(0, club_item)

            # 5. Dynamic RL Reasoning Meta-Controller Card (CoT, PAL, ESCALATE)
            from rat.engine.meta_reasoner import meta_reasoner
            if meta_reasoner.is_reasoning_query(q_text):
                try:
                    r_res = meta_reasoner.solve(q_text)
                    reason_item = SearchResultItem(
                        file_path=f"rat://reasoning_copy/{r_res.answer}",
                        file_name=f"Suy luận AI: {r_res.badge}",
                        file_ext=".ai",
                        file_size=0,
                        modified_at=time.time(),
                        score=2500.0,
                        explanation=f"Định tuyến bởi Meta-Controller RL ({r_res.strategy}) • Nhấn ↵ để sao chép đáp án",
                        snippet=f"{r_res.answer}\n\n[Chiến lược: {r_res.strategy} | Độ tự tin: {int(r_res.confidence*100)}% | Tiêu thụ: {r_res.tokens} tokens]",
                    )
                    results.insert(0, reason_item)

                    # Provide structured reasoning steps to preview panel
                    from rat.engine.reasoning_trace import ReasoningTrace
                    r_trace = ReasoningTrace(raw_query=q_text)
                    for s_idx, s_txt in enumerate(r_res.steps):
                        r_trace.add_step(
                            phase="reason",
                            thought=s_txt,
                            action=f"execute_{r_res.strategy.lower()}",
                            observation="Hoàn tất suy luận qua Meta-Controller",
                            evaluation=f"Độ tự tin: {int(r_res.confidence*100)}%",
                            latency_ms=round(r_res.latency_ms / max(len(r_res.steps), 1), 2),
                        )
                    r_trace.finalize(confidence=r_res.confidence, is_sufficient=True)
                    response["reasoning_trace"] = r_trace
                except Exception as e:
                    logger.debug(f"Reasoning card error: {e}")

            w.result_list.clear()

            for item in results:
                list_item = QListWidgetItem(w.result_list)
                list_item.setData(Qt.ItemDataRole.UserRole, item)
                w.result_list.addItem(list_item)

            trace = response.get("reasoning_trace")
            w.feedback.refresh(
                w.result_list, response.get("query", w.current_query),
                response.get("parsed_context", {}),
                response.get("latency_ms"),
            )
            plan = response.get("plan")
            w.preview_panel.set_reasoning_trace(trace, plan)

            cot_badge = "  •  Có lời giải từng bước" if trace and trace.steps else ""
            if results:
                w.result_list.setCurrentRow(0)
                w.footer_status.setText(f"Tìm thấy {len(results)} tệp{cot_badge}")
            else:
                w.preview_panel.set_item(None)
                query_hint = f" cho '{q_text}'" if q_text else ""
                w.footer_status.setText(f"Chưa thấy tệp nào{query_hint}. Thử từ khóa khác nhé.{cot_badge}")
        except Exception as e:
            logger.error(f"Error handling search completed in Omnibar: {e}", exc_info=True)



    def on_result_selected(self, row: int) -> None:
        w = self.window
        try:
            item = w.result_list.item(row)
            if item:
                search_item: SearchResultItem = item.data(Qt.ItemDataRole.UserRole)
                q_text = getattr(w, "current_query", "") or w.search_input.text().strip()
                w.preview_panel.set_item(search_item, query=q_text)
                if getattr(search_item, "file_ext", "") == ".ai":
                    w.preview_panel.set_active_tab(1)
            else:
                w.preview_panel.set_item(None)
        except Exception as e:
            logger.error(f"Error handling result selected: {e}", exc_info=True)



    def on_item_double_clicked(self, item: QListWidgetItem) -> None:
        w = self.window
        w._activate_current_item()



    def is_list_focused(self) -> bool:
        w = self.window
        return w.result_list.hasFocus() or w.recent_list.hasFocus() or w.compact_file_list.hasFocus()



    def active_file_list(self) -> QListWidget:
        w = self.window
        if w.current_section_idx == 0 and w.compact_file_list.isVisible() and w.compact_file_list.count():
            return w.compact_file_list
        return w.result_list if w.current_section_idx == 1 else w.recent_list



    def navigate_active_list(self, delta: int) -> None:
        w = self.window
        active_list = w._active_file_list()
        count = active_list.count()
        if count == 0:
            return
        curr = active_list.currentRow()
        new_row = max(0, min(count - 1, curr + delta))
        active_list.setCurrentRow(new_row)



    def activate_current_item(self) -> None:
        w = self.window
        active_list = w._active_file_list()
        curr_row = active_list.currentRow()
        item = active_list.item(curr_row)
        if not item:
            return

        search_item: SearchResultItem = item.data(Qt.ItemDataRole.UserRole)
        if not search_item:
            return

        fp = getattr(search_item, "file_path", "")

        # Virtual URIs routing
        if fp.startswith("rat://calc_copy/"):
            val = fp.split("rat://calc_copy/", 1)[1]
            QApplication.clipboard().setText(val)
            w.show_toast(f"Đã sao chép kết quả: {val}")
            return
        elif fp.startswith("rat://reasoning_copy/"):
            val = fp.split("rat://reasoning_copy/", 1)[1]
            QApplication.clipboard().setText(val)
            w.show_toast("Đã sao chép câu trả lời suy luận vào clipboard.")
            return
        elif fp == "rat://goto_schedule" or fp.startswith("rat://room_location"):
            w.switch_section(2)
            return
        elif fp == "rat://goto_club":
            w.switch_section(3)
            return

        # Real file path
        opener = _resolve_hook("open_file_default", open_file_default)
        w.feedback.perform("open", search_item, opener)



    def reveal_current_in_finder(self) -> None:
        w = self.window
        active_list = w._active_file_list()
        curr_row = active_list.currentRow()
        item = active_list.item(curr_row)
        if item:
            search_item: SearchResultItem = item.data(Qt.ItemDataRole.UserRole)
            if search_item:
                revealer = _resolve_hook("reveal_in_finder", reveal_in_finder)
                w.feedback.perform("reveal", search_item, revealer)

    def open_current_in_terminal(self) -> None:
        w = self.window
        active_list = w._active_file_list()
        curr_row = active_list.currentRow()
        item = active_list.item(curr_row)
        if item:
            search_item: SearchResultItem = item.data(Qt.ItemDataRole.UserRole)
            if search_item:
                term = _resolve_hook("open_in_terminal", open_in_terminal)
                w.feedback.perform("terminal", search_item, term)
                w.show_toast(f"💻 Đã mở Terminal: {search_item.file_name}")

    def preview_quick_look(self) -> None:
        w = self.window
        active_list = w._active_file_list()
        curr_row = active_list.currentRow()
        item = active_list.item(curr_row)
        if item:
            search_item: SearchResultItem = item.data(Qt.ItemDataRole.UserRole)
            if search_item:
                previewer = _resolve_hook("trigger_quicklook", trigger_quicklook)
                previewer(search_item.file_path)



    def copy_current_path(self) -> None:
        w = self.window
        active_list = w._active_file_list()
        curr_row = active_list.currentRow()
        item = active_list.item(curr_row)
        if item:
            search_item: SearchResultItem = item.data(Qt.ItemDataRole.UserRole)
            cb = QApplication.clipboard()
            if cb and search_item:
                cb.setText(search_item.file_path)
                w.show_toast(f"✓ Đã sao chép đường dẫn: {search_item.file_name}")



    def copy_current_content(self) -> None:
        w = self.window
        active_list = w._active_file_list()
        curr_row = active_list.currentRow()
        item = active_list.item(curr_row)
        if item:
            search_item: SearchResultItem = item.data(Qt.ItemDataRole.UserRole)
            if search_item:
                from rat.crawler.extractors import extract_document_content
                text = extract_document_content(search_item.file_path)
                cb = QApplication.clipboard()
                if cb:
                    cb.setText(text)
                    w.show_toast(f"✓ Đã chép nội dung ({len(text)} ký tự)")



    def quick_search(self, query: str) -> None:
        w = self.window
        if w.current_section_idx == 0:
            w._submit_chat_prompt(query)
        else:
            w.search_input.setText(query)
            w.switch_section(1)
            w._execute_search()

    def _quick_fill(self, prefix: str) -> None:
        w.switch_section(1)
        w.search_input.setFocus()
        w.search_input.setText(prefix)
        w.search_input.setCursorPosition(len(prefix))

    def _select_sched_day(self, code: str, idx: int) -> None:
        w.selected_day_code = code
        for i, btn in enumerate(w.day_buttons):
            btn.setProperty("active", "true" if i == idx else "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        w._refresh_schedule_view()

    def _on_sched_member_changed(self, idx: int) -> None:
        if 0 <= idx < len(w.members):
            w.current_member = w.members[idx]
            w.profile_badge.setText(w.current_member.name)
            w._refresh_schedule_view()
            w._refresh_home_agenda()

