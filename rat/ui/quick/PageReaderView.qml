import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ColumnLayout {
    id: pageReaderView
    property alias matchedExcerptText: matchedExcerptText
    property alias pageText: pageText
    visible: desk.liveMode && desk.liveSnapshot.view === "page"
    Layout.fillWidth: true
    spacing: 0

                    Rectangle {
                        id: matchedExcerptWrapper
                        objectName: "matchedExcerptWrapper"
                        visible: desk.liveSnapshot.view === "page" && desk.readerDisplayMode === "matched"
                        Layout.fillWidth: true
                        implicitHeight: matchedExcerptLayout.implicitHeight + 24
                        radius: 8
                        color: desk.sheetPaperColor
                        border.width: 1
                        border.color: desk.selectedEdge
                        clip: true

                        ColumnLayout {
                            id: matchedExcerptLayout
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.top: parent.top
                            anchors.margins: 12
                            spacing: 8

                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 3

                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 6
                                    Rectangle {
                                        implicitWidth: 6
                                        implicitHeight: 6
                                        radius: 3
                                        color: desk.accent
                                    }
                                    Label {
                                        Layout.fillWidth: true
                                        text: desk.liveSnapshot.hasMatchedSnippet
                                            ? ("Đoạn khớp với từ khóa \"" + (desk.liveSnapshot.matchedQuery || desk.liveSnapshot.searchQuery || "") + "\"")
                                            : "Đoạn nguồn"
                                        font.pixelSize: 12
                                        font.weight: Font.Medium
                                        color: desk.accent
                                        wrapMode: Text.Wrap
                                    }
                                }

                                Label {
                                    visible: Boolean(desk.liveSnapshot.hasMatchedSnippet && desk.liveSnapshot.matchedSnippetTruncated)
                                    Layout.leftMargin: 12
                                    text: "Đoạn trích đã được rút gọn"
                                    font.pixelSize: 11
                                    color: desk.muted
                                }
                            }

                            TextArea {
                                id: matchedExcerptText
                                objectName: "matchedExcerptText"
                                visible: Boolean(desk.liveSnapshot.hasMatchedSnippet)
                                Layout.fillWidth: true
                                Layout.preferredHeight: contentHeight + 6
                                readOnly: true
                                selectByMouse: true
                                persistentSelection: true
                                wrapMode: TextEdit.Wrap
                                textFormat: TextEdit.RichText
                                property string snippetKey: ""
                                Component.onCompleted: {
                                    snippetKey = desk.liveSnapshot.matchedSnippetHtml || ""
                                    text = snippetKey
                                }
                                Connections {
                                    target: desk
                                    function onLiveSnapshotChanged() {
                                        var nextSnippet = desk.liveSnapshot.matchedSnippetHtml || ""
                                        if (matchedExcerptText.snippetKey !== nextSnippet) {
                                            matchedExcerptText.snippetKey = nextSnippet
                                            matchedExcerptText.text = nextSnippet
                                        }
                                    }
                                }
                                color: desk.ink
                                font.pixelSize: 13
                                background: null
                                padding: 0
                                Accessible.name: "Đoạn khớp từ kết quả tìm kiếm"
                            }

                            Label {
                                visible: Boolean(desk.liveSnapshot.hasMatchedSnippet)
                                text: "Bôi chọn phần cần lấy hoặc bấm Chép đoạn để sao chép cả đoạn nguồn."
                                font.pixelSize: 12
                                color: desk.muted
                                wrapMode: Text.Wrap
                                Layout.fillWidth: true
                            }

                            ColumnLayout {
                                visible: !desk.liveSnapshot.hasMatchedSnippet
                                Layout.fillWidth: true
                                spacing: 8

                                Label {
                                    text: "Chưa có đoạn trích cho trang này."
                                    font.pixelSize: 12
                                    color: desk.muted
                                }
                                QuietButton {
                                    objectName: "openOriginalFallback"
                                    text: "Mở PDF gốc"
                                    iconName: "external"
                                    font.pixelSize: 12
                                    leftPadding: 6
                                    rightPadding: 8
                                    Accessible.name: "Mở PDF gốc bằng ứng dụng ngoài"
                                    onClicked: { if (desk.liveController) desk.liveController.openOriginal() }
                                }
                            }
                        }
                    }
                    Rectangle {
                        id: visualPageWrapper
                        objectName: "visualPageWrapper"
                        visible: desk.liveSnapshot.view === "page" && desk.readerDisplayMode === "visual"
                        Layout.fillWidth: true
                        implicitHeight: visualPdfPage.status === Image.Ready && visualPdfPage.implicitWidth > 0
                            ? Math.round(width * (visualPdfPage.implicitHeight / Math.max(1, visualPdfPage.implicitWidth))) + 8
                            : 320
                        radius: 8
                        color: desk.sheetPaperColor
                        border.width: 1
                        border.color: desk.edge
                        clip: true

                        Image {
                            id: visualPdfPage
                            objectName: "visualPdfPage"
                            anchors.fill: parent
                            anchors.margins: 4
                            fillMode: Image.PreserveAspectFit
                            smooth: true
                            mipmap: true
                            source: (desk.liveMode && desk.liveSnapshot.view === "page" && desk.readerDisplayMode === "visual" && desk.liveSnapshot.pageNumber > 0)
                                ? desk.liveController.fullPageSnapshot(desk.liveSnapshot.activeContext ? desk.liveSnapshot.activeContext.path : "", desk.liveSnapshot.pageNumber, 1200)
                                : ""
                        }

                        Label {
                            anchors.centerIn: parent
                            visible: visualPdfPage.status !== Image.Ready
                            text: visualPdfPage.status === Image.Loading ? "Đang dựng trang PDF…" : (desk.liveSnapshot.errorCode ? desk.liveSnapshot.errorText : "Đang tải trang…")
                            color: desk.muted
                            font.pixelSize: 12
                        }
                    }

                    TextArea {
                        id: pageText
                        objectName: "pageText"
                        visible: desk.liveSnapshot.view === "page" && desk.readerDisplayMode === "text"
                        Layout.fillWidth: true
                        Layout.preferredHeight: contentHeight + 14
                        bottomPadding: 14
                        text: desk.liveSnapshot.pageReadingText || desk.liveSnapshot.pageText || ""
                        textFormat: TextEdit.PlainText
                        wrapMode: TextEdit.Wrap
                        readOnly: true
                        selectByMouse: true
                        persistentSelection: true
                        color: desk.ink
                        selectionColor: desk.accent
                        selectedTextColor: desk.accentText
                        font.pixelSize: 14
                        padding: 0
                        background: null
                        Accessible.name: "Văn bản trích xuất từ trang PDF đang đọc"
                    }

}
