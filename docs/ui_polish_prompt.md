# Task: polish pass on the RAT Qt Quick desk

You are working in the `selective-delegation-agent` repository. Run every command from the
repository root. Do the six steps below in order, exactly as written. Every edit has been tried on a
copy of this code already, so if something does not match what this document says, stop and report
it instead of improvising.

## What this is

RAT is a macOS desktop assistant. Its main window is written in QML and lives in `rat/ui/quick/`.
The three windows are `PDFDesk.qml` (main desk), `MiniDesk.qml` (quick translate) and
`ReasoningLab.qml`. Small shared pieces such as `QuietButton.qml` sit beside them.

Two facts about this folder that you must rely on:

- Every window's root item has `id: desk`. Colours are properties on that root (`desk.ink`,
  `desk.accent`, and so on). The shared files such as `QuietButton.qml` read `desk.*` even though
  they are separate files. That works in QML and is how this project is built. Keep it that way.
- UI text is Vietnamese. Keep every Vietnamese string exactly as given here, accents included.

## Rules

1. Only create or change files inside `rat/ui/quick/`. Touch nothing else in the repository.
2. Do not change, delete, skip or weaken any test.
3. Do not run any git command other than `git status` and `git diff`. No commit, branch, stash,
   checkout, restore, reset or clean. Other work is in progress in this checkout.
4. Do not rename or remove any `objectName`, `id`, property or function that already exists.
5. Do not create these files, a test forbids them: `LookSurface.qml`, `SpeechBubble.qml`,
   `CompanionStatus.qml`, `PaperDesk.qml`. Do not leave `.bak` files anywhere in the repository.
6. Do not add new dependencies, new Python files, or new QML files other than `DeskTheme.qml`.
7. Do not "improve" anything this document does not ask for. No refactors, no reformatting.
8. If a check fails and the recovery instructions do not fix it, stop and write the report.

## Setup (do this before step 1)

Create a scratch folder outside the repository and the smoke script inside it.

```bash
mkdir -p /tmp/rat_ui_polish
```

Save the following as `/tmp/rat_ui_polish/smoke.py`, exactly:

