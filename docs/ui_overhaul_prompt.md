# RAT UI overhaul: brief for the agent doing the work

You are overhauling the user interface of RAT, a local-first macOS assistant written in Python
with PyQt6 and Qt Quick (QML). The plan is in `docs/ui_overhaul_plan.md` (Vietnamese). This file
tells you how to carry it out safely. Read both files fully before you change anything.

**Each time you are started, do exactly one phase: the first phase that section 9 of the plan
("Tiến độ") does not show as finished. Then stop and report.** The owner reviews and commits
between phases.

## Decisions already made

- Keep the "paper desk and Chuột (the rat mascot)" identity. Do not redesign the mascot or the
  base colours. Rework the structure inside.
- The interface language is Vietnamese. Write new interface text in plain Vietnamese.
- Two decisions are still open (plan section 8: the timetable window, and MiniDesk). They only
  affect phase 4. If they are still open when you reach phase 4, stop and ask.

## Rules

1. **Where you may edit.** `rat/ui/`, `tools/ui_shots.py` and new `tools/ui_*.py` files, and
   section 9 of `docs/ui_overhaul_plan.md`. Phase 4 also allows `rat/app/router.py`. Phase 5 also
   allows `.github/workflows/ci.yml`, `README.md` and `docs/images/`. Nothing else. If a step
   seems to need a change anywhere else, stop and ask.
2. **The owner has unfinished work in this checkout.** `rat/config.py`, `rat/crawler/indexer.py`,
   `rat/engine/hyde.py`, `rat/engine/reranker.py`, `rat/os/app.py`, `tests/test_resident_warmup.py`
   and some untracked files are theirs. Never edit, revert or delete them.
3. **Git is read-only for you.** You may run `git status`, `git diff`, `git log` and `git show`.
   Do not commit, stash, reset, restore, checkout, switch branches, or push. Roll back with the
   folder backups described below.
4. **Tests are the specification.** Do not edit, skip, mark `xfail` or delete a test to make it
   pass. Two exceptions, both only with the owner's written approval in the chat: updating a file
   path inside a test after a rename, and removing tests of code that phase 4 deletes.
5. **Keep every `objectName` and the root `id: desk`.** Tests find items with
   `findChild(QQuickItem, "<objectName>")`. There are 85 object names in `PDFDesk.qml`. An item a
   test looks for must exist as soon as the desk has loaded, so do not put a view behind a
   `Loader` with `active: false` or a `StackView` unless the tests still find it. The safe default
   is to keep every view created and switch it with `visible:`, exactly as today.
6. **Forbidden file names.** Never create `rat/ui/quick/LookSurface.qml`, `SpeechBubble.qml`,
   `CompanionStatus.qml` or `PaperDesk.qml`. Never leave `*.bak` or `*.pre-task*` files in the
   repository root. `tests/test_architecture_anti_overengineering.py` enforces this.
7. **One kind of change per step.** A refactor step must not change any pixel. A design step must
   not move code between files. Do not mix them.
8. **No new dependencies.** Do not start the real app, download models, or use the network.
9. **Python must still run on 3.11.** No syntax that needs 3.12.
10. **No unrequested work.** Do not fix or improve anything the current phase does not ask for.
    Write down what you notice in your report instead.

## Setup, at the start of every session

Run these from the repository root. They record the accepted state you compare against.

```bash
mkdir -p /tmp/rat_ui_overhaul && rm -rf /tmp/rat_ui_overhaul/shots_base /tmp/rat_ui_overhaul/backup_start && mkdir /tmp/rat_ui_overhaul/backup_start && cp -R rat/ui /tmp/rat_ui_overhaul/backup_start/ui && cp tools/ui_*.py /tmp/rat_ui_overhaul/backup_start/ && cp docs/ui_overhaul_plan.md /tmp/rat_ui_overhaul/backup_start/
```

```bash
.venv/bin/python tools/ui_shots.py shoot /tmp/rat_ui_overhaul/shots_base
```

