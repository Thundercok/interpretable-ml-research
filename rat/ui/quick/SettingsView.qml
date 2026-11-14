import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs

ColumnLayout {
    id: settingsView
    objectName: "settingsView"
    visible: desk.liveSnapshot.view === "settings"
    Layout.fillWidth: true
    spacing: 12

    Rectangle {
        Layout.fillWidth: true
        implicitHeight: folderCol.implicitHeight + 24
        radius: desk.cardRadius
        color: desk.utilitySurface
        border.width: 1
        border.color: desk.edge

        ColumnLayout {
            id: folderCol
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.margins: 14
            spacing: 8

            RowLayout {
                Layout.fillWidth: true
                spacing: 6
                DeskIcon { name: "folder"; color: desk.accent; width: 14; height: 14; Layout.preferredWidth: 14; Layout.preferredHeight: 14 }
                Label {
                    text: "Thư mục theo dõi & quét tệp"
                    font.pixelSize: 13
                    font.weight: Font.DemiBold
                    color: desk.ink
                    Layout.fillWidth: true
                }
            }

            Label {
                text: "RAT tự động cập nhật và tìm kiếm các tệp trong các thư mục này:"
                font.pixelSize: 12
                color: desk.muted
                Layout.fillWidth: true
                wrapMode: Text.Wrap
            }

            Repeater {
                id: folderRepeater
                model: desk.liveController ? desk.liveController.getIndexedFolders() : []
                RowLayout {
                    required property string modelData
                    required property int index
                    Layout.fillWidth: true
                    spacing: 8
                    Rectangle {
                        implicitWidth: 6; implicitHeight: 6; radius: 3; color: desk.accent
                    }
                    Label {
                        text: modelData
                        textFormat: Text.PlainText
                        color: desk.ink
                        font.pixelSize: 12
                        elide: Text.ElideMiddle
                        Layout.fillWidth: true
                    }
                    QuietButton {
                        text: "Bỏ"
                        font.pixelSize: 11
                        topPadding: 2; bottomPadding: 2; leftPadding: 6; rightPadding: 6
                        onClicked: {
                            if (desk.liveController) desk.liveController.removeIndexedFolder(index)
                        }
                    }
                }
            }

            QuietButton {
                text: "Thêm thư mục…"
                iconName: "plus"
                font.pixelSize: 12
                onClicked: folderDialog.open()
            }
        }
    }

    Rectangle {
        Layout.fillWidth: true
        implicitHeight: indexCol.implicitHeight + 24
        radius: desk.cardRadius
        color: desk.utilitySurface
        border.width: 1
        border.color: desk.edge

        ColumnLayout {
            id: indexCol
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.margins: 14
            spacing: 8

            RowLayout {
                Layout.fillWidth: true
                spacing: 6
                DeskIcon { name: "sparkle"; color: desk.accent; width: 14; height: 14; Layout.preferredWidth: 14; Layout.preferredHeight: 14 }
                Label {
                    text: "Chỉ mục tìm kiếm"
                    font.pixelSize: 13
                    font.weight: Font.DemiBold
                    color: desk.ink
                    Layout.fillWidth: true
                }
            }

            Label {
                text: desk.liveSnapshot.indexStatus || "Chỉ mục tìm kiếm đã sẵn sàng."
                font.pixelSize: 12
                color: desk.muted
                Layout.fillWidth: true
                wrapMode: Text.Wrap
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                QuietButton {
                    primary: true
                    text: "Quét lại chỉ mục ngay"
                    iconName: "search"
                    enabled: !desk.liveSnapshot.busy
                    onClicked: {
                        if (desk.liveController) desk.liveController.startIndexing("manual")
                    }
                }
            }
        }
    }

    Rectangle {
        Layout.fillWidth: true
        implicitHeight: appearCol.implicitHeight + 24
        radius: desk.cardRadius
        color: desk.utilitySurface
        border.width: 1
        border.color: desk.edge

        ColumnLayout {
            id: appearCol
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.margins: 14
            spacing: 10

            RowLayout {
                Layout.fillWidth: true
                spacing: 6
                DeskIcon { name: "eye"; color: desk.accent; width: 14; height: 14; Layout.preferredWidth: 14; Layout.preferredHeight: 14 }
                Label {
                    text: "Giao diện & Hiển thị"
                    font.pixelSize: 13
                    font.weight: Font.DemiBold
                    color: desk.ink
                    Layout.fillWidth: true
                }
            }

            RowLayout {
                Layout.fillWidth: true
                Label {
                    text: "Chế độ nền tối (Dark mode)"
                    font.pixelSize: 12
                    color: desk.ink
                    Layout.fillWidth: true
                }
                QuietButton {
                    text: desk.darkMode ? "Bật" : "Tắt"
                    primary: desk.darkMode
                    onClicked: desk.darkMode = !desk.darkMode
                }
            }

            RowLayout {
                Layout.fillWidth: true
                Label {
                    text: "Giảm chuyển động (Reduce motion)"
                    font.pixelSize: 12
                    color: desk.ink
                    Layout.fillWidth: true
                }
                QuietButton {
                    text: desk.reduceMotion ? "Bật" : "Tắt"
                    primary: desk.reduceMotion
                    onClicked: desk.reduceMotion = !desk.reduceMotion
                }
            }
        }
    }

    FolderDialog {
        id: folderDialog
        title: "Chọn thư mục cần theo dõi"
        onAccepted: {
            if (desk.liveController) {
                var path = desk.liveController.localFolderPath(selectedFolder)
                if (path) desk.liveController.addIndexedFolder(path)
            }
        }
    }
}
