import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

        Rectangle {
            id: resultPaper
            objectName: "resultPaper"
            property alias paperMove: paperMove
            property alias resultScroll: resultScroll
            property alias paperHeader: paperHeader
            property alias answerView: answerView
            property alias pageReaderView: pageReaderView
            property alias finderResults: finderResults
            property alias settingsView: settingsView
            property alias appsResultsLoader: appsResultsLoader
            visible: desk.expanded && desk.hasWorkbench
            x: (desk.isSideBySidePdfActive ? (sidePdfPane.width + 12) : (composer.x + unit.paperOffset)) + desk.paperDragX
            y: (composer.y + 22 - height) + desk.paperDragY
            width: desk.isSideBySidePdfActive ? (unit.width - (sidePdfPane.width + 12)) : ((composer.x + composer.width) - (composer.x + unit.paperOffset))
            height: desk.liveMode ? Math.min(resultContents.implicitHeight + 80, desk.maxPaperHeight) : Math.min(resultContents.implicitHeight + 38, composer.y + 22 - 70)
            radius: 16
            color: desk.paperColor
            border.color: desk.edge
            z: 1
            Behavior on y {
                enabled: desk.readyForMotion && !desk.reduceMotion
                NumberAnimation { id: paperMove; duration: 160; easing.type: Easing.OutCubic }
            }
            MouseArea {
                id: paperDragArea
                anchors.fill: parent
                z: 0
                property real pressX: 0
                property real pressY: 0
                property bool dragging: false
                onPressed: (mouse) => {
                    pressX = mouse.x
                    pressY = mouse.y
                    dragging = false
                }
                onPositionChanged: (mouse) => {
                    var dx = mouse.x - pressX
                    var dy = mouse.y - pressY
                    if (!dragging && (Math.abs(dx) > 6 || Math.abs(dy) > 6)) {
                        dragging = true
                    }
                    if (dragging) {
                        desk.paperDragTargetX = dx
                        desk.paperDragTargetY = dy
                    }
                }
                onReleased: (mouse) => {
                    if (dragging) {
                        dragging = false
                        if (Math.abs(desk.paperDragTargetX) > 180 || desk.paperDragTargetY < -120) {
                            desk.dismissPaperWithFlick(desk.paperDragTargetX * 1.5, desk.paperDragTargetY * 1.5)
                        } else {
                            desk.paperDragTargetX = 0.0
                            desk.paperDragTargetY = 0.0
                        }
                    }
                }
            }
            PaperHeader { id: paperHeader }
            Rectangle {
                visible: desk.liveMode
                x: 22
                y: 42
                width: parent.width - 44
                height: 1
                color: desk.edge
                opacity: 0.75
            }
            Rectangle {
                visible: desk.liveMode && desk.liveSnapshot.view !== "finder" && resultScroll.contentHeight > resultScroll.height + 4 && (!resultScroll.contentItem || resultScroll.contentItem.contentY + resultScroll.height < resultScroll.contentHeight - 6)
                x: 22
                y: resultScroll.y + resultScroll.height - 22
                width: parent.width - 52
                height: 22
                z: 4
                enabled: false
                gradient: Gradient {
                    GradientStop { position: 0.0; color: "transparent" }
                    GradientStop { position: 0.75; color: Qt.rgba(desk.paperColor.r, desk.paperColor.g, desk.paperColor.b, 0.88) }
                    GradientStop { position: 1.0; color: desk.paperColor }
                }
            }
            ScrollView {
                id: resultScroll
                objectName: "resultScroll"
                x: 22
                y: desk.liveMode ? ((desk.inlineFindOpen && desk.expanded) ? 86 : 46) : 16
                width: parent.width - 44
                height: Math.max(0, parent.height - (desk.liveMode ? ((desk.inlineFindOpen && desk.expanded) ? 120 : 80) : 38))
                contentWidth: width
                contentHeight: resultContents.implicitHeight
                clip: true
                ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
                ScrollBar.vertical: ScrollBar {
                    id: resultVerticalScroll
                    objectName: "resultVerticalScroll"
                    parent: resultScroll
                    x: resultScroll.width - width
                    y: 2
                    height: resultScroll.availableHeight - 4
                    width: 6
                    policy: (resultScroll.contentHeight > resultScroll.height + 4 && desk.liveSnapshot.view !== "finder") ? ScrollBar.AlwaysOn : ScrollBar.AlwaysOff
                    contentItem: Rectangle {
                        implicitWidth: 6
                        radius: 3
                        color: resultVerticalScroll.pressed ? desk.accent : (resultVerticalScroll.hovered ? desk.deskTheme.scrollThumbHover : desk.deskTheme.scrollThumb)
                        opacity: 0.92
                    }
                    background: Rectangle {
                        implicitWidth: 6
                        radius: 3
                        color: desk.darkMode ? Qt.rgba(1, 1, 1, 0.05) : Qt.rgba(0, 0, 0, 0.04)
                        visible: resultVerticalScroll.hovered || resultVerticalScroll.pressed
                    }
                }
            ColumnLayout {
                id: resultContents
                width: resultScroll.width - 12
                spacing: 6
                PreviewWorkbenchContents { id: previewContents }
                RowLayout {
                    visible: desk.liveMode && desk.liveSnapshot.view === "page"
                    Layout.fillWidth: true
                    spacing: 8

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 1

                        Label {
                            id: pageSourceTitle
                            objectName: "pageSourceTitle"
                            Layout.fillWidth: true
                            text: (desk.liveSnapshot.sourceKind === "search_hit" || Boolean(desk.liveSnapshot.hasMatchedSnippet))
                                ? ("Nguồn · Trang " + (desk.liveSnapshot.pageNumber || 1))
                                : ("Nguồn · Trang " + (desk.liveSnapshot.pageNumber || 1) + "/" + (desk.liveSnapshot.pageCount || 1))
                            textFormat: Text.PlainText
                            color: desk.ink
                            font.pixelSize: 13
                            font.weight: Font.DemiBold
                        }

                        Label {
                            id: pageMetaLabel
                            objectName: "pageMetadataLabel"
                            Layout.fillWidth: true
                            text: desk.liveSnapshot.fileName || ""
                            textFormat: Text.PlainText
                            elide: Text.ElideMiddle
                            color: desk.muted
                            font.pixelSize: 12
                            ToolTip.visible: pageMetaMouse.containsMouse
                            ToolTip.text: desk.liveSnapshot.fileName || ""
                            MouseArea {
                                id: pageMetaMouse
                                anchors.fill: parent
                                hoverEnabled: true
                            }
                        }
                    }

                    QuietButton {
                        id: openOriginalExternal
                        objectName: "openOriginalExternal"
                        text: resultPaper.width < 420 ? "PDF gốc" : "Mở PDF gốc"
                        iconName: "external"
                        font.pixelSize: 12
                        leftPadding: 6
                        rightPadding: 8
                        Accessible.name: "Mở PDF gốc bằng ứng dụng ngoài"
                        onClicked: { if (desk.liveController) desk.liveController.openOriginal() }
                    }
                }
                Label {
                    visible: desk.liveMode && (desk.liveSnapshot.view !== "answer" && desk.liveSnapshot.view !== "page" && desk.liveSnapshot.view !== "reading")
                    Layout.fillWidth: true
                    text: desk.liveSnapshot.view === "finder" ? (desk.liveSnapshot.title || "Gợi ý tìm kiếm")
                        : (desk.liveSnapshot.view === "apps" ? ("Ứng dụng (" + desk.filteredApps.length + ")")
                        : (desk.liveSnapshot.title || "Đang mở bàn làm việc…"))
                    textFormat: Text.PlainText
                    color: desk.ink
                    font.pixelSize: 16
                    font.weight: Font.Medium
                    wrapMode: Text.Wrap
                }
                ReadingDesk {
                    objectName: "readingWorkbench"
                    host: desk
                    visible: desk.liveMode && desk.liveSnapshot.view === "reading"
                    Layout.fillWidth: true
                }
                ColumnLayout {
                    visible: desk.liveMode
                    Layout.fillWidth: true
                    spacing: desk.emptyCancelledAnswer ? 8 : 12
                    AnswerView { id: answerView }
                    Label {
                        visible: desk.liveSnapshot.view !== "answer" && desk.liveSnapshot.view !== "busy" && desk.liveSnapshot.view !== "finder" && desk.liveSnapshot.view !== "apps" && desk.liveSnapshot.view !== "reading" && (desk.liveSnapshot.view !== "page" || desk.readerDisplayMode === "text" || desk.liveSnapshot.pageTruncated)
                        Layout.fillWidth: true
                        text: desk.liveSnapshot.view === "page" ? ((desk.liveSnapshot.pageTruncated ? "Đã cắt ở 8.000 ký tự. " : "") + (desk.readerDisplayMode === "text" ? "Bôi chọn đoạn cần lấy, rồi chép trích dẫn." : "")) : (desk.liveSnapshot.view === "error" ? desk.liveSnapshot.errorText : desk.liveSnapshot.status) || ""
                        textFormat: Text.PlainText
                        wrapMode: Text.Wrap
                        color: desk.muted
                        font.pixelSize: 12
                    }
                    RowLayout {
                        visible: desk.liveSnapshot.view === "error"
                        Layout.fillWidth: true
                        spacing: 8
                        QuietButton {
                            objectName: "errorActionButton"
                            primary: true
                            text: (desk.liveSnapshot.errorText || "").indexOf("PDF") !== -1 ? "Chọn tệp PDF" : "Thử lại"
                            iconName: (desk.liveSnapshot.errorText || "").indexOf("PDF") !== -1 ? "file" : "sparkle"
                            onClicked: {
                                if ((desk.liveSnapshot.errorText || "").indexOf("PDF") !== -1) {
                                    desk.openPdfDialog()
                                } else {
                                    desk.editor.forceActiveFocus()
                                }
                            }
                        }
                    }
                    RowLayout {
                        visible: desk.liveMode && desk.liveSnapshot.busy
                        Layout.fillWidth: true
                        spacing: 8
                        DeskProgress {
                            Layout.fillWidth: true
                            indeterminate: true
                            Accessible.name: "Đang xử lý yêu cầu"
                        }
                        QuietButton {
                            objectName: "stopBusyButton"
                            text: "Dừng"
                            iconName: "stop"
                            iconSize: 11
                            font.pixelSize: 11
                            topPadding: 3
                            bottomPadding: 3
                            leftPadding: 6
                            rightPadding: 6
                            Accessible.name: "Dừng yêu cầu đang xử lý"
                            onClicked: desk.stopRequest()
                        }
                    }
                    SearchResultsView { id: searchResultsView }
                    PageReaderView { id: pageReaderView }
                    FinderResultsView {
                        id: finderResults
                        Layout.fillWidth: true
                    }
                    SettingsView {
                        id: settingsView
                        Layout.fillWidth: true
                    }

                    // APPS CATALOG GRID VIEW (loaded lazily on demand)
                    Loader {
                        id: appsResultsLoader
                        objectName: "appsResultsLoader"
                        active: desk.liveMode && desk.liveSnapshot.view === "apps"
                        visible: active
                        Layout.fillWidth: true
                        source: "AppsCatalogView.qml"
                    }
                    RowLayout {
                        visible: desk.liveSnapshot.nextPage > 0
                        Layout.fillWidth: true
                        QuietButton { objectName: "nextBatch"; visible: desk.liveSnapshot.nextPage > 0; text: "Tìm tiếp từ trang " + desk.liveSnapshot.nextPage; onClicked: desk.liveController.nextBatch() }
                    }
                    RowLayout {
                        visible: desk.liveSnapshot.view !== "finder" && desk.liveSnapshot.view !== "apps" && desk.liveSnapshot.view !== "reading"
                        Layout.fillWidth: true
                        QuietButton {
                            objectName: "logToggle"
                            text: "Chi tiết & nhật ký"
                            iconName: desk.logOpen ? "chevron-down" : "chevron-right"
                            iconSize: 13
                            font.pixelSize: 12
                            leftPadding: 0
                            topPadding: 4
                            bottomPadding: 4
                            onClicked: desk.logOpen = !desk.logOpen
                        }
                        Item { Layout.fillWidth: true }
                    }
                    Label { visible: desk.logOpen && desk.liveSnapshot.view === "page"; text: desk.liveSnapshot.status || ""; textFormat: Text.PlainText; wrapMode: Text.Wrap; color: desk.muted; font.pixelSize: 12; Layout.fillWidth: true }
                    Repeater {
                        model: desk.logOpen && desk.liveSnapshot.view !== "reading" ? (desk.liveSnapshot.events || []) : []
                        Label { required property string modelData; text: "· " + modelData; textFormat: Text.PlainText; wrapMode: Text.Wrap; color: desk.muted; font.pixelSize: 12; Layout.fillWidth: true }
                    }
                    Item { Layout.fillWidth: true; implicitHeight: desk.liveMode ? 32 : 8 }
                }
                Rectangle { visible: !desk.liveMode; Layout.fillWidth: true; height: 1; color: desk.edge }
                RowLayout {
                    visible: !desk.liveMode
                    Layout.fillWidth: true
                    spacing: 4
                    QuietButton { text: "1 nguồn"; Accessible.name: "Mở nguồn minh họa"; onClicked: desk.sourceOpen = !desk.sourceOpen }
                    QuietButton {
                        text: desk.phase === "working" ? "3 / 4 bước" : "4 bước"
                        Accessible.name: "Luồng thao tác công khai"
                        onClicked: { if (desk.phase === "working") desk.compactTrail = !desk.compactTrail; else desk.logOpen = !desk.logOpen }
                    }
                    Item { Layout.fillWidth: true }
                    QuietButton { visible: desk.phase === "result"; text: desk.copied ? "Đã chép" : "Sao chép"; onClicked: desk.requestCopy() }
                }
            }
            }
        }
