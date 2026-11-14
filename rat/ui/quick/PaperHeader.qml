import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: liveHeader
    property real paperWidth: parent ? parent.width : 520
    property alias pagePicker: pagePicker
    visible: desk.liveMode
    anchors.left: parent ? parent.left : undefined
    anchors.right: parent ? parent.right : undefined
    anchors.leftMargin: 22
    anchors.rightMargin: 22
    y: 10
    height: 26

    QuietButton {
        id: liveFoldButton
        objectName: "liveFoldButton"
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        text: ""
        iconName: "minus"
        leftPadding: 6
        rightPadding: 6
        Accessible.name: "Thu gọn"
        ToolTip.visible: hovered
        ToolTip.text: "Thu gọn"
        onClicked: desk.foldWorkbench()
    }

    QuietButton {
        id: copyCitation
        objectName: "copyCitation"
        anchors.right: liveFoldButton.left
        anchors.rightMargin: 4
        anchors.verticalCenter: parent.verticalCenter
        visible: Boolean(desk.liveSnapshot.canCopy)
        text: desk.copied ? "Đã chép" : (desk.liveSnapshot.view === "page" ? "Chép đoạn" : (desk.liveSnapshot.view === "answer" ? (liveHeader.width < 320 ? "Chép" : "Sao chép") : (liveHeader.width < 400 ? "Chép" : "Chép trích dẫn")))
        iconName: desk.copied ? "check" : "copy"
        leftPadding: liveHeader.width < 320 ? 5 : 8
        rightPadding: liveHeader.width < 320 ? 5 : 8
        font.pixelSize: 12
        onClicked: desk.requestCopy()
    }

    RowLayout {
        id: leftHeaderControls
        anchors.left: parent.left
        anchors.right: copyCitation.visible ? copyCitation.left : liveFoldButton.left
        anchors.rightMargin: 8
        anchors.verticalCenter: parent.verticalCenter
        spacing: 4

        QuietButton {
            objectName: "backFromSettings"
            visible: desk.liveSnapshot.view === "settings"
            text: "Quay lại"
            iconName: "arrow-left"
            iconSize: 14
            leftPadding: 6
            Accessible.name: "Quay lại màn hình trước"
            onClicked: {
                if (desk.liveController) desk.liveController.closeSettings()
                if (desk.editor) desk.editor.forceActiveFocus()
            }
        }

        RowLayout {
            visible: !desk.liveSnapshot.canBack && desk.liveSnapshot.view !== "apps" && desk.liveSnapshot.view !== "finder" && desk.liveSnapshot.view !== "page" && desk.liveSnapshot.view !== "reading" && desk.liveSnapshot.view !== "settings"
            spacing: 6
            Rectangle {
                implicitWidth: 6
                implicitHeight: 6
                radius: 3
                color: desk.liveSnapshot.view === "answer" ? desk.accent : desk.selectedEdge
            }
            Label {
                id: titleLabel
                text: desk.liveSnapshot.view === "answer" ? (desk.cancelledAnswer ? "Đã dừng yêu cầu" : "Câu trả lời của Chuột")
                    : (desk.liveSnapshot.view === "busy" ? (desk.liveSnapshot.status || "Đang suy nghĩ…") : ("Trong tài liệu · " + (desk.liveSnapshot.fileName || "PDF")))
                elide: Text.ElideRight
                Layout.fillWidth: true
                Layout.maximumWidth: Math.min(215, Math.max(80, paperWidth - 150))
                font.pixelSize: 12
                font.weight: Font.Medium
                color: desk.muted
                HoverHandler { id: titleHover }
                ToolTip.visible: Boolean(titleHover.hovered && titleLabel.truncated)
                ToolTip.text: text
            }
        }
        QuietButton {
            objectName: "backToAnswer"
            visible: desk.liveSnapshot.view === "page" && Boolean(desk.liveSnapshot.canBackToAnswer)
            text: paperWidth < 400 ? "" : "Câu trả lời"
            iconName: "arrow-left"
            iconSize: 14
            leftPadding: 6
            rightPadding: paperWidth < 400 ? 6 : 9
            Accessible.name: "Quay lại câu trả lời vừa xem"
            onClicked: desk.liveController.backToAnswer()
        }
        QuietButton {
            objectName: "backToSearch"
            visible: Boolean(desk.liveSnapshot.canBack)
            text: paperWidth < 360 ? "Kết quả" : "Quay lại kết quả"
            iconName: "arrow-left"
            iconSize: 14
            leftPadding: 6
            rightPadding: 8
            Accessible.name: "Quay lại kết quả"
            onClicked: desk.liveController.backToSearch()
        }
        QuietButton {
            objectName: "backFromReading"
            visible: desk.liveSnapshot.view === "reading"
            text: "Bàn làm việc"
            iconName: "arrow-left"
            onClicked: { desk.liveController.closeReadingDesk(); if (desk.editor) desk.editor.forceActiveFocus() }
        }
        QuietButton {
            objectName: "backFromApps"
            visible: desk.liveSnapshot.view === "apps"
            text: "Bàn làm việc"
            iconName: "arrow-left"
            iconSize: 14
            leftPadding: 6
            onClicked: {
                var restored = desk.liveController.closeAppsView()
                if (desk.editor) {
                    desk.editor.text = restored
                    desk.editor.forceActiveFocus()
                }
            }
        }
        QuietButton {
            id: backFromFinderButton
            objectName: "backFromFinder"
            visible: desk.liveSnapshot.view === "finder"
            text: Boolean(desk.liveSnapshot.answerText) ? "Câu trả lời" : "Bàn làm việc"
            iconName: "arrow-left"
            iconSize: 14
            leftPadding: 6
            Accessible.name: Boolean(desk.liveSnapshot.answerText) ? "Quay lại câu trả lời và đóng gợi ý" : "Quay lại bàn làm việc và đóng gợi ý"
            onClicked: {
                desk.liveController.dismissFinder()
                if (desk.editor) desk.editor.forceActiveFocus()
            }
        }

        RowLayout {
            id: pageNavCluster
            visible: desk.liveSnapshot.view === "page" && !desk.liveSnapshot.canBack && desk.liveSnapshot.sourceKind !== "search_hit"
            spacing: 2

            IconButton {
                objectName: "prevPage"
                glyph: "chevron-left"
                iconSize: 11
                implicitWidth: 18
                implicitHeight: 20
                padding: 2
                enabled: !desk.liveSnapshot.busy && (desk.liveSnapshot.pageNumber || 1) > 1
                Accessible.name: "Trang trước"
                onClicked: { if (desk.liveController) desk.liveController.prevPage() }
                ToolTip.visible: hovered
                ToolTip.text: "Trang trước"
            }
            SpinBox {
                id: pagePicker
                objectName: "pagePicker"
                from: 1
                to: Math.max(1, desk.liveSnapshot.pageCount || 1)
                value: desk.liveSnapshot.pageNumber || 1
                editable: true
                implicitWidth: 38
                implicitHeight: 20
                font.pixelSize: 12
                Accessible.name: "Số trang PDF"
                contentItem: TextInput {
                    text: pagePicker.textFromValue(pagePicker.value, pagePicker.locale)
                    font: pagePicker.font
                    color: desk.ink
                    horizontalAlignment: Qt.AlignHCenter
                    verticalAlignment: Qt.AlignVCenter
                    readOnly: !pagePicker.editable
                    validator: pagePicker.validator
                    inputMethodHints: Qt.ImhDigitsOnly
                    onAccepted: {
                        if (desk.liveController && !desk.liveSnapshot.busy) {
                            desk.liveController.readPage(pagePicker.value)
                        }
                    }
                }
                up.indicator: Item {}
                down.indicator: Item {}
                background: Rectangle {
                    radius: 4
                    color: desk.utilitySurface
                    border.color: pagePicker.activeFocus ? desk.accent : desk.edge
                }
                onValueModified: {
                    if (desk.liveController && !desk.liveSnapshot.busy) {
                        desk.liveController.readPage(value)
                    }
                }
            }
            Label {
                text: "/ " + (desk.liveSnapshot.pageCount || 0)
                color: desk.muted
                font.pixelSize: 12
            }
            IconButton {
                objectName: "nextPage"
                glyph: "chevron-right"
                iconSize: 11
                implicitWidth: 18
                implicitHeight: 20
                padding: 2
                enabled: !desk.liveSnapshot.busy && (desk.liveSnapshot.pageNumber || 1) < (desk.liveSnapshot.pageCount || 1)
                Accessible.name: "Trang kế tiếp"
                onClicked: { if (desk.liveController) desk.liveController.nextPage() }
                ToolTip.visible: hovered
                ToolTip.text: "Trang sau"
            }
            IconButton {
                objectName: "readPage"
                glyph: "arrow-right"
                iconSize: 11
                implicitWidth: 18
                implicitHeight: 20
                padding: 2
                enabled: !desk.liveSnapshot.busy
                Accessible.name: "Đọc trang đã chọn"
                onClicked: { if (desk.liveController) desk.liveController.readPage(pagePicker.value) }
                ToolTip.visible: hovered
                ToolTip.text: "Đọc trang"
            }
        }

        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumWidth: 2
            MouseArea {
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.OpenHandCursor
                onPressed: desk.moveRequested()
            }
        }
    }
}
