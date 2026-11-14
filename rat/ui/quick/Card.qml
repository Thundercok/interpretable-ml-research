import QtQuick

Rectangle {
    id: card
    property DeskTheme deskTheme: DeskTheme {}
    color: desk ? desk.paperColor : deskTheme.paperColor
    radius: desk ? (desk.radiusLarge || 12) : deskTheme.radiusLarge
    border.width: 1
    border.color: desk ? desk.edge : deskTheme.edge
}
