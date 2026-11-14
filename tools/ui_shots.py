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
import concurrent.futures
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("PYTEST_CURRENT_TEST", "ui_shots")
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


def _all_targets() -> list[dict]:
    from tools.ui_shot_fixtures import LIVE_STATES, LIVE_WIDTHS

    targets = []
    for dark in (False, True):
        mode = "dark" if dark else "light"
        for scene in DESK_SCENES:
            targets.append({
                "qml": "PDFDesk.qml", "kind": "preview", "scene": scene,
                "dark": dark, "name": f"desk-{scene}-{mode}.png", "size": [700, 640]
            })
        targets.append({
            "qml": "ReasoningLab.qml", "kind": "lab", "dark": dark,
            "name": f"lab-{mode}.png", "size": [980, 780]
        })
        targets.append({
            "qml": "MiniDesk.qml", "kind": "mini", "dark": dark,
            "name": f"mini-{mode}.png", "size": [580, 480]
        })
        targets.append({
            "qml": "Gallery.qml", "kind": "preview", "scene": "idle", "dark": dark,
            "name": f"gallery-{mode}.png", "size": [700, 640]
        })
        for state in LIVE_STATES:
            for width in LIVE_WIDTHS:
                targets.append({
                    "qml": "PDFDesk.qml", "kind": "live", "state": state,
                    "dark": dark, "name": f"live-{state}-{width}-{mode}.png", "size": [width, 640]
                })
    return targets


def render_one(tree: Path, out: Path, spec: dict) -> int:
    from rat.ui.icon_provider import RatIconProvider
    from tools.ui_shot_fixtures import MiniStub, build_live_controller

    messages: list[str] = []
    qInstallMessageHandler(lambda mode, context, message: messages.append(message))
    app = QGuiApplication.instance() or QGuiApplication([sys.argv[0]])
    app.setFont(QFont("Helvetica Neue", 13))
    mascot = QUrl.fromLocalFile(str(tree / "rat/assets/rat_mascot_cutout.png"))

    qml = spec["qml"]
    dark = spec["dark"]
    name = spec["name"]
    size = tuple(spec["size"])
    kind = spec["kind"]

    ctrl = None
    tmp_dir = None
    try:
        if kind == "preview":
            props = {
                "darkMode": dark,
                "reduceMotion": True,
                "previewScene": spec["scene"],
                "mascotSource": mascot,
            }
        elif kind == "lab":
            props = {"controller": LabStub(), "darkMode": dark}
        elif kind == "mini":
            props = {
                "liveController": MiniStub(),
                "darkMode": dark,
                "reduceMotion": True,
                "mascotSource": mascot,
            }
        elif kind == "live":
            tmp_dir = tempfile.TemporaryDirectory()
            db_path = Path(tmp_dir.name) / f"{name}.db"
            ctrl = build_live_controller(spec["state"], db_path)
            props = {
                "liveController": ctrl,
                "darkMode": dark,
                "reduceMotion": True,
                "mascotSource": mascot,
            }

        view = QQuickView()
        view.setResizeMode(QQuickView.ResizeMode.SizeRootObjectToView)
        provider = RatIconProvider()
        view.engine().addImageProvider("icon", provider)
        view.setInitialProperties(props)
        del messages[:]
        view.setSource(QUrl.fromLocalFile(str(tree / "rat/ui/quick" / qml)))
        if view.status() != QQuickView.Status.Ready:
            err = "; ".join(e.toString() for e in view.errors())
            print(f"ERROR {name}: {err}", file=sys.stderr)
            return 1
        view.resize(*size)
        view.show()
        for _ in range(4):
            app.processEvents()

        for m in messages:
            if ".qml" in m:
                print(f"WARN: {name}: {_plain(m)}")
        del messages[:]

        saved = view.grabWindow().save(str(out / name))
        print(("saved " if saved else "FAILED ") + name)
        return 0 if saved else 1
    finally:
        if ctrl is not None:
            ctrl.close()
        if tmp_dir is not None:
            tmp_dir.cleanup()


def shoot(tree: Path, out: Path) -> int:
    out.mkdir(parents=True, exist_ok=True)
    targets = _all_targets()
    warnings = set()
    failures = 0

    def run_target(t: dict):
        spec_str = json.dumps(t)
        cmd = [
            sys.executable,
            str(Path(__file__).resolve()),
            "_render_one",
            spec_str,
            str(out),
            "--tree",
            str(tree),
        ]
        return subprocess.run(cmd, capture_output=True, text=True)

    max_workers = min(os.cpu_count() or 4, 4)
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
        results = list(ex.map(run_target, targets))

    for res in results:
        if res.returncode != 0:
            failures += 1
            if res.stderr:
                print(res.stderr.strip(), file=sys.stderr)
        for line in res.stdout.splitlines():
            if line.startswith("WARN: "):
                warnings.add(line[6:].strip())
            elif line.startswith("saved ") or line.startswith("FAILED "):
                print(line)

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
    old, new = ({line for line in (folder / WARNINGS).read_text(encoding="utf-8").splitlines() if line.strip()}
                if (folder / WARNINGS).exists() else set() for folder in (before, after))
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

    render_args = commands.add_parser("_render_one")
    render_args.add_argument("spec", type=str)
    render_args.add_argument("out", type=Path)
    render_args.add_argument("--tree", type=Path, default=REPO)

    compare_args = commands.add_parser("compare")
    compare_args.add_argument("before", type=Path)
    compare_args.add_argument("after", type=Path)
    compare_args.add_argument("--pairs", type=Path)

    args = parser.parse_args()
    sys.path.insert(0, str(REPO))

    if args.command == "shoot":
        return shoot(args.tree.resolve(), args.out.resolve())
    elif args.command == "_render_one":
        spec = json.loads(args.spec)
        return render_one(args.tree.resolve(), args.out.resolve(), spec)
    return compare(args.before.resolve(), args.after.resolve(),
                   (args.pairs or args.after / "pairs").resolve())


if __name__ == "__main__":
    raise SystemExit(main())