```bash
QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software .venv/bin/python -m pytest tests/test_quick_*.py tests/test_paper_and_mascot_interactions.py tests/test_reading_session.py tests/test_app_router.py tests/test_architecture_anti_overengineering.py -q -p no:cacheprovider 2>&1 | grep -E '^(FAILED|ERROR) ' | sed 's/ - .*//' | sort -u > /tmp/rat_ui_overhaul/fail_before.txt; wc -l < /tmp/rat_ui_overhaul/fail_before.txt
```

What to expect:

- `shoot` takes about three minutes and prints `saved` sixteen times (more after phase 0). It also
  writes `warnings.txt`. About 42 QML warnings exist already; they are part of the baseline.
- The test command takes between two and ten minutes. On 14/11/2026 it gave 29 failed and 52
  passed. These failures are known and are assigned to phases in the plan (phase 0 table).
- Three tests change result between runs without any code change:
  `tests/test_quick_escape.py::test_escape_on_a_folded_page_stays_folded`,
  `tests/test_quick_unified_flow.py::test_quick_step_6_cancellation_and_subsequent_query`,
  `tests/test_quick_pdf.py::test_header_controls_bounds_and_mode_instructions`.

## The check, after every step

```bash
rm -rf /tmp/rat_ui_overhaul/shots_now && .venv/bin/python tools/ui_shots.py shoot /tmp/rat_ui_overhaul/shots_now && .venv/bin/python tools/ui_shots.py compare /tmp/rat_ui_overhaul/shots_base /tmp/rat_ui_overhaul/shots_now
```

```bash
QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software .venv/bin/python -m pytest tests/test_quick_*.py tests/test_paper_and_mascot_interactions.py tests/test_reading_session.py tests/test_app_router.py tests/test_architecture_anti_overengineering.py -q -p no:cacheprovider 2>&1 | grep -E '^(FAILED|ERROR) ' | sed 's/ - .*//' | sort -u > /tmp/rat_ui_overhaul/fail_after.txt; comm -13 /tmp/rat_ui_overhaul/fail_before.txt /tmp/rat_ui_overhaul/fail_after.txt
```

A step passes when all of these hold:

- **Refactor step:** `compare` prints `0 of N images differ` and `0 new QML warnings`.
- **Design step:** `compare` prints `0 new QML warnings`, and the only images that differ are the
  ones you meant to change. Open every pair image it wrote (before on the left, after on the
  right) and look for clipped text, overlap, or a control pushed outside its card.
- **Tests:** the second command prints nothing, or only the three tests listed above. If it
  prints one of those three, run the check once more before deciding.

When a step passes:

1. Back up the same three things as at setup, into `/tmp/rat_ui_overhaul/after_<phase>_<step>`
   (for example `after_2_3`): `mkdir <folder> && cp -R rat/ui <folder>/ui && cp tools/ui_*.py
   docs/ui_overhaul_plan.md <folder>/`. In phase 4 also copy `rat/app/router.py`.
2. If it was a design step, the new look is now the accepted one: copy `shots_now` over
   `shots_base`.
3. Add one line to section 9 of the plan: date, phase and step, what you did, the check result.

When a step fails: read the error, fix it, and run the check again. If it fails a second time,
restore the last backup, stop, and report what failed with the exact output. To restore from
`<folder>`: `rm -rf rat/ui && cp -R <folder>/ui rat/ui`, then delete any `tools/ui_*.py` that
is not in `<folder>` and copy back the ones that are (`cp <folder>/ui_*.py tools/`), and copy back
`router.py` if the folder has it. Leave `docs/ui_overhaul_plan.md` as it is, so section 9 keeps
your notes.

Tests that were in `fail_before.txt` and now pass are progress. List them in your report.

## Facts about this code that will bite you

- **Scoping.** Small QML files such as `QuietButton.qml` read `desk.accent`, `desk.reduceMotion`
  and so on. They find `desk` because QML lets a component see the ids of the file that created
  it. Every window root must therefore keep `id: desk`. A view you move into its own file can
  still read `desk.*`. `ReadingDesk.qml` works differently: its root id is `reading` and it
  receives the desk as `required property var host`, reading `host.liveSnapshot` and so on (it
  has no `desk.` references). Do not rely on ids other than `desk` across files; pass those in as
  properties.
