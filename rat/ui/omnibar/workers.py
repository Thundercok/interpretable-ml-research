"""
rat.ui.omnibar.workers — Background workers for Omnibar search and AI inference.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Dict, List, Optional

from PyQt6.QtCore import QObject, QThread, pyqtSignal, pyqtSlot
from PyQt6.QtWidgets import QApplication

from rat.engine.hybrid_search import SearchEngine
from rat.ui.chat_session import CHAT_SYSTEM_PROMPT, build_chat_prompt

logger = logging.getLogger("rat.ui.omnibar.workers")


class SearchWorker(QObject):
    """Long-lived background search worker for Omnibar."""

    search_completed = pyqtSignal(int, dict)

    def __init__(self, engine: SearchEngine) -> None:
        super().__init__()
        self.engine = engine
        self._latest_id = 0
        self._lock = threading.Lock()
        try:
            self.engine.embedder.embed_query("warmup")
            self.engine.vector_cache.preload()
        except Exception as e:
            logger.warning(f"SearchWorker warmup error: {e}")

    @pyqtSlot(int, str, list)
    def do_search(self, request_id: int, query: str, extensions: list) -> None:
        with self._lock:
            if request_id < self._latest_id:
                return
            self._latest_id = request_id

        try:
            response = self.engine.search(
                query,
                limit=30,
                use_hyde=False,
                use_vector=True,
            )
            with self._lock:
                if request_id < self._latest_id:
                    return

            if extensions:
                filtered = [r for r in response.get("results", []) if r.file_ext.lower() in extensions]
                response["results"] = filtered

            self.search_completed.emit(request_id, response)
        except Exception as e:
            logger.error(f"SearchWorker error: {e}")
            self.search_completed.emit(
                request_id,
                {"query": query, "results": [], "latency_ms": 0, "parsed_context": {}, "error": True},
            )


class StreamReasoningWorker(QThread):
    """Background worker for streaming real-time LLM inference without freezing UI."""

    token_received = pyqtSignal(str)
    reasoning_finished = pyqtSignal(str, list, float, str, str)  # (ans, steps, lat_ms, strategy, badge)

    def __init__(self, query: str, history: Optional[List[Dict[str, str]]] = None) -> None:
        super().__init__(QApplication.instance())
        self.query = query
        self.history = [dict(message) for message in (history or [])]

    def run(self) -> None:
        t0 = time.time()
        from rat.engine.slm import slm_engine

        if self.isInterruptionRequested():
            return
        # Try live token streaming if Ollama is available
        if slm_engine.is_service_running():
            full_tokens = []
            completed = False
            try:
                for token, done in slm_engine.generate_stream(
                    prompt=build_chat_prompt(self.query, self.history),
                    system_prompt=CHAT_SYSTEM_PROMPT,
                ):
                    if self.isInterruptionRequested():
                        return
                    if token:
                        full_tokens.append(token)
                        self.token_received.emit(token)
                    if done:
                        completed = True
                        break

                if full_tokens and "".join(full_tokens).strip():
                    lat = (time.time() - t0) * 1000.0
                    ans_text = "".join(full_tokens).strip()
                    if not completed:
                        self.reasoning_finished.emit(
                            ans_text + "\n\n[Phản hồi bị ngắt. Kiểm tra kết nối AI rồi thử lại.]",
                            [],
                            lat,
                            "Phản hồi bị ngắt",
                            slm_engine.model,
                        )
                        return
                    steps = [
                        f"Yêu cầu hiện tại: '{self.query}'",
                        f"Ngữ cảnh: {len(self.history) // 2} lượt trao đổi trước.",
                        f"Mô hình cục bộ: {slm_engine.model}.",
                    ]
                    self.reasoning_finished.emit(ans_text, steps, lat, "AI cục bộ", slm_engine.model)
                    return
            except Exception as e:
                logger.debug(f"Chat streaming error: {e}")

        if not self.isInterruptionRequested():
            # A canned/demo controller cannot answer a real, contextual conversation.
            self.reasoning_finished.emit(
                "AI cục bộ chưa trả lời được. Kiểm tra Ollama và mô hình trong Cài đặt, rồi thử lại. "
                "Phép tính, tìm tệp và lịch học vẫn dùng được.",
                [],
                (time.time() - t0) * 1000.0,
                "AI chưa sẵn sàng",
                "Chưa kết nối",
            )