```python
"""Load the three desk QML files headless and write every QML error/warning, without line numbers."""
import os
import re
import sys
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")
os.environ["QT_QUICK_CONTROLS_STYLE"] = "Basic"

from PyQt6.QtCore import QUrl, qInstallMessageHandler  # noqa: E402
from PyQt6.QtGui import QGuiApplication  # noqa: E402
from PyQt6.QtQuick import QQuickView  # noqa: E402

DESKS = ("PDFDesk.qml", "MiniDesk.qml", "ReasoningLab.qml")
messages = []
qInstallMessageHandler(lambda mode, context, message: messages.append(message))


def normalise(text: str) -> str:
    text = re.sub(r"file://\S*/([A-Za-z]+\.qml)", r"\1", text)
    return re.sub(r"(\.qml):\d+(:\d+)?", r"\1", text).strip()


def main() -> int:
    project = Path(sys.argv[1]).resolve()
    output = Path(sys.argv[2]).resolve()
    app = QGuiApplication([sys.argv[0]])
    lines = set()
    for name in DESKS:
        for dark in (False, True):
            del messages[:]
            view = QQuickView()
            view.setInitialProperties({"darkMode": dark, "reduceMotion": True})
            view.setSource(QUrl.fromLocalFile(str(project / "rat/ui/quick" / name)))
            view.resize(700, 640)
            view.show()
            end = time.time() + 0.4
            while time.time() < end:
                app.processEvents()
            mode = "dark" if dark else "light"
            lines.add(f"{name} [{mode}] status={view.status().name}")
            for error in view.errors():
                lines.add(f"{name} [{mode}] ERROR {normalise(error.toString())}")
            for message in messages:
                if ".qml" in message:
                    lines.add(f"{name} [{mode}] WARN {normalise(message)}")
            view.setSource(QUrl())
            view.close()
            view.deleteLater()
            app.processEvents()
    output.write_text("\n".join(sorted(lines)) + "\n", encoding="utf-8")
    print(f"wrote {len(lines)} lines to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Record the starting state. The test command takes about 6 to 7 minutes and prints nothing until it
finishes; give it a 15 minute timeout and do not interrupt it.

```bash
.venv/bin/python /tmp/rat_ui_polish/smoke.py . /tmp/rat_ui_polish/smoke_before.txt
```

```bash
QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software .venv/bin/python -m pytest tests/test_quick_*.py tests/test_paper_and_mascot_interactions.py tests/test_reading_session.py tests/test_app_router.py tests/test_architecture_anti_overengineering.py -q -p no:cacheprovider 2>&1 | grep -E '^(FAILED|ERROR) ' | sed 's/ - .*//' | sort -u > /tmp/rat_ui_polish/fail_before.txt; wc -l /tmp/rat_ui_polish/fail_before.txt
```

Notes on the starting state, so they do not surprise you:

- `smoke_before.txt` already contains warnings, and `ReasoningLab.qml` reports `status=Error`
  because it needs a controller. That is normal. You only care that the file does not gain lines.
- `fail_before.txt` is not empty. When this document was written it held 34 lines: 34 of the 81
  tests in this group already fail before you start. You are not asked to fix them, except the
  four `test_quick_press_depth.py` ones, which step 6 fixes.
- `tests/test_quick_escape.py::test_escape_on_a_folded_page_stays_folded` passes on some runs and
  fails on others, with no code change. If it is the only new failure, ignore it.

## The check (run it after every step)

"Run the check" means all of this, in order:

1. Smoke:

   ```bash
   .venv/bin/python /tmp/rat_ui_polish/smoke.py . /tmp/rat_ui_polish/smoke_after.txt && diff /tmp/rat_ui_polish/smoke_before.txt /tmp/rat_ui_polish/smoke_after.txt && echo SMOKE_SAME
   ```

   It must print `SMOKE_SAME`. Any line starting with `>` in the diff is a new QML error you caused.

2. Tests:

   ```bash
   QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software .venv/bin/python -m pytest tests/test_quick_*.py tests/test_paper_and_mascot_interactions.py tests/test_reading_session.py tests/test_app_router.py tests/test_architecture_anti_overengineering.py -q -p no:cacheprovider 2>&1 | grep -E '^(FAILED|ERROR) ' | sed 's/ - .*//' | sort -u > /tmp/rat_ui_polish/fail_after.txt; comm -13 /tmp/rat_ui_polish/fail_before.txt /tmp/rat_ui_polish/fail_after.txt
   ```

   The `comm` output lists tests that fail now but did not fail at the start. It must be empty.

3. If the `comm` output is not empty, run the test command once more. These are timing-sensitive
   UI tests and one can fail by chance. Only a test that fails twice in a row counts.

If the check passes, save a backup of the folder and go to the next step (replace `N` with the
step number):

```bash
rm -rf /tmp/rat_ui_polish/after_step_N && cp -R rat/ui/quick /tmp/rat_ui_polish/after_step_N
```

Before step 1, save the untouched folder the same way as `/tmp/rat_ui_polish/after_step_0`.

If the check still fails after one attempt at fixing your edit, undo the step by copying the
previous backup back, then stop and write the report:

```bash
rm -rf rat/ui/quick && cp -R /tmp/rat_ui_polish/after_step_PREVIOUS rat/ui/quick
```

## Step 1: one shared palette

Why: `PDFDesk.qml`, `MiniDesk.qml` and `ReasoningLab.qml` each declare the same colour list by
hand, and the copies have drifted apart. After this step all three read one file.

Create `rat/ui/quick/DeskTheme.qml` with exactly this content:

```qml
import QtQuick