- **Inline components.** `component IconButton: ...`, `DeskProgress` and `PdfSnapshotCard` are
  declared inside `PDFDesk.qml`, and `Chip`, `Card` and `Metric` inside `ReasoningLab.qml`. An
  inline component is invisible to other files. Move it to its own file before moving anything
  that uses it.
- **Palette.** Colours live in `rat/ui/quick/DeskTheme.qml`. Each desk creates one
  (`property DeskTheme deskTheme`) and re-exports the colours as `desk.ink`, `desk.accent`, and so
  on. In `ReasoningLab.qml`, `backingColor` is the window behind the cards and has its own dark
  value on purpose; in `PDFDesk.qml` the same name is the sheet behind the paper.
- **Tooltips.** All tooltips in a window are one shared popup, styled once in `styleToolTips()`.
  Its colours are set with `Qt.binding(...)` so they follow light and dark. Keep that.
- **The build label is a handle.** The "Build 2026.…" label in the composer holds the
  `dragHandle` mouse area that moves the window. If you move or remove the label, the window must
  still be draggable.
- **`QuietButton.pressDepth`** is read by `tests/test_quick_press_depth.py`. Keep it.
- **Strings.** Tests assert some interface text, for example "Chưa xác định trang". Before you
  change any visible text, search `tests/` for it.
- **Font sizes were already raised once** (9 and 10 to 11, 11 to 12). Do not run a bulk
  replacement on `pixelSize` again.
- **Controls style.** The app forces `QT_QUICK_CONTROLS_STYLE=Basic`. Qt is 6.12, the venv Python
  is 3.12. Headless runs use `QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software`.
- **Live views are not in the preview scenes.** `PDFDesk.qml` has nine `liveSnapshot.view` states
  (`answer`, `page`, `search`, `finder`, `apps`, `reading`, `busy`, `error`, `none`), but
  `tools/ui_shots.py` only renders the seven preview scenes, which need no controller. Until
  phase 0 adds the live views, the pixel check does not cover them. This is why phase 0 comes
  first.
- **File references.** `PDFDesk.qml` is named in `rat/ui/quick_app.py`, `tools/ui_shots.py` and
  four test files. Renaming it needs the owner's approval for the test edits (rule 4).

## Phase 0: safety net

Goal: the check covers every screen.

1. Read how the tests build a live desk with fake data: `quick_env` in
   `tests/test_quick_unified_flow.py`, `complete_fixture` in
   `tests/test_quick_answer_presentation.py`, and `show_page` in `tests/test_quick_escape.py`.
2. Extend `tools/ui_shots.py` so `shoot` also renders `PDFDesk.qml` with a live controller in each
   of these states, light and dark, at widths 520 and 700: answer with two sources, page, search
   hits, finder results, apps catalogue, reading, busy, error. Build the states the way the tests
   do, with fixed fake data and a temporary state directory. Do not import from `tests/`; put
   shared fixture data in `tools/ui_shot_fixtures.py`. Name the images `live-<state>-<width>-<mode>.png`.
3. Run `shoot` twice into two folders and `compare` them. Every image must be identical between
   the two runs. If a state is not stable (a clock, an animation, a random value), make the
   fixture deterministic. If you cannot, leave that state out and say so in the report.
4. Try the same for `MiniDesk.qml` with a stub controller. If it is not working within about an
   hour of effort, leave it out and say so.

Done when: `shoot` covers the eight live states and two identical runs compare as identical.
This phase changes no file under `rat/ui/`, so the test check must print nothing new.

## Phase 1: design system

Goal: one source for every colour, text size and corner radius, and shared components in their
own files.

Do these as separate steps, in this order:

