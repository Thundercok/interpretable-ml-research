import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs

Rectangle {
    id: desk
    objectName: "paperDesk"
    width: 640
    height: 640
    color: floatingWindow ? "transparent" : deskTheme.windowColor

    property bool quitOnClose: true
    property DeskTheme deskTheme: DeskTheme { darkMode: desk.darkMode; reduceMotion: desk.reduceMotion }
    property alias editor: composer.editor
    property alias composerResize: composer.composerResize
    property alias paperHeader: resultPaper.paperHeader
    property alias answerView: resultPaper.answerView
    property alias pageReaderView: resultPaper.pageReaderView
    property alias resultScroll: resultPaper.resultScroll
    property alias finderResults: resultPaper.finderResults
    property alias settingsView: resultPaper.settingsView
    property alias appsResultsLoader: resultPaper.appsResultsLoader
    property bool darkMode: false
    property bool reduceMotion: false
    property url mascotSource
    property string previewScene: "idle"
    property string phase: "idle"
    property bool expanded: false
    property bool unread: false
    property bool sourceOpen: false
    property bool logOpen: false
    property bool compactTrail: false
    property bool answerSourcesOpen: false
    property bool answerQuestionOpen: false
    property bool copied: false
    property bool readyForMotion: false
    property bool showOnboardingGuide: true

    // Mascot poke streak micro-interaction (Step 4.2)
    property int pokeStreak: 0
    function pokeRat() {
        if (desk.pokeStreak >= 3) {
            desk.pokeStreak = 1
        } else {
            desk.pokeStreak += 1
        }
        if (mascotItem && mascotItem.triggerPokeReaction) {
            mascotItem.triggerPokeReaction(desk.pokeStreak)
        }
        pokeTimer.restart()
    }
    Timer {
        id: pokeTimer
        interval: 1200
        repeat: false
        onTriggered: {
            desk.pokeStreak = 0
        }
    }

    // Tactile paper dragging and dismiss physics (Step 4.1 & 4.3)
    property real paperDragTargetX: 0.0
    property real paperDragTargetY: 0.0
    property real paperDragX: 0.0
    property real paperDragY: 0.0
    property bool paperDismissing: false

    onPaperDragTargetXChanged: desk.paperDragX = desk.paperDragTargetX
    onPaperDragTargetYChanged: desk.paperDragY = desk.paperDragTargetY

    Behavior on paperDragX {
        enabled: desk.readyForMotion && !desk.reduceMotion
        NumberAnimation {
            duration: desk.paperDismissing ? 95 : 110
            easing.type: desk.paperDismissing ? Easing.InQuad : Easing.OutBack
            easing.overshoot: 1.35
        }
    }
    Behavior on paperDragY {
        enabled: desk.readyForMotion && !desk.reduceMotion
        NumberAnimation {
            duration: desk.paperDismissing ? 95 : 110
            easing.type: desk.paperDismissing ? Easing.InQuad : Easing.OutBack
            easing.overshoot: 1.35
        }
    }
    Timer {
        id: paperDismissTimer
        interval: 95
        repeat: false
        onTriggered: {
            desk.paperDismissing = false
            desk.paperDragTargetX = 0.0
            desk.paperDragTargetY = 0.0
            desk.paperDragX = 0.0
            desk.paperDragY = 0.0
            desk.foldWorkbench()
        }
    }
    function dismissPaperWithFlick(targetX, targetY) {
        desk.paperDismissing = true
        desk.paperDragTargetX = targetX
        desk.paperDragTargetY = targetY
        desk.paperDragX = targetX
        desk.paperDragY = targetY
        paperDismissTimer.restart()
    }
    readonly property var composerKeyHints: {
        if (!liveMode) return []
        if (liveSnapshot.view === "page" || Boolean(liveSnapshot.fileName)) {
            return [
                {"key": "↵", "label": "hỏi Chuột"},
                {"key": "⌘F", "label": "tìm chữ trong PDF"}
            ]
        }
        return []
    }
    property var liveController: null
    property var liveSnapshot: ({})
    property int selectedFinderIndex: -1
    property int selectedAppGridIndex: 0
    readonly property bool liveMode: liveController !== null
    // Keep rich text stable when only mode/status changes; reparsing loses selection.
    readonly property string displayedAnswerHtml: (darkMode ? liveSnapshot.answerHtmlDark : liveSnapshot.answerHtml) || ""
    readonly property int gridColumns: Math.max(3, Math.min(6, Math.floor((desk.resultScroll ? desk.resultScroll.availableWidth : 520) / 105)))
    readonly property var allApps: desk.liveSnapshot.installedApps || []
    readonly property var filteredApps: {
        var q = (desk.editor ? desk.editor.text : "").trim().toLowerCase()
        if (!q || desk.liveSnapshot.view !== "apps") return desk.allApps
        return desk.allApps.filter(function(app) {
            if (app.name && app.name.toLowerCase().indexOf(q) !== -1) return true
            if (app.bundle_id && app.bundle_id.toLowerCase().indexOf(q) !== -1) return true
            if (app.names && app.names.some(function(alias) { return alias.toLowerCase().indexOf(q) !== -1 })) return true
            if (app.description && app.description.toLowerCase().indexOf(q) !== -1) return true
            if (app.purposes && app.purposes.some(function(p) { return p.toLowerCase().indexOf(q) !== -1 })) return true
            return false
        })
    }

    onSelectedFinderIndexChanged: {
        Qt.callLater(function() {
            if (selectedFinderIndex >= 0 && liveSnapshot.view === "finder") {
                finderResults.scrollSelectionIntoView(selectedFinderIndex)
            }
        })
    }

    function scrollAppIntoView(idx) {
        if (!appsResultsLoader.item) return
        var repeater = appsResultsLoader.item.appsRepeaterItem
        if (!repeater) return
        var cell = repeater.itemAt(idx)
        if (!cell) return
        if (resultScroll.contentHeight <= resultScroll.height) return

        var point = cell.mapToItem(resultContents, 0, 0)
        var itemTop = point.y
        var itemBottom = point.y + cell.height + 46

        var viewTop = resultScroll.ScrollBar.vertical.position * resultScroll.contentHeight
        var viewBottom = viewTop + resultScroll.height

        if (itemTop < viewTop) {
            resultScroll.ScrollBar.vertical.position = Math.max(0, itemTop / resultScroll.contentHeight)
        } else if (itemBottom > viewBottom) {
            resultScroll.ScrollBar.vertical.position = Math.min(
                1.0 - (resultScroll.height / resultScroll.contentHeight),
                (itemBottom - resultScroll.height) / resultScroll.contentHeight
            )
        }
    }

    onSelectedAppGridIndexChanged: {
        if (selectedAppGridIndex >= 0 && liveSnapshot.view === "apps") {
            scrollAppIntoView(selectedAppGridIndex)
        }
    }

    onFilteredAppsChanged: {
        if (desk.liveSnapshot.view === "apps") {
            if (desk.filteredApps.length === 0) {
                desk.selectedAppGridIndex = -1
            } else if (desk.selectedAppGridIndex < 0 || desk.selectedAppGridIndex >= desk.filteredApps.length) {
                desk.selectedAppGridIndex = 0
            }
        }
    }
    property bool floatingWindow: liveMode
    property bool spaciousWorkbench: false
    readonly property bool roomyActive: (spaciousWorkbench || currentWorkspaceMode === "multi") && expanded && hasWorkbench
    readonly property real composerHeight: composer.height
    property real maxPaperHeight: 520
    readonly property real preferredWindowHeight: 48 + composer.height + Math.max(116, expanded && hasWorkbench ? resultPaper.height - 22 : 0)
    readonly property bool hasWorkbench: liveMode ? Boolean(liveSnapshot.hasWorkbench) : phase === "working" || phase === "result"
    readonly property bool hasAnswerPreview: liveMode && liveSnapshot.view === "answer"
    readonly property bool hasReadingPreview: liveMode && liveSnapshot.view === "reading"
    readonly property bool cancelledAnswer: hasAnswerPreview && liveSnapshot.answerOutcome === "cancelled"
    readonly property bool emptyCancelledAnswer: cancelledAnswer && !(liveSnapshot.answerText || "").trim().length
    readonly property bool hasPagePreview: liveMode && liveSnapshot.view === "page" && !liveSnapshot.busy && !liveSnapshot.errorCode
    readonly property string pagePreviewTitle: "Đang đọc trang " + liveSnapshot.pageLabel
    readonly property string uiBuildLabel: "Build 2026.10.25.33"
    readonly property string currentWorkspaceMode: liveMode ? (liveSnapshot.workspaceMode || "single") : "single"
    readonly property bool isSideBySidePdfActive: desk.liveMode && desk.expanded && desk.hasWorkbench && desk.liveSnapshot.view === "answer" && Boolean(desk.liveSnapshot.fileName) && (desk.currentWorkspaceMode === "multi" || desk.roomyActive)
    property string readerDisplayMode: "matched"
    property bool processDetailsOpen: false
    property bool contextExpanded: false
    property string expandedEvidenceText: ""
    property bool sourceCopied: false
    property bool inlineFindOpen: false
    property bool showAllFinderHits: false
    readonly property var allFinderHits: liveSnapshot.finderHits || []
    readonly property var visibleFinderHits: showAllFinderHits ? allFinderHits : allFinderHits.slice(0, 3)
    readonly property int remainingFinderHits: Math.max(0, allFinderHits.length - 3)
    readonly property bool hasLatentFinderHits: liveMode && !liveSnapshot.busy && !liveSnapshot.fileName && liveSnapshot.view !== "finder" && liveSnapshot.view !== "apps" && allFinderHits.length > 0
    readonly property var searchHits: liveSnapshot.items || []
    onVisibleFinderHitsChanged: {
        if (selectedFinderIndex >= (visibleFinderHits || []).length) {
            selectedFinderIndex = -1
        }
    }
    onShowAllFinderHitsChanged: {
        if (selectedFinderIndex >= (visibleFinderHits || []).length) {
            selectedFinderIndex = -1
        }
    }
    readonly property bool hasFinderPreview: liveMode && liveSnapshot.view === "finder" && allFinderHits.length > 0
    readonly property bool incompletePreview: hasAnswerPreview && liveSnapshot.answerOutcome !== "completed"
    readonly property string previewBody: liveSnapshot.answerExcerpt || (incompletePreview ? (liveSnapshot.status || "Yêu cầu chưa hoàn tất") : "Mở câu trả lời đầy đủ")
    readonly property string previewMeta: incompletePreview ? (liveSnapshot.answerOutcome === "cancelled" ? "Đã dừng · chưa hoàn tất" : "Chưa hoàn tất · mở để xem thông báo")
        : "Xem nhanh" + (liveSnapshot.answerReadScope ? " · " + liveSnapshot.answerReadScope : ((liveSnapshot.answerSources || []).length ? " · " + liveSnapshot.answerSources.length + " tham chiếu" : ""))
          + " · " + (liveSnapshot.answerVerification === "PASS" ? "Đạt kiểm tra được báo cáo" : liveSnapshot.answerVerification === "FAIL" ? "Kiểm tra chưa đạt" : "Chưa xác minh")
    readonly property bool noticeVisible: liveMode ? unread && !expanded : phase === "result" && unread && !expanded
    readonly property string sceneKey: hasWorkbench ? (expanded ? phase : unread ? "unread" : "folded") : phase
    readonly property bool animationsRunning: (composer.composerResize ? composer.composerResize.running : false) || (resultPaper.paperMove ? resultPaper.paperMove.running : false)
    readonly property color ink: deskTheme.ink
    readonly property color muted: deskTheme.muted
    readonly property color paperColor: deskTheme.paperColor
    readonly property color inputColor: deskTheme.inputColor
    readonly property color windowColor: deskTheme.windowColor
    readonly property color backingColor: deskTheme.backingColor
    readonly property color edge: deskTheme.edge
    readonly property color accent: deskTheme.accent
    readonly property color accentText: deskTheme.accentText
    readonly property color warningInk: deskTheme.warningInk
    readonly property color pdfInk: deskTheme.pdfInk
    readonly property color sheetPaperColor: deskTheme.sheetPaperColor
    // Shared states for the live desk; retain the existing paper/sage palette.
    readonly property color selectedSurface: deskTheme.selectedSurface
    readonly property color selectedEdge: deskTheme.selectedEdge
    readonly property color utilitySurface: deskTheme.utilitySurface
    readonly property color hoverSurface: deskTheme.hoverSurface
    readonly property color errorSurface: deskTheme.errorSurface
    readonly property color errorEdge: deskTheme.errorEdge
    readonly property color errorInk: deskTheme.errorInk
    readonly property int textCaption: deskTheme.textCaption
    readonly property int textSmall: deskTheme.textSmall
    readonly property int textBody: deskTheme.textBody
    readonly property int textLarge: deskTheme.textLarge
    readonly property int textTitle: deskTheme.textTitle
    readonly property int textDisplay: deskTheme.textDisplay
    readonly property int radiusSmall: deskTheme.radiusSmall
    readonly property int radiusMedium: deskTheme.radiusMedium
    readonly property int radiusLarge: deskTheme.radiusLarge
    readonly property int cardRadius: deskTheme.radiusLarge
    readonly property int controlRadius: deskTheme.radiusLarge

    function cleanSnippetText(raw) {
        if (!raw) return ""
        var s = String(raw).replace(/(\w+)-\s*\n\s*(\w+)/g, "$1$2")
        s = s.replace(/\r\n/g, "\n")
        var paragraphs = s.split(/\n\s*\n+/)
        for (var i = 0; i < paragraphs.length; i++) {
            paragraphs[i] = paragraphs[i].replace(/[ \t]*\n[ \t]*/g, " ").replace(/[ \t]+/g, " ").trim()
        }
        return paragraphs.join("\n\n")
    }

    signal copyRequested(string text)
    signal moveRequested()
    signal closeRequested()

    function syncLive() {
        if (!liveMode) return
        const next = liveController.snapshot
        if (next.pageNumber !== liveSnapshot.pageNumber) {
            copied = false
            if (pageReaderView.matchedExcerptText) pageReaderView.matchedExcerptText.deselect()
        }
        if (next.fileName !== liveSnapshot.fileName || next.view !== "page") {
            copied = false
        }
        if (next.fileName !== liveSnapshot.fileName) {
            paperHeader.pagePicker.value = 1
            pdfSearchField.text = ""
        }
        if (next.view === "page" && next.pageNumber) paperHeader.pagePicker.value = next.pageNumber
        if (next.view === "page") {
            readerDisplayMode = next.hasMatchedSnippet ? "matched" : "text"
        }
        if (next.view === "search" && next.searchQuery && !pdfSearchField.activeFocus) pdfSearchField.text = next.searchQuery
        if (next.view !== "finder") {
            selectedFinderIndex = -1
            showAllFinderHits = false
        } else if (selectedFinderIndex >= (visibleFinderHits || []).length) {
            selectedFinderIndex = -1
        }
        if (next.view !== "apps") selectedAppGridIndex = 0
        if (next.answerText !== liveSnapshot.answerText || next.userQuery !== liveSnapshot.userQuery) {
            answerSourcesOpen = false
            answerQuestionOpen = false
            contextExpanded = false
            expandedEvidenceText = ""
        }
        liveSnapshot = next
        phase = next.phase
        expanded = next.expanded
        unread = next.unread
    }

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
    function applyScene(scene) {
        if (liveMode) return
        phase = scene === "unread" || scene === "folded" ? "result" : scene
        expanded = scene === "working" || scene === "result"
        unread = scene === "unread"
        sourceOpen = false
        logOpen = false
        copied = false
    }
    function openWorkbench() {
        if (!hasWorkbench) return
        if (liveMode) { liveController.setExpanded(true); return }
        expanded = true
        unread = false
    }
    function handleEscape() {
        if (desk.inlineFindOpen) {
            desk.inlineFindOpen = false;
            if (desk.editor) desk.editor.forceActiveFocus();
            return true;
        }
        if (!desk.liveMode) {
            if (desk.expanded) {
                desk.foldWorkbench();
                return true;
            }
            return false;
        }
        if (desk.liveSnapshot.view === "reading") {
            desk.liveController.closeReadingDesk();
            if (desk.editor) desk.editor.forceActiveFocus();
            return true;
        }
        if (desk.liveSnapshot.view === "apps") {
            var restored = desk.liveController.closeAppsView();
            if (desk.editor) {
                desk.editor.text = restored;
                desk.editor.forceActiveFocus();
            }
            return true;
        }
        if (desk.liveSnapshot.view === "finder") {
            if (desk.selectedFinderIndex >= 0) {
                desk.selectedFinderIndex = -1;
            } else {
                desk.liveController.dismissFinder();
            }
            if (desk.editor) desk.editor.forceActiveFocus();
            return true;
        }
        if (desk.liveSnapshot.view === "settings") {
            desk.liveController.closeSettings();
            if (desk.editor) desk.editor.forceActiveFocus();
            return true;
        }
        if (desk.expanded && desk.liveSnapshot.view === "page") {
            if (desk.liveSnapshot.pageReturnView === "search" || desk.liveSnapshot.canBack) {
                desk.liveController.backToSearch();
            } else {
                desk.liveController.backToAnswer();
            }
            if (desk.editor) desk.editor.forceActiveFocus();
            return true;
        }
        if (desk.expanded) {
            desk.foldWorkbench();
            if (desk.editor) desk.editor.forceActiveFocus();
            return true;
        }
        if (!desk.quitOnClose) {
            desk.closeRequested();
            return true;
        }
        return false;
    }
    function foldWorkbench() {
        if (liveMode) { liveController.setExpanded(false); editor.forceActiveFocus(); return }
        expanded = false
        unread = false
        editor.forceActiveFocus()
    }
    function openPdfSearch() {
        if (!liveMode || !liveSnapshot.fileName) return
        inlineFindOpen = true
        pdfSearchField.forceActiveFocus()
        pdfSearchField.selectAll()
    }
    function openPdfSearchPopup() {
        openPdfSearch()
    }
    function runPdfSearchAction() {
        if (!liveMode || !liveSnapshot.fileName || liveSnapshot.busy) return
        const kw = pdfSearchField.text.trim()
        if (!kw.length) return
        inlineFindOpen = false
        liveController.search(kw)
        editor.forceActiveFocus()
    }
    function isAppsCommand(value) {
        const command = value.trim().toLowerCase()
        return command === "/apps" || command === "ứng dụng" || command === "mở ứng dụng"
    }
    function submitDraft() { composer.submitDraft() }
    function handleComposerReturn(event) { composer.handleComposerReturn(event) }
    function stopRequest() { composer.stopRequest() }
    function requestCopy() {
        if (liveMode) {
            var sel = "";
            if (desk.liveSnapshot.view === "answer") {
                sel = (answerView.answerText && answerView.answerText.selectedText) ? answerView.answerText.selectedText : "";
            } else if (desk.liveSnapshot.view === "page") {
                if (pageReaderView.matchedExcerptText && pageReaderView.matchedExcerptText.visible && pageReaderView.matchedExcerptText.selectedText) {
                    sel = pageReaderView.matchedExcerptText.selectedText;
                } else {
                    sel = desk.liveSnapshot.rawMatchedSnippet || desk.liveSnapshot.matchedSnippet || "";
                }
            }
            liveController.copyCitation(sel);
            return
        }
        copyRequested("Tối đa 24 tín chỉ cho học kỳ chính. Học kỳ hè tối đa 12 tín chỉ.\n(Nội dung minh họa.)")
        copied = true
        copyFeedback.restart()
    }
    onPreviewSceneChanged: applyScene(previewScene)
    Component.onCompleted: { styleToolTips(); if (liveMode) syncLive(); else applyScene(previewScene); readyForMotion = true }

    Connections {
        target: desk.liveController
        function onChanged() { desk.syncLive() }
        function onCopyConfirmed(text) {
            desk.copied = true
            copyFeedback.restart()
        }
    }
    FileDialog {
        id: pdfDialog
        title: "Chọn một PDF để tìm và đọc"
        nameFilters: ["PDF (*.pdf *.PDF)"]
        onAccepted: { if (desk.liveMode) desk.liveController.openPdfDocument(String(selectedFile)) }
    }
    function openPdfDialog() { pdfDialog.open() }
    function openReadingProfileDialog() { readingProfileDialog.open() }
    FileDialog {
        id: readingProfileDialog
        objectName: "readingProfileDialog"
        title: "Mở hồ sơ lá số đã lưu từ Natal Atlas"
        nameFilters: ["Hồ sơ lá số JSON (*.json *.JSON)"]
        onAccepted: { if (desk.liveMode) desk.liveController.importReadingProfile(String(selectedFile)) }
    }
    DropArea {
        id: pdfDropArea
        anchors.fill: parent
        enabled: desk.liveMode
        onDropped: drop => {
            if (drop.hasUrls && drop.urls.length === 1) {
                if (desk.liveSnapshot.view === "reading" && /\.json$/i.test(String(drop.urls[0]))) {
                    drop.accepted = desk.liveController.importReadingProfile(String(drop.urls[0]))
                    return
                }
                desk.liveController.openPdfDocument(String(drop.urls[0]))
                drop.accepted = true
            } else drop.accepted = false
        }
    }

    Timer {
        id: copyFeedback
        interval: 1600
        repeat: false
        onTriggered: desk.copied = false
    }

    Timer {
        id: sourceCopyFeedback
        interval: 1600
        repeat: false
        onTriggered: desk.sourceCopied = false
    }



    PreviewScenePicker { id: scenePicker }

    Item {
        id: unit
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.leftMargin: desk.liveMode ? 24 : 32
        anchors.rightMargin: desk.liveMode ? 24 : 32
        anchors.bottomMargin: desk.liveMode ? 24 : 28
        height: parent.height - (desk.liveMode ? 48 : 100)
        readonly property int paperOffset: desk.roomyActive ? 0 : (width < 520 ? 110 : 128)

        Rectangle {
            visible: desk.expanded && desk.hasWorkbench
            x: resultPaper.x - 6
            y: resultPaper.y - 5
            width: resultPaper.width
            height: resultPaper.height
            radius: 15
            rotation: -0.9
            antialiasing: true
            color: desk.backingColor
            border.width: 1
            border.color: desk.edge
            z: 0
        }
        SidePdfPane { id: sidePdfPane; y: resultPaper.y; height: resultPaper.height }
        ResultPaper { id: resultPaper }

        Rectangle {
            visible: true
            x: composer.x + 6
            y: (desk.expanded && desk.hasWorkbench) ? (composer.y + 1) : (composer.y - 5)
            width: composer.width
            height: (desk.expanded && desk.hasWorkbench) ? (composer.height - 4) : composer.height
            radius: composer.radius
            rotation: (desk.expanded && desk.hasWorkbench) ? -0.8 : -1.1
            antialiasing: true
            color: desk.backingColor
            border.width: 1
            border.color: desk.edge
            z: 0
        }
        Rectangle {
            id: firstLaunchGuide
            objectName: "firstLaunchGuide"
            visible: desk.liveMode && !desk.expanded && !desk.hasWorkbench && !desk.liveSnapshot.fileName && desk.liveSnapshot.view === "none" && (desk.editor ? desk.editor.text.length === 0 : true) && desk.showOnboardingGuide
            anchors.bottom: composer.top
            anchors.bottomMargin: 14
            anchors.horizontalCenter: composer.horizontalCenter
            width: composer.width
            implicitHeight: guideCol.implicitHeight + 20
            radius: desk.cardRadius
            color: desk.utilitySurface
            border.width: 1
            border.color: desk.edge
            z: 2
            ColumnLayout {
                id: guideCol
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.margins: 10
                spacing: 8

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 6
                    DeskIcon { name: "sparkle"; color: desk.accent; width: 13; height: 13; Layout.preferredWidth: 13; Layout.preferredHeight: 13 }
                    Label {
                        text: "3 bước bắt đầu cùng RAT"
                        font.pixelSize: 12
                        font.weight: Font.DemiBold
                        color: desk.accent
                        Layout.fillWidth: true
                    }
                    IconButton {
                        glyph: "close"
                        iconSize: 10
                        implicitWidth: 18
                        implicitHeight: 18
                        padding: 3
                        Accessible.name: "Đóng hướng dẫn"
                        onClicked: desk.showOnboardingGuide = false
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8

                    RowLayout {
                        spacing: 4
                        Rectangle {
                            implicitWidth: 16; implicitHeight: 16; radius: 8; color: desk.selectedSurface
                            Label { anchors.centerIn: parent; text: "1"; font.pixelSize: 10; font.weight: Font.Bold; color: desk.accent }
                        }
                        Label { text: "⌥Space mở bàn"; font.pixelSize: 11; color: desk.ink }
                    }

                    RowLayout {
                        spacing: 4
                        Rectangle {
                            implicitWidth: 16; implicitHeight: 16; radius: 8; color: desk.selectedSurface
                            Label { anchors.centerIn: parent; text: "2"; font.pixelSize: 10; font.weight: Font.Bold; color: desk.accent }
                        }
                        Label { text: "Thả PDF vào đây"; font.pixelSize: 11; color: desk.ink }
                    }

                    RowLayout {
                        spacing: 4
                        Rectangle {
                            implicitWidth: 16; implicitHeight: 16; radius: 8; color: desk.selectedSurface
                            Label { anchors.centerIn: parent; text: "3"; font.pixelSize: 10; font.weight: Font.Bold; color: desk.accent }
                        }
                        Label { text: "Gõ câu hỏi tiếng Việt"; font.pixelSize: 11; color: desk.ink }
                    }
                }
            }
        }
        FoldedNote { id: note; composerX: composer.x; composerY: composer.y; composerWidth: composer.width }
        MascotArea { id: mascotItem; composerX: composer.x; composerY: composer.y }
        FinderDrawerTab { id: finderDrawerTab; anchors.right: composer.right; anchors.rightMargin: 18; y: composer.y - height + 9 }
        Rectangle {
            id: inlineFindBar
            objectName: "inlineFindBar"
            visible: desk.liveMode && desk.inlineFindOpen && Boolean(desk.liveSnapshot.fileName)
            x: desk.expanded ? (resultPaper.x + 22) : composer.x
            y: desk.expanded ? (resultPaper.y + 46) : (composer.y - height - 8)
            width: desk.expanded ? (resultPaper.width - 44) : composer.width
            height: 36
            radius: 8
            color: desk.utilitySurface
            border.width: 1
            border.color: desk.selectedEdge
            z: 6

            DeskIcon {
                id: inlineFindSearchIcon
                anchors.left: parent.left
                anchors.leftMargin: 8
                anchors.verticalCenter: parent.verticalCenter
                name: "search"
                color: desk.accent
                width: 13
                height: 13
            }

            IconButton {
                id: closeInlineFindBtn
                objectName: "closeInlineFind"
                anchors.right: parent.right
                anchors.rightMargin: 6
                anchors.verticalCenter: parent.verticalCenter
                glyph: "close"
                iconSize: 11
                implicitWidth: 22
                implicitHeight: 22
                padding: 5
                Accessible.name: "Đóng thanh tìm chữ"
                onClicked: {
                    desk.inlineFindOpen = false
                    editor.forceActiveFocus()
                }
            }

            QuietButton {
                id: runPdfSearchBtn
                objectName: "runPdfSearch"
                anchors.right: closeInlineFindBtn.left
                anchors.rightMargin: 4
                anchors.verticalCenter: parent.verticalCenter
                text: "Tìm"
                primary: true
                implicitHeight: 24
                topPadding: 2
                bottomPadding: 2
                leftPadding: 8
                rightPadding: 8
                font.pixelSize: 12
                enabled: !desk.liveSnapshot.busy && pdfSearchField.text.trim().length > 0
                onClicked: desk.runPdfSearchAction()
            }

            TextField {
                id: pdfSearchField
                objectName: "pdfSearchField"
                anchors.left: inlineFindSearchIcon.right
                anchors.leftMargin: 6
                anchors.right: runPdfSearchBtn.left
                anchors.rightMargin: 6
                anchors.verticalCenter: parent.verticalCenter
                implicitHeight: 28
                padding: 0
                leftPadding: 4
                rightPadding: 4
                font.pixelSize: 13
                color: desk.ink
                placeholderText: "Tìm từ khóa trong PDF…"
                placeholderTextColor: desk.muted
                selectionColor: desk.accent
                selectedTextColor: desk.accentText
                selectByMouse: true
                Accessible.name: "Từ khóa cần tìm trong PDF"
                background: null
                onAccepted: desk.runPdfSearchAction()
                Keys.onEscapePressed: {
                    desk.inlineFindOpen = false
                    editor.forceActiveFocus()
                }
            }
        }
        Composer { id: composer; unitWidth: unit.width; paperX: resultPaper.x; paperWidth: resultPaper.width; containsDrag: Boolean(pdfDropArea && pdfDropArea.containsDrag) }
    }
    DeskShortcuts { id: deskShortcuts }
}