// One place for the paper/sage palette. Each desk creates one and re-exports the names on its
// root (`desk.ink`, `desk.accent`, ...), so the other files in this folder keep reading `desk.*`.
QtObject {
    property bool darkMode: false

    readonly property color ink: darkMode ? "#eef0e9" : "#2c302a"
    readonly property color muted: darkMode ? "#b7bdaf" : "#62695e"
    readonly property color paperColor: darkMode ? "#272d25" : "#fdfdf9"
    readonly property color inputColor: darkMode ? "#2b3227" : "#fdfefb"
    readonly property color backingColor: darkMode ? "#3a4332" : "#e8ece1"
    readonly property color edge: darkMode ? "#424d39" : "#e0e5d8"
    readonly property color accent: darkMode ? "#c0d2a7" : "#4f6740"
    readonly property color accentText: darkMode ? "#24301b" : "#fafcf5"
    readonly property color warningInk: darkMode ? "#e4bb89" : "#916329"
    readonly property color pdfInk: darkMode ? "#dbaa9f" : "#a15e50"
    readonly property color selectedSurface: darkMode ? "#2d3727" : "#edf4e8"
    readonly property color selectedEdge: darkMode ? "#46593d" : "#b5ceaa"
    readonly property color utilitySurface: darkMode ? "#242820" : "#f0f4ea"
    readonly property color hoverSurface: darkMode ? "#2a3125" : "#f1f6ed"
}
```

Then run these two commands. The first points each colour at the theme. The second adds the line
that creates the theme, just above the first colour.

```bash
perl -pi -e 's/^(\s*readonly property color (ink|muted|paperColor|inputColor|backingColor|edge|accent|accentText|warningInk|pdfInk|selectedSurface|selectedEdge|utilitySurface|hoverSurface)): darkMode \? "#[0-9a-fA-F]+" : "#[0-9a-fA-F]+"\s*$/$1: deskTheme.$2\n/' rat/ui/quick/PDFDesk.qml rat/ui/quick/MiniDesk.qml rat/ui/quick/ReasoningLab.qml
```

```bash
perl -pi -e 's/^(\s*)(readonly property color ink: deskTheme\.ink)$/$1property DeskTheme deskTheme: DeskTheme { darkMode: desk.darkMode }\n$1$2/' rat/ui/quick/PDFDesk.qml rat/ui/quick/MiniDesk.qml rat/ui/quick/ReasoningLab.qml
```

In `rat/ui/quick/ReasoningLab.qml` the name `backingColor` is the window behind the cards, not the
sheet behind the paper, so its dark value must stay darker than the cards. Replace this line (it
appears once):

```qml
    readonly property color backingColor: deskTheme.backingColor
```

with:

```qml
    // Here this is the window behind the cards, so in the dark it must stay darker than paperColor.
    readonly property color backingColor: darkMode ? "#1f241c" : deskTheme.backingColor
