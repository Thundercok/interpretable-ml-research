import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: finderDrawerTab
    objectName: "finderDrawerTab"
    visible: desk.hasLatentFinderHits
    width: drawerTabRow.implicitWidth + 20
    height: 33
    radius: 12
    color: drawerTabMouse.containsMouse ? desk.selectedSurface : desk.utilitySurface
    border.width: 1
    border.color: desk.selectedEdge
    z: 4.5
    Accessible.name: desk.allFinderHits.length + " tệp hoặc ứng dụng khớp, bấm để mở gợi ý"
    Accessible.role: Accessible.Button

    Row {
        id: drawerTabRow
        anchors.left: parent.left
        anchors.leftMargin: 10
        anchors.top: parent.top
        anchors.topMargin: 5
        spacing: 6
        DeskIcon {
            name: "folder"
            color: desk.accent
            width: 13
            height: 13
        }
        Label {
            text: desk.allFinderHits.length + " tệp/app khớp · Xem"
            font.pixelSize: 12
            font.weight: Font.Medium
            color: desk.accent
        }
        DeskIcon {
            name: "chevron-up"
            color: desk.accent
            width: 11
            height: 11
        }
    }

    MouseArea {
        id: drawerTabMouse
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: {
            if (desk.liveController) {
                desk.liveController.openFinderSuggestions()
                desk.editor.forceActiveFocus()
            }
        }
    }
}
