import QtQuick
import QtQuick.Controls

Item {
    id: emptyState
    property DeskTheme deskTheme: DeskTheme {}
    property string iconName: "search"
    property string title: ""
    property string subtitle: ""
    property string actionText: ""
    signal actionClicked()

    implicitWidth: 320
    implicitHeight: col.implicitHeight

    Column {
        id: col
        anchors.centerIn: parent
        width: Math.min(parent.width, 360)
        spacing: 8

        DeskIcon {
            anchors.horizontalCenter: parent.horizontalCenter
            name: emptyState.iconName
            color: desk ? desk.muted : emptyState.deskTheme.muted
            width: 32
            height: 32
        }

        Label {
            visible: Boolean(emptyState.title)
            width: parent.width
            text: emptyState.title
            font.pixelSize: desk ? (desk.textTitle || 18) : emptyState.deskTheme.textTitle
            font.weight: Font.DemiBold
            color: desk ? desk.ink : emptyState.deskTheme.ink
            horizontalAlignment: Text.AlignHCenter
        }

        Label {
            visible: Boolean(emptyState.subtitle)
            width: parent.width
            text: emptyState.subtitle
            font.pixelSize: desk ? (desk.textSmall || 12) : emptyState.deskTheme.textSmall
            color: desk ? desk.muted : emptyState.deskTheme.muted
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WordWrap
        }

        QuietButton {
            visible: Boolean(emptyState.actionText)
            anchors.horizontalCenter: parent.horizontalCenter
            text: emptyState.actionText
            primary: true
            onClicked: emptyState.actionClicked()
        }
    }
}
