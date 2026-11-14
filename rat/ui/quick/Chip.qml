import QtQuick
import QtQuick.Controls

Rectangle {
    id: chip
    property DeskTheme deskTheme: DeskTheme {}
    property string label: ""
    property bool active: false
    signal clicked()
    implicitHeight: 30
    implicitWidth: chipLabel.implicitWidth + 24
    radius: 15
    color: active
        ? (desk ? desk.selectedSurface : deskTheme.selectedSurface)
        : (chipMouse.containsMouse
            ? (desk ? desk.hoverSurface : deskTheme.hoverSurface)
            : (desk ? desk.utilitySurface : deskTheme.utilitySurface))
    border.width: 1
    border.color: active
        ? (desk ? desk.selectedEdge : deskTheme.selectedEdge)
        : (desk ? desk.edge : deskTheme.edge)
    opacity: enabled ? 1 : 0.5
    Accessible.role: Accessible.Button
    Accessible.name: label

    Label {
        id: chipLabel
        anchors.centerIn: parent
        text: chip.label
        font.pixelSize: desk ? (desk.textSmall || 12) : chip.deskTheme.textSmall
        font.weight: chip.active ? Font.DemiBold : Font.Medium
        color: chip.active
            ? (desk ? desk.accent : chip.deskTheme.accent)
            : (desk ? desk.ink : chip.deskTheme.ink)
    }

    MouseArea {
        id: chipMouse
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: chip.clicked()
    }
}
