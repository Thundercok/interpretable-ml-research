"""
rat.ui.omnibar.chat_controller — Intent routing, prompt processing, and LLM reasoning orchestration.
"""

from __future__ import annotations

import logging
import re
import sys
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QApplication, QDialog

from rat.engine.reranker import SearchResultItem
from rat.timetable.model import resolve_room_location
from rat.ui.chat_session import (
    CHAT_SYSTEM_PROMPT,
    extract_arithmetic_request,
    normalize_chat_request,
)
from .companion import ResetConfirmationDialog
from .workers import StreamReasoningWorker

if TYPE_CHECKING:
    from .window import OmnibarWindow

logger = logging.getLogger('rat.ui.omnibar.chat_controller')


def _resolve_hook(name: str, fallback: Any) -> Any:
    mod = sys.modules.get('rat.ui.omnibar')
    if mod and hasattr(mod, name):
        return getattr(mod, name)
    return fallback


from dataclasses import dataclass

@dataclass
class ChatPresentationState:
    phase: str = "idle"  # "idle" | "waiting" | "writing" | "searching" | "completed" | "interrupted" | "error"
    request_id: int = 0
    generation: int = 0
    query: str = ""
    retry_available: bool = False
    status_text: str = ""
    is_search: bool = False


class ChatController:
    """Controller orchestrating chat prompt submissions, intent routing, and streaming inference."""

    def __init__(self, window: OmnibarWindow) -> None:
        self.window = window

    def on_complete_status_timeout(self) -> None:
        w = self.window
        if hasattr(w, "_presentation_state") and w._presentation_state.phase == "completed":
            w._presentation_state.phase = "idle"
            w._sync_compact_surface()

    def prefill_chat(self, text: str) -> None:
        w = self.window
        w.chat_composer_input.setText(text)
        w.chat_composer_input.setFocus()
        w.chat_composer_input.setCursorPosition(len(text))

    def complete_chat_turn(self, answer: str) -> None:
        w = self.window
        if w._pending_chat_query is not None:
            w._conversation.add_turn(w._pending_chat_query, answer)
            w._pending_chat_query = None

    def deliver_assistant_reply(
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
        w = self.window
        """
        Deliver assistant reply:
        - In compact mode: Chuột speaks via speech bubble.
        - In expanded mode: reply goes cleanly to chat stream, NO floating bubble outside!
        """
        incomplete = strategy in {"AI chưa sẵn sàng", "Phản hồi bị ngắt"}
        if incomplete:
            w._pending_chat_query = None
            if strategy == "Phản hồi bị ngắt":
                w._presentation_state.phase = "interrupted"
                w._presentation_state.status_text = "Phản hồi bị ngắt"
            else:
                w._presentation_state.phase = "error"
                w._presentation_state.status_text = "Chưa nhận được phản hồi"
            w._presentation_state.retry_available = True
        else:
            w._complete_chat_turn(answer)
            w._presentation_state.phase = "completed"
            w._presentation_state.status_text = "Đã tìm xong" if strategy == "Search" else "Đã trả lời"
            w._presentation_state.retry_available = False
            w._complete_status_timer.start(2000)

        if hasattr(w, "reply_reader"):
            curr_q = getattr(w, "_presentation_state", None) and w._presentation_state.query or ""
            req_id = getattr(w, "_presentation_state", None) and w._presentation_state.request_id or 0
            gen = getattr(w, "_chat_generation", 0)
            turn_id = f"gen_{gen}_req_{req_id}"
            if hasattr(w.reply_reader, "start_live_turn"):
                w.reply_reader.start_live_turn(turn_id, curr_q)
            if hasattr(w.reply_reader, "finalize_live_turn"):
                w.reply_reader.finalize_live_turn(answer, is_error=incomplete, query=curr_q)
            if hasattr(w, "_conversation") and hasattr(w.reply_reader, "sync_history"):
                w.reply_reader.sync_history(w._conversation._turns)

        w._set_compact_files(inline_files)
        context_str = {
            "Search": "Tìm tệp", "Math": "Tính nhanh", "Timetable": "Lịch học",
            "CampusMap": "Phòng học", "Club-Matrix": "Giờ rảnh", "Direct": "Trả lời",
            "AI chưa sẵn sàng": "Chưa kết nối", "Phản hồi bị ngắt": "Bị ngắt",
        }.get(strategy, "Trả lời")
        w._present_compact_reply(
            answer, context_str, has_details=bool(custom_widget), file_summary=bool(inline_files)
        )
        w.speech_bubble.context_pill.setToolTip(f"{strategy} · {latency_ms:.0f} ms")

        if hasattr(w, "chat_stream"):
            try:
                turn = step_number or (len(w._conversation._turns) if hasattr(w, "_conversation") else 1)
                w.chat_stream.add_assistant_message(
                    answer=answer,
                    reasoning_steps=reasoning_steps,
                    latency_ms=latency_ms,
                    strategy=strategy,
                    confidence=confidence,
                    custom_widget=custom_widget,
                    inline_files=inline_files,
                    step_number=turn,
                    step_suggestions=step_suggestions,
                )
            except Exception as e:
                logger.debug(f"Chat stream add error: {e}")
        w._sync_compact_surface()
        if hasattr(w, "conversation_ribbon"):
            w.conversation_ribbon.set_session_info(
                w._conversation.get_tag_label(),
                len(w._conversation._turns)
            )
        if hasattr(w, "reply_reader") and hasattr(w.reply_reader, "set_session_tag"):
            w.reply_reader.set_session_tag(w._conversation.get_tag_label())

        if getattr(w, "rat_stage", None):
            w.rat_stage.set_state("idle")
        if getattr(w, "set_mascot_state", None) and getattr(w, "_mascot_state", "idle") != "angry":
            w.set_mascot_state("idle")

    def request_reset_chat(self) -> None:
        w = self.window
        if w._dialog_active:
            return
        has_history = hasattr(w, "_conversation") and len(w._conversation._turns) > 0
        # Pending and failed turns are visible before they enter completed history.
        has_messages = hasattr(w, "chat_stream") and not w.chat_stream.is_empty()
        has_pending = w._pending_chat_query is not None or w._chat_file_request is not None
        draft_text = w.chat_composer_input.text().strip() if hasattr(w, "chat_composer_input") else ""
        has_draft = bool(draft_text and draft_text.lower() not in ("/clear", "clear", "/reset", "reset"))
        if has_history or has_messages or has_pending or has_draft:
            dialog = ResetConfirmationDialog(w)
            dialog.move(
                w.x() + (w.width() - dialog.width()) // 2,
                w.y() + (w.height() - dialog.height()) // 2,
            )
            # The modal becomes active; do not hide its parent on ActivationChange.
            w._dialog_active = True
            try:
                result = dialog.exec()
            finally:
                w._dialog_active = False
                dialog.deleteLater()
            if result != QDialog.DialogCode.Accepted:
                return
        w._reset_chat()

    def reset_chat(self) -> None:
        w = self.window
        w._chat_generation += 1
        w._conversation.clear()
        if hasattr(w, "conversation_ribbon"):
            w.conversation_ribbon.set_session_info(w._conversation.get_tag_label(), 0)
        if hasattr(w, "reply_reader"):
            if hasattr(w.reply_reader, "clear_all"):
                w.reply_reader.clear_all()
            else:
                w.reply_reader.set_reply("")
                if hasattr(w.reply_reader, "set_turns"):
                    w.reply_reader.set_turns([])
            if hasattr(w.reply_reader, "set_session_tag"):
                w.reply_reader.set_session_tag(w._conversation.get_tag_label())
        w._pending_chat_query = None
        w._chat_file_request = None
        w._request_counter += 1
        w._complete_status_timer.stop()
        w._presentation_state = ChatPresentationState(generation=w._chat_generation)
        w._current_stream_handle = None
        if w._current_reasoner is not None:
            w._current_reasoner.requestInterruption()
            w._current_reasoner = None
        if hasattr(w, "chat_stream"):
            w.chat_stream.clear_chat()
        w._set_compact_files(None)
        w.set_expanded(False)
        w.set_mascot_idle()
        if hasattr(w, "speech_bubble"):
            w.speech_bubble.reset_welcome("Xong. Phiên mới, hỏi tiếp đi.")
        w.search_input.clear()
        if hasattr(w, "chat_composer_input"):
            w.chat_composer_input.clear()
        w.switch_section(0)
        w.show_toast(f"Đã làm mới phiên #{w._conversation.session_id}")
        w._sync_compact_surface()

    def submit_chat_prompt(self, query: str) -> None:
        w = self.window
        q = query.strip()
        if not q:
            return
        if q.lower() in ("/clear", "clear", "/reset", "reset"):
            w.request_reset_chat()
            return
        busy = (
            getattr(w, "_presentation_state", None) is not None
            and w._presentation_state.phase in ("waiting", "writing", "searching")
        ) or w._pending_chat_query is not None
        if busy:
            # Keep a second draft intact rather than interleaving unfinished turns.
            w.footer_status.setText("Đang trả lời câu trước. Câu đang gõ vẫn được giữ.")
            return

        w._complete_status_timer.stop()
        w.set_reply_reader_open(False)
        w._chat_request_counter += 1
        req_id = w._chat_request_counter
        w._presentation_state = ChatPresentationState(
            phase="waiting",
            request_id=req_id,
            generation=w._chat_generation,
            query=q,
            retry_available=False,
            status_text="Đang chờ phản hồi…",
        )
        w._pending_chat_query = q
        w._set_compact_files(None)
        turn_id = f"gen_{w._chat_generation}_req_{req_id}"
        if hasattr(w, "reply_reader"):
            if hasattr(w.reply_reader, "start_live_turn"):
                w.reply_reader.start_live_turn(turn_id, q)
            else:
                w.reply_reader.set_reply("")

        if w.current_section_idx != 0:
            w.switch_section(0)

        # Quick mode answers directly via speech bubble without forcing expansion
        w.set_mascot_state("thinking", "Chuột · Đang chờ phản hồi…")
        w.speech_bubble.set_reply("Đang chờ phản hồi…", "Đang chờ", copy_text="")

        w.chat_stream.add_user_message(q)
        w.search_input.clear()
        if hasattr(w, "chat_composer_input"):
            w.chat_composer_input.clear()
        w._sync_compact_surface()
        if hasattr(w, "return_keycap"):
            w.return_keycap.setProperty("active", "false")
            w.return_keycap.style().unpolish(w.return_keycap)
            w.return_keycap.style().polish(w.return_keycap)
        request = normalize_chat_request(q)
        q_lower = request.lower()
        intent = q_lower.strip(" .!?,…")
        original_intent = q.lower().strip(" .!?,…")
        t0 = time.time()

        # Shortcuts must match a whole intent, never swallow an attached request.
        greetings = ["chào", "chao", "hello", "hi", "alo", "helo", "hey", "chuột ơi", "chuot oi", "chào chuột", "chao chuot", "rat ơi", "rat oi", "chào rat", "chao rat"]
        if original_intent in greetings or intent in greetings:
            lat = (time.time() - t0) * 1000.0
            w._deliver_assistant_reply(
                answer="Nghe đây. Cần gì?",
                latency_ms=lat,
                strategy="Direct",
            )
            return

        # 0b. Help & Capabilities Guide
        help_kw = ["help", "giúp", "bạn làm được gì", "ban lam duoc gi", "làm được gì", "lam duoc gi", "bạn có thể làm gì", "hướng dẫn", "huong dan", "tính năng", "tinh nang", "dùng sao", "dung sao"]
        if intent in help_kw:
            lat = (time.time() - t0) * 1000.0
            ans_text = "Hỏi đáp, cùng nghĩ ý tưởng, hoặc tra lịch, phòng học, tìm tệp và tính nhanh. Cứ gõ việc bạn cần."
            w._deliver_assistant_reply(
                answer=ans_text,
                latency_ms=lat,
                strategy="Direct",
            )
            return

        # 0c. Gratitude & Goodbyes
        if intent in ["cảm ơn", "cam on", "thanks", "thank you", "tks", "cảm ơn chuột", "cảm ơn rat"]:
            lat = (time.time() - t0) * 1000.0
            w._deliver_assistant_reply(
                answer="Ừ, được rồi. Cần gì cứ gọi.",
                latency_ms=lat,
                strategy="Direct",
            )
            return

        if intent in ["tạm biệt", "tam biet", "bye", "bai", "bye chuột", "bye rat"]:
            lat = (time.time() - t0) * 1000.0
            w._deliver_assistant_reply(
                answer="Ừ. Tôi ở đây khi cần.",
                latency_ms=lat,
                strategy="Direct",
            )
            return

        # Only standalone mascot teasing gets a cheeky canned response.
        # Frustration or an insult attached to a real task still goes to the model.
        if original_intent in ["chuột ngốc", "chuột ngu", "rat ngốc", "rat ngu"]:
            ans_text = "Ừ, chê xong rồi thì đưa việc đây. Mình thử lại."
            w._deliver_assistant_reply(
                answer=ans_text,
                latency_ms=1.0,
                strategy="Direct",
            )
            return

        # 2. Campus Room Locator
        room_match = re.search(r"\b([A-Fa-fCcFf]\d{3}|TRET-NTD-2)\b", q)
        if room_match and (any(w in q_lower for w in ["phòng", "phong", "ở đâu", "o dau", "tòa", "toa", "vị trí", "vi tri"]) or len(q.split()) <= 2):
            try:
                rm = room_match.group(1).upper()
                lat = (time.time() - t0) * 1000.0
                if rm == "C302":
                    ans_text = "Tầng 3, Tòa C. Rẽ trái từ thang máy."
                else:
                    loc = resolve_room_location(rm)
                    ans_text = f"Phòng {rm}: {loc}."
                w._deliver_assistant_reply(
                    answer=ans_text,
                    latency_ms=lat,
                    strategy="CampusMap",
                    confidence=1.0,
                )
                w.footer_status.setText(f"Phòng {rm} ({lat:.0f}ms)")
                return
            except Exception as e:
                logger.debug(f"Chat room error: {e}")

        schedule_intent = bool(re.search(
            r"\b(?:lịch học|lich hoc|tkb|thời khóa biểu|thoi khoa bieu|ca học|ca hoc|"
            r"lịch (?:hôm nay|ngày mai|thứ)|lich (?:hom nay|ngay mai|thu)|"
            r"(?:có )?học (?:gì|môn nào|ở đâu)|hoc (?:gi|mon nao|o dau))\b", q_lower
        )) or intent in ["lịch", "lich", "hôm nay", "hom nay", "ngày mai", "ngay mai"]
        if schedule_intent and not any(k in q_lower for k in ["tìm", "tệp", "file", "tài liệu", "tai lieu"]):
            try:
                day_name_map = {
                    "T2": "Thứ Hai", "T3": "Thứ Ba", "T4": "Thứ Tư",
                    "T5": "Thứ Năm", "T6": "Thứ Sáu", "T7": "Thứ Bảy", "CN": "Chủ Nhật"
                }
                target_day = None
                day_label = ""
                now = datetime.now()

                if "hôm nay" in q_lower or "hom nay" in q_lower:
                    target_day = "TODAY"
                    day_label = "hôm nay"
                elif "ngày mai" in q_lower or "ngay mai" in q_lower or "mai " in q_lower or q_lower == "mai":
                    target_day = "TOMORROW"
                    day_label = "ngày mai"
                else:
                    for d_code, kws in [
                        ("T2", ["thứ 2", "thứ hai", "thu 2", "thu hai", "t2"]),
                        ("T3", ["thứ 3", "thứ ba", "thu 3", "thu ba", "t3"]),
                        ("T4", ["thứ 4", "thứ tư", "thu 4", "thu tu", "t4"]),
                        ("T5", ["thứ 5", "thứ năm", "thu 5", "thu nam", "t5"]),
                        ("T6", ["thứ 6", "thứ sáu", "thu 6", "thu sau", "t6"]),
                        ("T7", ["thứ 7", "thứ bảy", "thu 7", "thu bay", "t7"]),
                        ("CN", ["chủ nhật", "chu nhat", "cn"]),
                    ]:
                        if any(kw in q_lower for kw in kws):
                            target_day = d_code
                            day_label = day_name_map[d_code]
                            break

                if target_day or any(k in q_lower for k in ["lịch học", "tkb", "thời khóa biểu"]):
                    if target_day == "TODAY" or target_day is None:
                        agenda = w.compositor.get_today_agenda(w.current_member)
                        sessions = [item["session"] for item in agenda]
                        day_label = "hôm nay"
                    elif target_day == "TOMORROW":
                        tomorrow_idx = (now.weekday() + 1) % 7
                        code_map = {0: "T2", 1: "T3", 2: "T4", 3: "T5", 4: "T6", 5: "T7", 6: "CN"}
                        t_code = code_map[tomorrow_idx]
                        sessions = w.current_member.schedule.get(t_code, [])
                        day_label = f"ngày mai ({day_name_map[t_code]})"
                    else:
                        sessions = w.current_member.schedule.get(target_day, [])

                    lat = (time.time() - t0) * 1000.0
                    if sessions:
                        from rat.timetable.model import TDTU_PERIODS
                        sched_items = []
                        for s in sessions:
                            p_start_str = TDTU_PERIODS.get(s.start_period, ("00:00", "00:00", "", ""))[0]
                            p_end_str = TDTU_PERIODS.get(s.end_period, ("23:59", "23:59", "", ""))[1]
                            sched_items.append(f"{s.course_name} ({p_start_str}-{p_end_str}, {s.room})")
                        ans_text = f"Lịch {day_label} ({len(sessions)} môn): " + "; ".join(sched_items)
                    else:
                        ans_text = f"Lịch học {day_label}: Không có ca học nào."

                    w._deliver_assistant_reply(
                        answer=ans_text,
                        latency_ms=lat,
                        strategy="Timetable",
                        confidence=1.0,
                    )
                    w.footer_status.setText(f"Lịch học {day_label} ({lat:.0f}ms)")
                    return
            except Exception as e:
                logger.debug(f"Chat schedule error: {e}")

        # 4. Instant Math Calculation
        calc_expr = extract_arithmetic_request(q)

        if calc_expr:
            try:
                try:
                    from rat.engine.meta_reasoner import safe_calculate
                except ImportError:
                    from reasoning_strategies import safe_calculate
                res_str = safe_calculate(calc_expr)
                if res_str and res_str.lower().startswith(("error:", "lỗi")):
                    answer = (
                        "Không thể chia cho 0. Thử đổi số chia nhé."
                        if "division by zero" in res_str or "modulo by zero" in res_str
                        else "Chưa tính được biểu thức này. Kiểm tra số và dấu phép tính nhé."
                    )
                    w._deliver_assistant_reply(answer, strategy="Math", confidence=0.0)
                    return
                if res_str and not res_str.lower().startswith(("error:", "lỗi")) and res_str != "None":
                    lat = (time.time() - t0) * 1000.0
                    ans_text = f"{calc_expr} = {res_str}"
                    w._deliver_assistant_reply(
                        answer=ans_text,
                        latency_ms=lat,
                        strategy="Math",
                        confidence=1.0,
                    )
                    w.footer_status.setText(f"Tính toán ({lat:.0f}ms)")
                    return
            except Exception as e:
                logger.debug(f"Chat calc error: {e}")

        # 5. Club Golden Slots & Group Availability
        if intent == "clb" or any(k in q_lower for k in ["ai rảnh", "ai ranh", "golden slot", "giờ rảnh", "gio ranh", "lịch họp nhóm"]):
            try:
                slots = w.compositor.find_golden_windows(min_ratio=0.8)
                lat = (time.time() - t0) * 1000.0
                if slots:
                    s = slots[0]
                    free_names = ", ".join(s.free_members[:4])
                    if len(s.free_members) > 4:
                        free_names += f" và {len(s.free_members) - 4} bạn khác"
                    ans_text = (
                        f"Khung giờ họp tốt nhất: {s.day_name} ({s.time_range}), "
                        f"{s.free_count}/{s.total_count} người rảnh ({int(s.ratio * 100)}%). "
                        f"Thành viên: {free_names}."
                    )
                else:
                    ans_text = "Không có khung giờ nào đạt ≥80% thành viên rảnh trong tuần."
                w._deliver_assistant_reply(
                    answer=ans_text,
                    latency_ms=lat,
                    strategy="Club-Matrix",
                    confidence=1.0,
                )
                w.footer_status.setText(f"Giờ rảnh CLB ({lat:.0f}ms)")
                return
            except Exception as e:
                logger.debug(f"Chat club error: {e}")

        # 6. Explicit File / Document Search
        is_explicit_file = (
            bool(re.fullmatch(r"[^\s]+\.(?:py|pdf|docx|xlsx|pptx|txt|md|json|csv|sh|png|jpg|jpeg|zip|tar|gz)", request, flags=re.I))
            or bool(re.match(r"^(?:(?:tìm|kiếm)\s+(?:kiếm\s+)?(?:file|tệp|tài liệu|tập tin)|(?:search|find)\s+(?:file|document))\b", request, flags=re.I))
            or q_lower.startswith("file:")
        )

        clean_q = re.sub(r"^(?:(?:tìm|kiếm)\s+(?:kiếm\s+)?(?:file|tệp|tài liệu|tập tin)|(?:search|find)\s+(?:file|document)|file:)\s*", "", request, flags=re.I).strip()
        search_target = clean_q if len(clean_q) >= 2 else request

        if is_explicit_file:
            if not clean_q:
                w._deliver_assistant_reply("Bạn muốn tìm tệp nào? Gõ một phần tên hoặc nội dung.")
                return
            w.set_mascot_state("searching")
            w.search_timer.stop()
            w._request_counter += 1
            w._chat_file_request = {
                "request_id": w._request_counter, "generation": w._chat_generation,
                "target": search_target, "started_at": t0,
            }
            w.speech_bubble.set_reply("Đang tìm tệp…", "Tìm tệp", copy_text="")
            w._sync_compact_surface()
            w.search_requested.emit(w._request_counter, search_target, [])
            return

        # 6b. Dynamic Meta-Reasoner Engine (PAL / CoT / Regulations / Quantitative Reasoning)
        from rat.engine.meta_reasoner import meta_reasoner
        req_lower = request.lower()
        if meta_reasoner.is_reasoning_query(request) and (meta_reasoner._is_quantitative_query(req_lower) or meta_reasoner._is_policy_query(req_lower)):
            try:
                t0_reason = time.time()
                r_res = meta_reasoner.solve(request, history=w._conversation.messages())
                lat = (time.time() - t0_reason) * 1000.0

                suggestions = []
                if r_res.strategy == "PAL":
                    suggestions = ["Tính thêm kỳ tới: ", "Điều kiện học bổng Giỏi", "Kỳ sau cần bao nhiêu điểm?"]
                elif r_res.strategy in ("CoT", "LADDER", "ESCALATED"):
                    suggestions = ["Điều kiện cụ thể", "Có ngoại lệ không?", "Thủ tục nộp đơn"]
                else:
                    suggestions = ["Giải thích rõ hơn", "Cho ví dụ cụ thể", "Tóm tắt trong 3 ý"]

                turn_num = len(w._conversation._turns) + 1
                w._deliver_assistant_reply(
                    answer=r_res.answer,
                    latency_ms=r_res.latency_ms or lat,
                    strategy=r_res.strategy,
                    confidence=r_res.confidence,
                    reasoning_steps=r_res.steps,
                    step_number=turn_num,
                    step_suggestions=suggestions,
                )
                w.footer_status.setText(f"Chuột · {r_res.strategy} ({lat:.0f}ms)")
                return
            except Exception as e:
                logger.debug(f"Meta-reasoner chat solve error: {e}")

        # 7. Conversational Reasoning / Q&A / On-Device AI Streaming
        try:
            handle = w.chat_stream.create_streaming_message(
                strategy="AI cục bộ",
                badge="Đang kết nối",
                context="Trả lời",
                query=q,
            )
            handle["generation"] = w._chat_generation
            handle["request_id"] = req_id
            w._current_stream_handle = handle
            w.footer_status.setText("Đang chờ phản hồi…")
            worker = _resolve_hook("StreamReasoningWorker", StreamReasoningWorker)(q, history=w._conversation.messages())
            w._current_reasoner = worker
            w._reasoning_workers.add(worker)
            worker.token_received.connect(
                lambda tok, h=handle: w._on_reasoning_token(h, tok)
            )
            worker.reasoning_finished.connect(
                lambda ans, stp, lat, strat, bdg, h=handle: w._on_reasoning_finished(h, ans, stp, lat, strat, bdg)
            )
            worker.finished.connect(lambda w=worker: w._on_chat_worker_finished(w))
            worker.finished.connect(worker.deleteLater)
            worker.start()
            return
        except Exception as e:
            logger.debug(f"Chat reasoning fallback error: {e}")

        # 8. Implicit File Search as Fallback
        try:
            search_res = w.engine.search(search_target, limit=3)
            files = search_res.get("results", [])
            lat = search_res.get("latency_ms", (time.time() - t0) * 1000.0)
            if files:
                ans_text = f"Gợi ý {len(files)} tệp liên quan đến '{search_target}'."
                w._deliver_assistant_reply(
                    answer=ans_text,
                    latency_ms=lat,
                    strategy="Search",
                    confidence=0.85,
                    inline_files=files,
                )
                w.footer_status.setText(f"{len(files)} tệp ({lat:.0f}ms)")
                return
        except Exception:
            pass

        # 9. Fallback Guide
        lat = (time.time() - t0) * 1000.0
        fallback_ans = "Chưa gửi được câu hỏi tới AI. Thử lại hoặc kiểm tra mô hình trong Cài đặt nhé."
        w._deliver_assistant_reply(
            answer=fallback_ans,
            latency_ms=lat,
            strategy="Direct",
            confidence=0.80,
        )
        w.footer_status.setText("Sẵn sàng")

    def on_reasoning_token(self, handle: Dict[str, Any], token: str) -> None:
        w = self.window
        if handle.get("generation", w._chat_generation) != w._chat_generation:
            return
        if handle.get("request_id", 0) != w._presentation_state.request_id:
            return
        if w._presentation_state.phase == "waiting":
            w._presentation_state.phase = "writing"
            w._presentation_state.status_text = "Đang viết…"
            w._sync_compact_surface()
        w.chat_stream.append_stream_token(handle, token)
        w._present_compact_reply(handle["full_text"], "Đang gõ")
        if getattr(w, "rat_stage", None):
            w.rat_stage.set_state("thinking", "Chuột · Đang viết...")
        w.set_mascot_state("thinking")

    def on_reasoning_finished(
            self,
            handle: Dict[str, Any],
            answer: str,
            steps: List[str],
            latency_ms: float,
            strategy: str,
            badge: str,
        ) -> None:
        w = self.window
        if handle.get("generation", w._chat_generation) != w._chat_generation:
            return
        if handle.get("request_id", 0) != w._presentation_state.request_id:
            return
        if handle.get("finalized"):
            return

        # Non-streaming fallback and final corrections must replace partial tokens.
        handle["full_text"] = answer if answer.strip() else handle.get("full_text", "")
        incomplete = strategy in {"AI chưa sẵn sàng", "Phản hồi bị ngắt"}
        if incomplete:
            w._pending_chat_query = None  # Don't treat a connection error as an answer.
            if strategy == "Phản hồi bị ngắt":
                w._presentation_state.phase = "interrupted"
                w._presentation_state.status_text = "Phản hồi bị ngắt"
            else:
                w._presentation_state.phase = "error"
                w._presentation_state.status_text = "Chưa nhận được phản hồi"
            w._presentation_state.retry_available = True
        else:
            w._complete_chat_turn(handle["full_text"])
            w._presentation_state.phase = "completed"
            w._presentation_state.status_text = "Đã trả lời"
            w._presentation_state.retry_available = False
            w._complete_status_timer.start(2000)

        if hasattr(w, "reply_reader"):
            curr_q = getattr(w, "_presentation_state", None) and w._presentation_state.query or handle.get("query", "")
            if hasattr(w.reply_reader, "finalize_live_turn"):
                w.reply_reader.finalize_live_turn(handle["full_text"], is_error=incomplete, query=curr_q)
            if hasattr(w, "_conversation") and hasattr(w.reply_reader, "sync_history"):
                w.reply_reader.sync_history(w._conversation._turns)

        w._current_reasoner = None
        if "badge_lbl" in handle:
            handle["badge_lbl"].setText(f"· {badge}")
        turn_num = len(w._conversation._turns) if hasattr(w, "_conversation") else 1
        w.chat_stream.finalize_stream(
            handle, reasoning_steps=steps, latency_ms=latency_ms,
            strategy=strategy, step_number=turn_num
        )
        status = {"AI chưa sẵn sàng": "Chưa kết nối", "Phản hồi bị ngắt": "Bị ngắt"}.get(strategy, "Xong")
        w._present_compact_reply(handle["full_text"], status)
        w.footer_status.setText(f"Chuột · {strategy} ({latency_ms:.0f}ms)")
        if getattr(w, "rat_stage", None):
            w.rat_stage.set_state("idle")
        w.set_mascot_state("idle")
        w._sync_compact_surface()

    def on_chat_worker_finished(self, worker: StreamReasoningWorker) -> None:
        w = self.window
        w._reasoning_workers.discard(worker)
        if w._current_reasoner is worker:
            w._current_reasoner = None
            w._pending_chat_query = None
            if hasattr(w, "_current_stream_handle") and w._current_stream_handle and not w._current_stream_handle.get("finalized"):
                w._on_reasoning_finished(
                    w._current_stream_handle,
                    "Chưa nhận được phản hồi từ AI. Kiểm tra mô hình trong Cài đặt rồi thử lại nhé.",
                    [], 0.0, "AI chưa sẵn sàng", "Chưa kết nối"
                )
            else:
                w._deliver_assistant_reply(
                    "Chưa nhận được phản hồi từ AI. Kiểm tra mô hình trong Cài đặt rồi thử lại nhé.",
                    strategy="AI chưa sẵn sàng", confidence=0.0,
                )

    def retry_chat(self) -> None:
        w = self.window
        if not w._presentation_state.retry_available or not w._presentation_state.query:
            return
        if w._presentation_state.phase in ("waiting", "writing", "searching"):
            return
        q = w._presentation_state.query
        w._presentation_state.retry_available = False
        w._complete_status_timer.stop()
        w._chat_request_counter += 1
        req_id = w._chat_request_counter
        w._presentation_state = ChatPresentationState(
            phase="waiting",
            request_id=req_id,
            generation=w._chat_generation,
            query=q,
            retry_available=False,
            status_text="Đang chờ phản hồi…",
        )
        w._pending_chat_query = q
        turn_id = f"gen_{w._chat_generation}_req_{req_id}"
        if hasattr(w, "reply_reader"):
            if hasattr(w.reply_reader, "start_live_turn"):
                w.reply_reader.start_live_turn(turn_id, q)
            else:
                w.reply_reader.set_reply("")
        # Keep composer draft intact! Do NOT clear chat_composer_input!
        w.set_mascot_state("thinking", "Chuột · Đang chờ phản hồi…")
        w.speech_bubble.set_reply("Đang chờ phản hồi…", "Đang chờ", copy_text="")
        w._sync_compact_surface()

        handle = w.chat_stream.create_streaming_message(
            strategy="AI cục bộ",
            badge="Đang kết nối",
            context="Trả lời lại",
            query=q,
        )
        handle["generation"] = w._chat_generation
        handle["request_id"] = req_id
        w._current_stream_handle = handle
        w.footer_status.setText("Đang chờ phản hồi…")

        worker = _resolve_hook("StreamReasoningWorker", StreamReasoningWorker)(q, history=w._conversation.messages())
        w._current_reasoner = worker
        w._reasoning_workers.add(worker)
        worker.token_received.connect(
            lambda tok, h=handle: w._on_reasoning_token(h, tok)
        )
        worker.reasoning_finished.connect(
            lambda ans, stp, lat, strat, bdg, h=handle: w._on_reasoning_finished(h, ans, stp, lat, strat, bdg)
        )
        worker.finished.connect(lambda w=worker: w._on_chat_worker_finished(w))
        worker.finished.connect(worker.deleteLater)
        worker.start()