```

Verify:

```bash
grep -c 'deskTheme\.' rat/ui/quick/PDFDesk.qml rat/ui/quick/MiniDesk.qml rat/ui/quick/ReasoningLab.qml; grep -c 'property DeskTheme deskTheme' rat/ui/quick/PDFDesk.qml rat/ui/quick/MiniDesk.qml rat/ui/quick/ReasoningLab.qml
```

Expected: `PDFDesk.qml:14`, `MiniDesk.qml:13`, `ReasoningLab.qml:13`, then `1` for each of the
three files. `ReasoningLab.qml` keeps its own `wrongInk` line unchanged; that is correct.
The mini desk's colours shift very slightly to match the main desk. That is intended.

Run the check.

## Step 2: larger small text

Why: most labels are 9 to 11 pixels, which is hard to read with Vietnamese accents. This raises
9 and 10 to 11, and 11 to 12, in one pass. Sizes 12 and above stay as they are.

Run this command exactly once. Running it twice would raise the sizes twice.

```bash
perl -pi -e 's/(pixelSize:\s*)(9|10|11)\b/$1 . ($2 == 11 ? 12 : 11)/ge' rat/ui/quick/*.qml
```

Verify:

```bash
grep -ohE 'pixelSize: *[0-9]+' rat/ui/quick/*.qml | sort | uniq -c | sort -k3 -n | head -3
```

Expected first lines: `54 pixelSize: 11`, `136 pixelSize: 12`, `22 pixelSize: 13`. There must be
no `pixelSize: 9` or `pixelSize: 10` left.

Run the check.

## Step 3: tooltips in the desk's colours

Why: tooltips currently use Qt's default look, a white box with a black border, which clashes
with the desk. All tooltips in a window share one popup, so styling it once covers all of them.

In `rat/ui/quick/PDFDesk.qml`, find this line (it appears once):

```qml
    function applyScene(scene) {
```

Insert this block directly above it:

```qml
    // Every tooltip in this window is one shared popup; dress it in the desk palette once.
    function styleToolTips() {
        var tip = desk.ToolTip.toolTip
        tip.palette.toolTipBase = Qt.binding(function() { return desk.ink })
        tip.palette.toolTipText = Qt.binding(function() { return desk.paperColor })
        tip.font.pixelSize = 12
        tip.padding = 7
        if (tip.background) {
            tip.background.radius = 7
            tip.background.border.width = 0
        }
    }
```

In the same file, replace this line (it appears once):

```qml
    Component.onCompleted: { if (liveMode) syncLive(); else applyScene(previewScene); readyForMotion = true }
```

with:

```qml
    Component.onCompleted: { styleToolTips(); if (liveMode) syncLive(); else applyScene(previewScene); readyForMotion = true }
```

In `rat/ui/quick/MiniDesk.qml`, find this (it appears once, at four spaces of indentation):

```qml
    Component.onCompleted: {
        liveSnapshot = liveController.snapshot
```

Replace it with:

```qml
    // Every tooltip in this window is one shared popup; dress it in the desk palette once.
    function styleToolTips() {
        var tip = desk.ToolTip.toolTip
        tip.palette.toolTipBase = Qt.binding(function() { return desk.ink })
        tip.palette.toolTipText = Qt.binding(function() { return desk.paperColor })
        tip.font.pixelSize = 12
        tip.padding = 7
        if (tip.background) {
            tip.background.radius = 7
            tip.background.border.width = 0
        }
    }
    Component.onCompleted: {
        styleToolTips()
        liveSnapshot = liveController.snapshot
```

Run the check.

## Step 4: the question tooltip only when the question is cut off

Why: hovering the question at the top of an answer always pops up a tooltip repeating the same
text, even when the whole question is already visible.

In `rat/ui/quick/PDFDesk.qml`, find the button with `objectName: "answerQuestion"`. Near its end
are these two lines (this exact pair appears once in the file):

```qml
                                    ToolTip.visible: hovered
                                    ToolTip.text: desk.liveSnapshot.userQuery || ""
```

Replace them with:

```qml
                                    ToolTip.visible: hovered && !desk.answerQuestionOpen && contentItem.truncated
                                    ToolTip.delay: 600
                                    ToolTip.text: desk.liveSnapshot.userQuery || ""
```

Run the check.

## Step 5: explain "not verified", and a clearer excerpt label

Why: the answer card shows "Chưa được xác minh" in grey with no explanation, and a cut excerpt is
labelled with the placeholder "Trích đoạn (…)".

In `rat/ui/quick/PDFDesk.qml`, find the label with `objectName: "answerVerification"`. It ends
like this (after step 2 its font size is 12):

```qml
                                color: desk.liveSnapshot.answerVerification === "FAIL" ? desk.warningInk : desk.muted
                                font.pixelSize: 12
                                wrapMode: Text.Wrap
                            }
```

Replace those four lines with:

```qml
                                color: desk.liveSnapshot.answerVerification === "FAIL" ? desk.warningInk : desk.muted
                                font.pixelSize: 12
                                wrapMode: Text.Wrap
                                HoverHandler { id: verificationHover }
                                ToolTip.visible: verificationHover.hovered && desk.liveSnapshot.answerVerification !== "PASS"
                                ToolTip.delay: 600
                                ToolTip.text: desk.liveSnapshot.answerVerification === "FAIL"
                                    ? "Bước kiểm tra báo câu trả lời chưa khớp với nguồn. Hãy mở nguồn để đối chiếu."
                                    : "Chưa có bước kiểm tra nào xác nhận câu trả lời này. Hãy mở nguồn để tự đối chiếu."
                            }
```

Do not change the label's own `text:`. Do not change the string "Chưa xác định trang" anywhere;
a test checks it.

In the same file, replace this (it appears once):

```qml
                                    text: "Trích đoạn (…)"
```

with:

```qml
                                    text: "Đoạn trích đã được rút gọn"
```

Run the check.

## Step 6: buttons respond to a press

Why: buttons give no feedback when pressed. `tests/test_quick_press_depth.py` already describes
the wanted behaviour and four of its tests fail today. Read that test file before editing; do not
change it.

All three edits are in `rat/ui/quick/QuietButton.qml`.

Edit A. Find:

```qml
    property bool plain: false
```

Add directly below it:

```qml
    // How far the face sinks while pressed. Read by tests/test_quick_press_depth.py.
    readonly property int pressDepth: (down && !desk.reduceMotion) ? ((iconOnly || plain) ? 1 : 2) : 0
```

Edit B. Find:

```qml
    contentItem: RowLayout {
```

Add directly below it:

```qml
        transform: Translate { y: control.pressDepth; Behavior on y { NumberAnimation { duration: 70 } } }
```

Edit C. Find:

```qml
    background: Rectangle {
        visible: !control.plain
```

Add directly below those two lines:

```qml
        transform: Translate { y: control.pressDepth; Behavior on y { NumberAnimation { duration: 70 } } }
```

Then find the last line of that same `background: Rectangle { ... }` block:

```qml
        border.width: control.visualFocus ? 2 : (!control.primary && !control.iconOnly ? 1 : 0)
```

Add directly below it:

```qml
        Behavior on color { enabled: !desk.reduceMotion; ColorAnimation { duration: 90 } }
```

Verify this step with its own test first:

```bash
QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software .venv/bin/python -m pytest tests/test_quick_press_depth.py -q -p no:cacheprovider
```

Expected: `6 passed`. Then run the check. This time also confirm the four press-depth tests are
gone from the failures:

```bash
grep -c 'test_quick_press_depth' /tmp/rat_ui_polish/fail_after.txt
```

Expected: `0`.

## Finish

Run `git status --short`. The only entries you may have added are:

- `?? rat/ui/quick/DeskTheme.qml`
- ` M rat/ui/quick/PDFDesk.qml`
- ` M rat/ui/quick/MiniDesk.qml`
- ` M rat/ui/quick/ReasoningLab.qml`
- ` M rat/ui/quick/QuietButton.qml`
- other `.qml` files in `rat/ui/quick/` changed only by the font size command in step 2

Entries outside `rat/ui/quick/` were there before you started. Leave them alone. Do not commit.

Write a short report with:

1. Which steps you completed, and which you did not and why.
2. The `SMOKE_SAME` result of the last check.
3. The line counts of `fail_before.txt` and `fail_after.txt`, and the `comm` output of the last
   check.
4. Anything in the files that did not match what this document said.
5. This sentence, so the owner knows what still needs a human: "Tooltip colours and the button
   press movement were checked by tests and by loading the QML headless, not by looking at the
   running app."

## Out of scope (do not start these)

- Splitting `PDFDesk.qml` into smaller files.
- Anything under `rat/ui/` outside `rat/ui/quick/`, including the old QtWidgets windows.
- The build label in the composer footer. It is also the handle used to drag the window.
- Fixing tests that were already failing at the start, other than the press-depth ones.
- README, screenshots, documentation.
