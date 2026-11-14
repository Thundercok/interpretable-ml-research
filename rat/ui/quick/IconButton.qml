import QtQuick
import QtQuick.Controls

Button {
    id: iconControl
    property DeskTheme deskTheme: DeskTheme {}
    property string glyph: "eye"
    property int iconSize: 16
    opacity: enabled ? 1 : 0.45
    hoverEnabled: true
    implicitWidth: 28
    implicitHeight: 28
    padding: 6
    contentItem: Item {
        implicitWidth: iconControl.iconSize
        implicitHeight: iconControl.iconSize
        DeskIcon {
            anchors.centerIn: parent
            name: iconControl.glyph
            color: desk ? desk.muted : iconControl.deskTheme.muted
            width: iconControl.iconSize
            height: iconControl.iconSize
        }
    }
    background: Rectangle {
        radius: 8
        color: iconControl.down
            ? (desk ? desk.selectedSurface : iconControl.deskTheme.selectedSurface)
            : (iconControl.hovered
                ? (desk ? desk.hoverSurface : iconControl.deskTheme.hoverSurface)
                : "transparent")
        border.color: desk ? desk.accent : iconControl.deskTheme.accent
        border.width: iconControl.visualFocus ? 1 : 0
    }
}