1. **Colour literals (refactor step).** Every `"#rrggbb"` literal in `rat/ui/quick/*.qml` outside
   `DeskTheme.qml` becomes a token. If the exact value already exists as a token, use it. If not,
   add a token to `DeskTheme.qml` named for its role (for example `codeSurface`, `shadow`) with
   exactly that value, including a dark value if the literal sat in a `darkMode ? … : …`
   expression. Add `windowColor` and move ReasoningLab's own `backingColor` value into it.
   `ReadingDesk.qml` reaches tokens through `host` (for example `host.deskTheme.<name>`).
   Pixels must not change.
2. **Scale tokens (refactor step).** Add to `DeskTheme.qml`: text sizes `textCaption: 11`,
   `textSmall: 12`, `textBody: 13`, `textLarge: 14`, `textTitle: 18`, `textDisplay: 24`; radii
   `radiusSmall: 4`, `radiusMedium: 8`, `radiusLarge: 12`; spacing `space1: 4`, `space2: 8`,
   `space3: 12`, `space4: 16`, `space6: 24`; durations `motionFast: 70`, `motionBase: 140`,
   `motionSlow: 220`. Read them as `desk.deskTheme.<name>`. Replace only the uses whose value
   already equals a token. Pixels must not change.
3. **Round text sizes (design step).** 15 becomes 14; 16 and 17 become 18; 23 and 26 become 24.
   Leave 30 and 36 (large glyphs). Review the pairs.
4. **Round radii (design step).** 5 or less becomes 4, except on items thinner than 8 pixels,
   which stay as they are. 6 to 9 becomes 8. 10 to 13 becomes 12. 14 and above is a pill: leave
   it if it already equals half the item's height. Review the pairs.
5. **Shared components (refactor steps, one component per step).** Move `IconButton`,
   `DeskProgress` and `PdfSnapshotCard` out of `PDFDesk.qml`; move `Chip` and `Card` out of
   `ReasoningLab.qml`; turn the five hand-written tag rectangles in `ArtifactCard.qml` into one
   `Badge.qml`. Pixels must not change.
6. **Gallery.** Add `rat/ui/quick/Gallery.qml` showing every shared component in its states, and
   add it to `shoot` in light and dark. Its root needs `id: desk`, `darkMode`, `reduceMotion`, a
   `DeskTheme` and the same re-exported colour names as `PDFDesk.qml`, because the components
   read `desk.*`.

Do not change spacing values in this phase. Spacing moves to the tokens screen by screen in
phase 3.

Done when: `grep -nE '"#[0-9a-fA-F]{6,8}"' rat/ui/quick/*.qml` prints lines only from
`DeskTheme.qml`; every `pixelSize:` and `radius:` in `rat/ui/quick/` is a token or one of the
stated exceptions.

## Phase 2: split the shell and fix navigation

Goal: `PDFDesk.qml` is a shell; each screen is its own file; going back works the same way
everywhere.

1. **Move one view per step (refactor steps).** Order, smallest first: busy and error, apps,
   finder, reading, search hits, page, answer. For each: cut the subtree out of `resultPaper`
   into `rat/ui/quick/<Name>View.qml`, create it at the same place with the same `objectName`s
   and the same `visible:` condition. Pixels must not change and no test may newly fail.
2. **Move the composer and the paper header** into their own files the same way.
3. **Navigation (design and behaviour step).** There are five back buttons (`backToAnswer`,
   `backToSearch`, `backFromReading`, `backFromApps`, `backFromFinder`). Read
   `tests/test_quick_escape.py` first: it is the specification for what Esc and "back" do from
   every screen. Give the controller one navigation stack and make all five buttons and Esc use
   it. Keep the five object names, since tests use them. The six tests in
   `tests/test_quick_escape.py` should pass afterwards.
4. **Split `rat/ui/quick_pdf_controller.py`** (2,222 lines) along the same screen boundaries, only
   if steps 1 to 3 are finished and passing. Behaviour must not change.
5. Do not rename `PDFDesk.qml` in this phase. Propose a new name in your report.

