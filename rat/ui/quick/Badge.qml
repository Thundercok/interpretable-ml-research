import QtQuick
import QtQuick.Controls

Rectangle {
    id: badge
    property DeskTheme deskTheme: DeskTheme {}
    property string text: ""
    property color textColor: desk ? desk.ink : deskTheme.ink
    property int fontPixelSize: desk ? (desk.textCaption || 11) : deskTheme.textCaption
    property int fontWeight: Font.Normal

    radius: desk ? (desk.radiusSmall || 4) : deskTheme.radiusSmall
    color: desk ? desk.selectedSurface : deskTheme.selectedSurface
    border.width: 1
    border.color: desk ? desk.selectedEdge : deskTheme.selectedEdge
    implicitWidth: badgeLabel.implicitWidth + 12
    implicitHeight: 22

    Label {
        id: badgeLabel
        anchors.centerIn: parent
        text: badge.text
        font.pixelSize: badge.fontPixelSize
        font.weight: badge.fontWeight
        color: badge.textColor
    }
}
