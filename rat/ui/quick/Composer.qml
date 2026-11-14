import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: composer
    objectName: "composer"
    property real unitWidth: parent ? parent.width : 580
    property real paperX: 0
    property real paperWidth: 520
    property bool containsDrag: false
    property alias editor: editor
    property alias composerResize: composerResize
    x: desk.isSideBySidePdfActive ? resultPaper.x : Math.max(0, Math.floor((unit.width - width) / 2))
    width: desk.isSideBySidePdfActive ? resultPaper.width : Math.min(580, unit.width)
    anchors.bottom: parent.bottom
    height: desk.phase === "startup" ? 94 : Math.min(148, Math.max(94, editorColumn.implicitHeight + 18))
    radius: 18
    color: desk.inputColor
    border.width: containsDrag ? 1.5 : 1
    border.color: containsDrag ? desk.accent : (editor.activeFocus ? desk.selectedEdge : desk.edge)
    z: 5
    clip: true
    Behavior on height {
        enabled: desk.readyForMotion && !desk.reduceMotion
        NumberAnimation { id: composerResize; duration: 160; easing.type: Easing.OutCubic }
    }
    ColumnLayout {
        visible: desk.phase === "startup"
        anchors.fill: parent
        anchors.margins: 15
        spacing: 15
        RowLayout {
            Layout.fillWidth: true
            Label { text: "RAT"; color: desk.accent; font.pixelSize: 13; font.weight: Font.Medium; Layout.fillWidth: true }
            Label { text: "Đang mở bàn làm việc…"; color: desk.muted; font.pixelSize: 13 }
        }
        Loader {
            Layout.fillWidth: true
            active: desk.phase === "startup"
            sourceComponent: DeskProgress { indeterminate: true; Accessible.name: "Đang chuẩn bị giao diện" }
        }
    }
    ColumnLayout {
        id: editorColumn
        visible: desk.phase !== "startup"
        x: 14
        y: 13
        width: parent.width - 28
        spacing: 7

        Rectangle {
            id: ambientTicker
            objectName: "ambientTicker"
            visible: desk.currentWorkspaceMode === "minimal" && Boolean(desk.liveSnapshot.oneLineAnswer || desk.liveSnapshot.answerExcerpt)
            implicitHeight: 28
            Layout.fillWidth: true
            radius: 8
            color: desk.utilitySurface
            border.width: 1
            border.color: desk.selectedEdge
            RowLayout {
                anchors.fill: parent
                anchors.margins: 4
                spacing: 6
                Rectangle {
                    implicitWidth: 6
                    implicitHeight: 6
                    radius: 3
                    color: desk.accent
                }
                Label {
                    text: "1 câu"
                    font.pixelSize: 11
                    font.weight: Font.Medium
                    color: desk.accent
                }
                Label {
                    Layout.fillWidth: true
                    text: (desk.liveSnapshot.oneLineAnswer || desk.liveSnapshot.answerExcerpt) || ""
                    font.pixelSize: 12
                    color: desk.ink
                    elide: Text.ElideRight
                }
                QuietButton {
                    text: "Mở rộng"
                    font.pixelSize: 11
                    topPadding: 2
                    bottomPadding: 2
                    leftPadding: 4
                    rightPadding: 4
                    onClicked: desk.liveController.setWorkspaceMode("single")
                }
            }
        }

        // One document control in both folded and expanded modes.
        Rectangle {
            id: contextChip
            objectName: "contextChip"
            visible: Boolean(desk.liveSnapshot.activeContext)
            implicitHeight: 28
            implicitWidth: Math.min(chipRow.implicitWidth + 8, editorColumn.width)
            Layout.maximumWidth: editorColumn.width
            radius: 8
            color: desk.utilitySurface
            border.width: 1
            border.color: desk.edge
            RowLayout {
                id: chipRow
                anchors.fill: parent
                anchors.margins: 3
                spacing: 2
                QuietButton {
                    id: documentButton
                    objectName: "documentMenu"
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    text: desk.liveSnapshot.activeContext ? desk.liveSnapshot.activeContext.title : ""
                    iconName: desk.liveSnapshot.fileName ? "pdf" : "file"
                    iconColor: desk.liveSnapshot.fileName ? desk.pdfInk : "transparent"
                    trailingIconName: ""
                    iconSize: 14
                    trailingIconSize: 0
                    elideText: true
                    font.pixelSize: 12
                    topPadding: 2
                    bottomPadding: 2
                    leftPadding: 4
                    rightPadding: 4
                    Accessible.name: "Tài liệu đang chọn: " + text + ", mở trang đang đọc"
                    enabled: Boolean(desk.liveSnapshot.fileName)
                    onClicked: { if (desk.liveController) desk.liveController.showCurrentPdfPage() }
                    ToolTip.visible: hovered
                    ToolTip.text: desk.liveSnapshot.activeContext ? desk.liveSnapshot.activeContext.title : ""
                }
                IconButton {
                    objectName: "openPdfSearch"
                    visible: Boolean(desk.liveSnapshot.fileName)
                    glyph: "search"
                    iconSize: 13
                    implicitWidth: 22
                    implicitHeight: 22
                    padding: 4
                    Accessible.name: "Tìm từ khóa trong PDF đang chọn"
                    onClicked: desk.openPdfSearch()
                    ToolTip.visible: hovered
                    ToolTip.text: "Tìm chữ trong PDF (⌘F)"
                }
                IconButton {
                    objectName: "clearContext"
                    glyph: "close"
                    iconSize: 12
                    implicitWidth: 22
                    implicitHeight: 22
                    padding: 5
                    Accessible.name: "Bỏ chọn tài liệu đính kèm"
                    onClicked: { if (desk.liveController) desk.liveController.clearActiveContext() }
                }
            }
        }

        // Ambient CoT inquiry prompts (clean, soft, no boxes, no emojis)
        RowLayout {
            id: ambientPromptsRow
            objectName: "ambientPromptsRow"
            visible: desk.liveMode && Boolean(desk.liveSnapshot.fileName) && !desk.liveSnapshot.busy && Boolean(desk.liveSnapshot.quickPrompts && desk.liveSnapshot.quickPrompts.length > 0)
            Layout.fillWidth: true
            Layout.maximumWidth: editorColumn.width
            implicitHeight: 20
            spacing: 6
            clip: true

            Label {
                text: "Gợi ý hỏi:"
                font.pixelSize: 12
                color: desk.muted
                opacity: 0.8
            }

            Repeater {
                model: desk.liveSnapshot.quickPrompts || []
                RowLayout {
                    spacing: 6
                    opacity: (x + width) <= (ambientPromptsRow.width - 24) ? 1.0 : 0.0
                    Behavior on opacity { NumberAnimation { duration: 120 } }
                    Label {
                        text: modelData.label || ""
                        font.pixelSize: 12
                        color: promptHover.hovered ? desk.accent : desk.muted
                        font.underline: promptHover.hovered
                        HoverHandler { id: promptHover }
                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                editor.text = (modelData.text || "")
                                editor.forceActiveFocus()
                            }
                        }
                    }
                    Label {
                        visible: index < (desk.liveSnapshot.quickPrompts.length - 1)
                        text: "·"
                        font.pixelSize: 12
                        color: desk.muted
                        opacity: 0.5
                    }
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.maximumWidth: editorColumn.width
            spacing: 8
            clip: true
            ScrollView {
                Layout.fillWidth: true
                Layout.alignment: Qt.AlignVCenter
                Layout.preferredHeight: Math.min(contextChip.visible ? 56 : 78, Math.max(30, editor.contentHeight + 4))
                contentWidth: availableWidth
                clip: true
            TextArea {
                id: editor
                objectName: "draftEditor"
                Accessible.name: "Nhập yêu cầu"
                Keys.priority: Keys.BeforeItem
                KeyNavigation.priority: KeyNavigation.BeforeItem
                KeyNavigation.tab: sendControl
                padding: 0
                topPadding: 4
                font.pixelSize: 14
                color: desk.ink
                selectionColor: desk.accent
                selectedTextColor: desk.accentText
                placeholderTextColor: desk.muted
                placeholderText: desk.liveMode ? (
                    desk.liveSnapshot.view === "apps" ? "Tìm ứng dụng…"
                    : desk.liveSnapshot.view === "reading" ? "Bản nháp của phiên xem · chưa nối soạn luận…"
                    : (desk.liveSnapshot.fileName ? "Hỏi tiếp về tài liệu này…" : "Tìm tệp, mở app hoặc hỏi Chuột…")
                ) : desk.phase === "idle" ? "Chuột nghe đây. Bạn cần gì?" : "Hỏi tiếp hoặc sửa điều gì đó…"
                wrapMode: TextEdit.Wrap
                selectByMouse: true
                background: null
                onTextChanged: {
                    if (desk.liveMode) {
                        if (desk.liveSnapshot.view === "apps") {
                            desk.selectedAppGridIndex = 0
                        } else {
                            desk.selectedFinderIndex = -1
                        }
                        if (desk.liveSnapshot.view === "apps" || !desk.isAppsCommand(text)) {
                            desk.liveController.onComposerTextChanged(text)
                        }
                    }
                }
                Keys.onDownPressed: event => {
                    if (desk.liveMode && desk.liveSnapshot.view === "apps") {
                        var total = desk.filteredApps.length
                        if (total > 0) {
                            event.accepted = true
                            var cols = desk.gridColumns
                            desk.selectedAppGridIndex = Math.min(total - 1, desk.selectedAppGridIndex + cols)
                            return
                        }
                    }
                    if (desk.liveMode && desk.liveSnapshot.view === "finder") {
                        var hits = desk.visibleFinderHits
                        if (hits.length > 0) {
                            event.accepted = true
                            if (desk.selectedFinderIndex < hits.length - 1) {
                                desk.selectedFinderIndex++
                            } else {
                                desk.selectedFinderIndex = 0
                            }
                            return
                        }
                    }
                    event.accepted = false
                }
                Keys.onUpPressed: event => {
                    if (desk.liveMode && desk.liveSnapshot.view === "apps") {
                        var total = desk.filteredApps.length
                        if (total > 0) {
                            event.accepted = true
                            var cols = desk.gridColumns
                            desk.selectedAppGridIndex = Math.max(0, desk.selectedAppGridIndex - cols)
                            return
                        }
                    }
                    if (desk.liveMode && desk.liveSnapshot.view === "finder") {
                        var hits = desk.visibleFinderHits
                        if (hits.length > 0) {
                            event.accepted = true
                            if (desk.selectedFinderIndex > 0) {
                                desk.selectedFinderIndex--
                            } else {
                                desk.selectedFinderIndex = hits.length - 1
                            }
                            return
                        }
                    }
                    event.accepted = false
                }
                Keys.onLeftPressed: event => {
                    if (desk.liveMode && desk.liveSnapshot.view === "apps") {
                        var total = desk.filteredApps.length
                        if (total > 0) {
                            event.accepted = true
                            desk.selectedAppGridIndex = Math.max(0, desk.selectedAppGridIndex - 1)
                            return
                        }
                    }
                    event.accepted = false
                }
                Keys.onRightPressed: event => {
                    if (desk.liveMode && desk.liveSnapshot.view === "apps") {
                        var total = desk.filteredApps.length
                        if (total > 0) {
                            event.accepted = true
                            desk.selectedAppGridIndex = Math.min(total - 1, desk.selectedAppGridIndex + 1)
                            return
                        }
                    }
                    event.accepted = false
                }
                Keys.onEscapePressed: event => {
                    event.accepted = desk.handleEscape()
                }
                Keys.onTabPressed: event => {
                    if (desk.liveMode && desk.liveSnapshot.view === "finder" && desk.selectedFinderIndex >= 0 && desk.selectedFinderIndex < (desk.visibleFinderHits || []).length) {
                        event.accepted = true
                        var idx = desk.selectedFinderIndex
                        desk.selectedFinderIndex = -1
                        desk.liveController.adoptSelectedHit(idx, editor.text)
                        editor.forceActiveFocus()
                        return
                    }
                    event.accepted = false
                }
                Keys.onReturnPressed: event => desk.handleComposerReturn(event)
                Keys.onEnterPressed: event => desk.handleComposerReturn(event)
            }
            }
            QuietButton {
                id: sendControl
                objectName: "sendButton"
                enabled: !desk.hasReadingPreview
                text: ""
                iconName: desk.phase === "receiving" || (desk.liveMode && desk.liveSnapshot.busy) ? "stop" : (desk.liveMode && desk.liveSnapshot.view === "apps" ? "enter" : "arrow-up")
                iconSize: 16
                leftPadding: 0
                rightPadding: 0
                topPadding: 0
                bottomPadding: 0
                Accessible.name: desk.liveMode ? (desk.liveSnapshot.busy ? "Dừng yêu cầu" : (desk.liveSnapshot.view === "apps" ? "Mở ứng dụng đã chọn" : "Gửi câu hỏi cho Chuột")) : desk.phase === "receiving" ? "Dừng yêu cầu minh họa" : "Gửi yêu cầu minh họa"
                primary: true
                implicitWidth: 32
                implicitHeight: 32
                Layout.preferredWidth: 32
                Layout.preferredHeight: 32
                Layout.alignment: Qt.AlignVCenter
                font.pixelSize: 18
                onClicked: {
                    if (desk.phase === "receiving" || (desk.liveMode && desk.liveSnapshot.busy)) {
                        desk.stopRequest()
                    } else if (desk.liveMode && desk.liveSnapshot.view === "apps") {
                        if (desk.filteredApps.length > 0 && desk.selectedAppGridIndex >= 0 && desk.selectedAppGridIndex < desk.filteredApps.length) {
                            var app = desk.filteredApps[desk.selectedAppGridIndex]
                            desk.liveController.launchApplication(app.path)
                            var restored = desk.liveController.closeAppsView()
                            editor.text = restored
                        }
                    } else {
                        desk.submitDraft()
                    }
                }
            }
        }
        RowLayout {
            id: suggestionChipsRow
            objectName: "suggestionChipsRow"
            visible: desk.liveMode && editor.text.length === 0 && !desk.liveSnapshot.busy && desk.liveSnapshot.view === "none" && !desk.expanded && !desk.liveSnapshot.fileName
            Layout.fillWidth: true
            spacing: 6
            Chip {
                label: "Tìm một tệp"
                onClicked: { editor.text = "Tìm một tệp"; editor.forceActiveFocus() }
            }
            Chip {
                label: "Hỏi về tài liệu đang mở"
                onClicked: { editor.text = "Hỏi về tài liệu đang mở"; editor.forceActiveFocus() }
            }
            Chip {
                label: "Lịch hôm nay"
                onClicked: { editor.text = "Lịch hôm nay"; editor.forceActiveFocus() }
            }
        }
        RowLayout {
            Layout.fillWidth: true
            Label { visible: desk.phase === "idle" && !desk.liveMode; text: "↵ Gửi · ⇧↵ Xuống dòng"; color: desk.muted; font.pixelSize: 12 }
            Label {
                objectName: "uiBuildLabel"
                visible: desk.liveMode
                text: desk.uiBuildLabel
                textFormat: Text.PlainText
                color: desk.muted
                font.pixelSize: 11
                opacity: 0.65
                topPadding: 4
                bottomPadding: 4
                leftPadding: 0
                rightPadding: 2
                Accessible.name: "Bản build giao diện " + desk.uiBuildLabel
                ToolTip.visible: dragHandle.containsMouse
                ToolTip.text: "Bản build giao diện · Kéo để di chuyển cửa sổ"
                MouseArea { id: dragHandle; objectName: "dragHandle"; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.OpenHandCursor; onPressed: desk.moveRequested() }
            }
            RowLayout {
                visible: desk.liveMode
                Layout.fillWidth: true
                spacing: 5
                Label {
                    text: "·"
                    color: desk.muted
                    opacity: 0.65
                    font.pixelSize: 12
                }
                Rectangle {
                    visible: !containsDrag && !desk.liveSnapshot.busy && desk.liveSnapshot.view === "none" && !desk.liveSnapshot.fileName
                    implicitWidth: 6
                    implicitHeight: 6
                    radius: 3
                    color: desk.accent
                    opacity: 0.75
                }
                RowLayout {
                    id: composerKeyHintRow
                    objectName: "composerKeyHintRow"
                    visible: Boolean(desk.composerKeyHints && desk.composerKeyHints.length > 0) && !desk.liveSnapshot.indexStatus && !desk.liveSnapshot.finderFeedback && !containsDrag
                    spacing: 6
                    Repeater {
                        model: desk.composerKeyHints || []
                        RowLayout {
                            spacing: 3
                            KeycapBadge {
                                keyText: modelData.key || ""
                            }
                            Label {
                                text: modelData.label || ""
                                color: desk.muted
                                font.pixelSize: 11
                            }
                        }
                    }
                }
                Label {
                    objectName: "composerDropStatus"
                    Layout.fillWidth: true
                    text: containsDrag ? "Thả PDF vào bàn Chuột"
                        : desk.liveSnapshot.finderFeedback ? desk.liveSnapshot.finderFeedback
                        : desk.liveSnapshot.indexStatus ? desk.liveSnapshot.indexStatus
                        : (desk.composerKeyHints && desk.composerKeyHints.length > 0) ? ""
                        : (desk.liveSnapshot.busy && !desk.expanded) ? desk.liveSnapshot.status
                        : desk.liveSnapshot.view === "reading" ? "Bàn xem · đang chuẩn bị dữ liệu"
                        : desk.liveSnapshot.view === "finder" ? "↑↓ chọn · ↵ mở · Tab đưa vào bàn & hỏi Chuột · Esc đóng"
                        : desk.liveSnapshot.view === "answer" ? (desk.hasLatentFinderHits ? "↵ hỏi tiếp Chuột · Bấm ngăn trên mở tệp" : "↵ hỏi tiếp Chuột")
                        : "Chuột sẵn sàng"
                    elide: Text.ElideRight
                    color: containsDrag ? desk.accent : desk.muted
                    font.weight: containsDrag ? Font.Medium : Font.Normal
                    font.pixelSize: 12
                }
            }
            QuietButton {
                objectName: "choosePdf"
                visible: desk.liveMode
                text: ""
                iconName: "paperclip"
                iconSize: 16
                leftPadding: 0
                rightPadding: 0
                topPadding: 0
                bottomPadding: 0
                implicitWidth: 30
                implicitHeight: 30
                Accessible.name: desk.liveSnapshot.view === "reading" ? "Mở hồ sơ lá số JSON" : (desk.liveSnapshot.fileName ? "Đổi PDF" : "Chọn PDF")
                ToolTip.visible: hovered
                ToolTip.text: desk.liveSnapshot.view === "reading" ? "Mở hoặc thả hồ sơ lá số JSON" : (desk.liveSnapshot.fileName ? "Đổi hoặc kéo thả PDF khác" : "Chọn hoặc kéo thả PDF")
                onClicked: { if (desk.liveSnapshot.view === "reading") desk.openReadingProfileDialog(); else desk.openPdfDialog() }
            }
            QuietButton {
                objectName: "closeDesk"
                visible: desk.liveMode
                text: ""
                iconName: "close"
                iconSize: 16
                leftPadding: 0
                rightPadding: 0
                topPadding: 0
                bottomPadding: 0
                implicitWidth: 30
                implicitHeight: 30
                Accessible.name: "Đóng cửa sổ RAT"
                onClicked: desk.closeRequested()
            }
            Label { visible: desk.phase === "receiving"; text: "Đang nhận yêu cầu…"; color: desk.muted; font.pixelSize: 12 }
            QuietButton {
                visible: !desk.liveMode && desk.hasWorkbench
                text: "Quy chế học vụ"
                onClicked: { desk.openWorkbench(); desk.sourceOpen = true }
            }
            Item { visible: !desk.liveMode; Layout.fillWidth: true }
        }
        Label {
            objectName: "applicationLaunchFeedback"
            visible: desk.liveMode && Boolean(desk.liveSnapshot.launchFeedback)
            text: desk.liveSnapshot.launchFeedback || ""
            textFormat: Text.PlainText
            color: desk.liveSnapshot.launchFeedbackError ? desk.pdfInk : desk.accent
            font.pixelSize: 12
            wrapMode: Text.Wrap
            Layout.fillWidth: true
            Accessible.name: text
        }
        Label {
            objectName: "finderSearchFeedback"
            visible: desk.liveMode && Boolean(desk.liveSnapshot.finderFeedback)
            text: desk.liveSnapshot.finderFeedback || ""
            textFormat: Text.PlainText
            color: desk.muted
            font.pixelSize: 12
            wrapMode: Text.Wrap
            Layout.fillWidth: true
            Accessible.name: text
        }
        Loader {
            Layout.fillWidth: true
            active: desk.phase === "receiving" || (desk.liveMode && desk.liveSnapshot.busy && !desk.expanded)
            visible: active
            sourceComponent: DeskProgress { indeterminate: true; Accessible.name: "Đang nhận yêu cầu" }
        }
    }

    function submitDraft() {
        if (desk.liveMode) {
            if (!desk.liveSnapshot.busy) {
                if (editor.text.trim() === "" && desk.liveSnapshot.view === "finder" && (desk.visibleFinderHits || []).length > 0) {
                    var hitIdx = desk.selectedFinderIndex >= 0 ? desk.selectedFinderIndex : 0
                    if (hitIdx < desk.visibleFinderHits.length) {
                        var hit = desk.visibleFinderHits[hitIdx] || ({})
                        desk.selectedFinderIndex = -1
                        var isPdf = Boolean(hit.is_pdf)
                        desk.liveController.openSelectedHit(hitIdx)
                        if (isPdf) {
                            editor.text = ""
                        }
                        editor.forceActiveFocus()
                        return
                    }
                }
                if (editor.text.trim().toLowerCase() === "/reading") {
                    desk.liveController.openReadingDesk()
                    editor.text = ""
                    editor.forceActiveFocus()
                    return
                }
                if (desk.isAppsCommand(editor.text)) {
                    desk.liveController.openAppsView("")
                    if (desk.liveController.snapshot.view === "apps") editor.text = ""
                    editor.forceActiveFocus()
                    return
                }
                desk.liveController.submitQuery(editor.text)
                if (desk.liveController.snapshot.busy) editor.text = ""
                editor.forceActiveFocus()
            }
            return
        }
        if (desk.phase === "receiving" || editor.text.trim().length === 0) return
        desk.phase = "receiving"
        desk.expanded = false
        desk.unread = false
        desk.sourceOpen = false
        desk.logOpen = false
    }

    function handleComposerReturn(event) {
        if (editor.inputMethodComposing) {
            event.accepted = false
            return
        }
        const hasCmdOrCtrl = Boolean((event.modifiers & Qt.MetaModifier) || (event.modifiers & Qt.ControlModifier))
        const hasShift = Boolean(event.modifiers & Qt.ShiftModifier)

        if (desk.liveMode && desk.liveSnapshot.view === "apps") {
            event.accepted = true
            if (desk.filteredApps.length > 0 && desk.selectedAppGridIndex >= 0 && desk.selectedAppGridIndex < desk.filteredApps.length) {
                var app = desk.filteredApps[desk.selectedAppGridIndex]
                if (hasCmdOrCtrl) {
                    desk.liveController.revealInFinder(app.path)
                } else {
                    desk.liveController.launchApplication(app.path)
                    var restored = desk.liveController.closeAppsView()
                    editor.text = restored
                }
            }
            return
        }

        if (desk.liveMode && desk.liveSnapshot.view === "finder" && (desk.visibleFinderHits || []).length > 0) {
            var hitIdx = desk.selectedFinderIndex >= 0 ? desk.selectedFinderIndex : 0
            if (hitIdx < desk.visibleFinderHits.length && (editor.text.trim() === "" || desk.selectedFinderIndex >= 0)) {
                var hit = desk.visibleFinderHits[hitIdx] || ({})
                if (hasCmdOrCtrl) {
                    event.accepted = true
                    desk.liveController.revealSelectedInFinder(hitIdx)
                    return
                }
                if (!hasShift) {
                    event.accepted = true
                    desk.selectedFinderIndex = -1
                    var isPdf = Boolean(hit.is_pdf)
                    desk.liveController.openSelectedHit(hitIdx)
                    if (isPdf) {
                        editor.text = ""
                        editor.forceActiveFocus()
                    }
                    return
                }
                if (!hit.is_pdf) {
                    event.accepted = true
                    var fileIdx = hitIdx
                    desk.selectedFinderIndex = -1
                    desk.liveController.askAboutSelectedHit(fileIdx, editor.text)
                    if (desk.liveController.snapshot.busy) editor.text = ""
                    return
                }
            }
        }

        if (!hasShift) {
            event.accepted = true
            submitDraft()
        } else {
            event.accepted = false
        }
    }

    function stopRequest() {
        if (desk.liveMode) { desk.liveController.cancel(); editor.forceActiveFocus(); return }
        if (desk.phase === "receiving") {
            desk.phase = "idle"
            desk.expanded = false
            editor.forceActiveFocus()
        }
    }
}