Done when: `PDFDesk.qml` is under 600 lines; every refactor step compared identical; no test newly
fails; the Esc tests pass.

## Phase 3: redesign the flows

Goal: what the user sees. One item per step. For each item, read the failing tests named in the
plan's phase 0 table first; where a test describes the behaviour, the test wins over this text.
Use the spacing tokens on every screen you touch.

1. **Composer.** Move the build number out of the input area into the window menu or an "about"
   line, and keep the window draggable by the composer's frame. When the input is empty and
   nothing is running, show three suggestion chips: "Tìm một tệp", "Hỏi về tài liệu đang mở",
   "Lịch hôm nay". A chip fills the input; it does not submit. Indexing status shows in the
   composer footer as `tests/test_quick_index_status.py` describes.
2. **Paper header.** One back control on the left, then the full title. The title elides at the
   end, never in the middle, and shows the whole text in a tooltip when cut. No control may reach
   outside the paper at widths 520, 700 and 980
   (`test_header_controls_bounds_and_mode_instructions`).
3. **One result layout.** Every result reads top to bottom: answer, then evidence (sources, page,
   verification state), then at most three actions. Apply it to the answer view, the timetable
   card, the web page card, and file results.
4. **Errors have a way out.** Every error message carries one button that fixes it. For "Hãy chọn
   một tệp PDF." the button is "Chọn tệp PDF" and opens the existing file dialog.
5. **Progress.** A collapsible strip of steps inside the paper shows what Chuột is doing, with a
   stop button. See `test_answer_copy_and_source_page_journey` for `processDetailsOpen`.
6. **Widths.** The paper is never wider than the window. Check 520, 700 and 980.
7. **First run.** Three short steps on the desk itself: the shortcut, choosing a folder, trying
   one request. Read `rat/ui/onboarding_dialog.py` for the existing content.

Done when: each item has before and after pairs you have looked at, and the tests the plan
assigns to phase 3 pass or you have reported exactly why one does not.

## Phase 4: one interface

Stop first if plan section 8 still shows the timetable window or MiniDesk as undecided.

1. Build Settings in Qt Quick for the main desk. `rat/ui/settings_dialog.py` lists the settings;
   `MiniDesk.qml` already has a preferences surface to borrow from.
2. Carry out the owner's two decisions.
3. List every file under `rat/` that imports `PyQt6.QtWidgets` (20 files, about 13,000 lines on
   14/11/2026), every place that imports those files, and every test that imports them. Put the
   three lists in your report and **stop for approval before deleting anything**.
4. After approval: delete the files, remove the `spotlight`, `widgets` and `omnibar` modes from
   `rat/app/router.py`, and remove the approved tests.

Done when: `tests/test_quick_only_runtime.py` passes.

## Phase 5: finish

1. Accessibility: `Accessible.name` and `Accessible.description` on `ArtifactCard.qml` and
   `SpeechSurface.qml`; every explanation that exists only in a tooltip also as
   `Accessible.description`; a keyboard path to every action.
2. Motion: paper opening, screen change, press feedback. All of it off when `desk.reduceMotion`.
3. Restore `pokeStreak` and `paperDragX` as `tests/test_paper_and_mascot_interactions.py`
   describes.
4. When the interface test group is fully green, add it to `.github/workflows/ci.yml`.
5. Regenerate the README screenshots with `tools/ui_shots.py`.

## Stop and ask the owner when

- The check fails twice on the same step.
- A step needs a file outside the allowed paths, or a test edit.
- A test and this brief disagree and the test does not settle it.
- You are about to delete a file that this brief does not name.
- A decision is needed that the plan does not make.

## Report, at the end of the phase

1. Which phase and steps you finished, and which you did not.
2. For the last check: the `compare` summary lines and the output of the `comm -13` command.
3. Tests that were failing at the start and now pass.
4. Files created, renamed or deleted.
5. For design steps: the folder holding the pair images, and one sentence per changed screen.
6. Anything you noticed but did not change.
7. What still needs a person to look at in the running app. You have not seen the real app;
   say so.
