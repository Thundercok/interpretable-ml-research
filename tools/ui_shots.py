"""Screenshot the Qt Quick desks headless, and compare two sets of screenshots pixel by pixel.

A refactor must leave every image identical; a design change must come with the pairs it produced.

    python tools/ui_shots.py shoot OUT_DIR [--tree DIR]
    python tools/ui_shots.py compare BEFORE_DIR AFTER_DIR [--pairs DIR]

`--tree` renders another checkout's `rat/ui/quick` (for a "before" set); it defaults to this one.
`shoot` also records every QML warning (without line numbers) in OUT_DIR/warnings.txt.
`compare` exits 1 when any image differs or is missing, or a QML warning is new, and writes
before|after pairs for the images that differ.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")
os.environ["QT_QUICK_CONTROLS_STYLE"] = "Basic"

from PyQt6.QtCore import (
    QObject,
    QUrl,
    pyqtProperty,
    pyqtSignal,
    pyqtSlot,
    qInstallMessageHandler,
)
from PyQt6.QtGui import QColor, QFont, QGuiApplication, QImage, QPainter
from PyQt6.QtQuick import QQuickView

REPO = Path(__file__).resolve().parents[1]
DESK_SCENES = ("idle", "unread", "folded", "startup", "receiving", "working", "result")
WARNINGS = "warnings.txt"

_LAB_STEP = {
    "strategy": "cot", "label": "Suy luận từng bước", "answer": "42", "verdict": "correct",
    "confidence": "0.9312", "tokens": 218, "seconds": 3.4,
    "text": "Mỗi hộp có 6 quả, 7 hộp là 6 × 7 = 42 quả.", "code": "print(6*7)",
    "toolOutput": "42", "toolOk": True, "decision": "Độ tin cậy vượt ngưỡng nên dừng ở đây.",
}
_LAB_RESULT = {
    "question": "7 hộp, mỗi hộp 6 quả. Có bao nhiêu quả?", "mode": "policy", "reason": "", "status": "done",
    "finalLabel": "Suy luận từng bước", "finalAnswer": "42", "finalVerdict": "correct", "expected": "42",
    "path": ["Trả lời thẳng", "Suy luận từng bước"], "tokens": 431, "promptTokens": 512, "calls": 2,
    "seconds": 6.1,
    "steps": [dict(_LAB_STEP, strategy="direct", label="Trả lời thẳng", answer="48", verdict="wrong",
                   confidence="0.5120"), _LAB_STEP],
}


class LabStub(QObject):
    """Stands in for ReasoningLabController with one finished run, so no model is loaded."""
    changed = pyqtSignal()

    @pyqtProperty("QVariantMap", notify=changed)
    def snapshot(self):
        return {"busy": False, "status": "", "error": "", "question": _LAB_RESULT["question"],
                "mode": "policy", "result": _LAB_RESULT, "logPath": "/tmp/reasoning.log",
                "examples": [{"text": "Ví dụ một", "expected": "1", "label": "Ví dụ 1"}]}

    @pyqtSlot(int)
    def useExample(self, index): pass

    @pyqtSlot(str)
    def editQuestion(self, text): pass

    @pyqtSlot(str)
    def setMode(self, mode): pass

    @pyqtSlot()
    def submit(self): pass

    @pyqtSlot()
    def cancel(self): pass


def shoot(tree: Path, out: Path) -> int:
    from rat.ui.icon_provider import RatIconProvider

    out.mkdir(parents=True, exist_ok=True)
    messages: list = []
    qInstallMessageHandler(lambda mode, context, message: messages.append(message))
    warnings = set()
    app = QGuiApplication.instance() or QGuiApplication([sys.argv[0]])
    app.setFont(QFont("Helvetica Neue", 13))
    mascot = QUrl.fromLocalFile(str(REPO / "rat/assets/rat_mascot_cutout.png"))
    lab = LabStub()
    providers = []  # the engine does not own a Python image provider
    failures = 0

    def one(qml: str, props: dict, name: str, size: tuple) -> None:
        nonlocal failures
        view = QQuickView()
        view.setResizeMode(QQuickView.ResizeMode.SizeRootObjectToView)
        providers.append(RatIconProvider())
        view.engine().addImageProvider("icon", providers[-1])
        view.setInitialProperties(props)
        del messages[:]
        view.setSource(QUrl.fromLocalFile(str(tree / "rat/ui/quick" / qml)))
        if view.status() != QQuickView.Status.Ready:
            print(f"ERROR {name}: " + "; ".join(error.toString() for error in view.errors()))
            failures += 1
            return
        view.resize(*size)
        view.show()
        for _ in range(40):
            app.processEvents()
        warnings.update(f"{name}: {_plain(message)}" for message in messages if ".qml" in message)
        saved = view.grabWindow().save(str(out / name))
        print(("saved " if saved else "FAILED ") + name, flush=True)
        failures += 0 if saved else 1
        view.setSource(QUrl())
        view.close()
        view.deleteLater()
        app.processEvents()

    for dark in (False, True):
        mode = "dark" if dark else "light"
        for scene in DESK_SCENES:
            one("PDFDesk.qml", {"darkMode": dark, "reduceMotion": True, "previewScene": scene,
                                "mascotSource": mascot}, f"desk-{scene}-{mode}.png", (700, 640))
        one("ReasoningLab.qml", {"controller": lab, "darkMode": dark}, f"lab-{mode}.png", (980, 780))
    (out / WARNINGS).write_text("\n".join(sorted(warnings)) + "\n", encoding="utf-8")
    print(f"wrote {len(warnings)} QML warnings to {WARNINGS}")
    return 1 if failures else 0


def _plain(message: str) -> str:
    """Keep the file name and the text of a QML message; drop the folder and line numbers."""
    message = re.sub(r"file://\S*/([A-Za-z]+\.qml)", r"\1", message)
    return re.sub(r"(\.qml):\d+(:\d+)?", r"\1", message).strip()


def compare(before: Path, after: Path, pairs: Path) -> int:
    QGuiApplication.instance() or QGuiApplication([sys.argv[0]])
    names = sorted({p.name for p in before.glob("*.png")} | {p.name for p in after.glob("*.png")})
    changed = 0
    for name in names:
        if not (before / name).exists() or not (after / name).exists():
            print(f"MISSING {name}")
            changed += 1
            continue
        a, b = QImage(str(before / name)), QImage(str(after / name))
        if a == b:
            print(f"same    {name}")
            continue
        changed += 1
        pairs.mkdir(parents=True, exist_ok=True)
        sheet = QImage(a.width() + b.width() + 12, max(a.height(), b.height()), QImage.Format.Format_RGB32)
        sheet.fill(QColor("#ff00ff"))
        painter = QPainter(sheet)
        painter.drawImage(0, 0, a)
        painter.drawImage(a.width() + 12, 0, b)
        painter.end()
        sheet.save(str(pairs / name))
        print(f"DIFFERS {name} -> {pairs / name}")
    print(f"{changed} of {len(names)} images differ")
    old, new = (set((folder / WARNINGS).read_text(encoding="utf-8").splitlines()) if (folder / WARNINGS).exists()
                else set() for folder in (before, after))
    for line in sorted(new - old):
        print(f"NEW WARNING {line}")
    print(f"{len(new - old)} new QML warnings")
    return 1 if changed or new - old else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    shoot_args = commands.add_parser("shoot")
    shoot_args.add_argument("out", type=Path)
    shoot_args.add_argument("--tree", type=Path, default=REPO)
    compare_args = commands.add_parser("compare")
    compare_args.add_argument("before", type=Path)
    compare_args.add_argument("after", type=Path)
    compare_args.add_argument("--pairs", type=Path)
    args = parser.parse_args()
    sys.path.insert(0, str(REPO))
    if args.command == "shoot":
        return shoot(args.tree.resolve(), args.out.resolve())
    return compare(args.before.resolve(), args.after.resolve(),
                   (args.pairs or args.after / "pairs").resolve())


if __name__ == "__main__":
    raise SystemExit(main())
