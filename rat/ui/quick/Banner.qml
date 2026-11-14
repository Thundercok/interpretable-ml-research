import QtQuick
import QtQuick.Controls

Rectangle {
    id: banner
    property DeskTheme deskTheme: DeskTheme {}
    property string text: ""
    property string iconName: "alert"
    property string type: "info"
    property string actionText: ""
    signal actionClicked()
    signal dismissClicked()

    readonly property color bannerBg: type === "error"
        ? (desk ? desk.errorSurface : deskTheme.errorSurface)
        : type === "warning"
            ? (desk ? desk.utilitySurface : deskTheme.utilitySurface)
            : (desk ? desk.selectedSurface : deskTheme.selectedSurface)

    readonly property color bannerEdge: type === "error"
        ? (desk ? desk.errorEdge : deskTheme.errorEdge)
        : type === "warning"
            ? (desk ? desk.selectedEdge : deskTheme.selectedEdge)
            : (desk ? desk.selectedEdge : deskTheme.selectedEdge)

    readonly property color bannerText: type === "error"
        ? (desk ? desk.errorInk : deskTheme.errorInk)
        : type === "warning"
            ? (desk ? desk.warningInk : deskTheme.warningInk)
            : (desk ? desk.ink : deskTheme.ink)

    radius: desk ? (desk.radiusMedium || 8) : deskTheme.radiusMedium
    color: bannerBg
    border.width: 1
    border.color: bannerEdge
    implicitHeight: 36
    implicitWidth: 320

    Row {
        anchors.fill: parent
        anchors.leftMargin: 10
        anchors.rightMargin: 10
        spacing: 8

        DeskIcon {
            anchors.verticalCenter: parent.verticalCenter
            name: banner.iconName
            color: banner.bannerText
            width: 16
            height: 16
        }

        Label {
            anchors.verticalCenter: parent.verticalCenter
            width: parent.width - 24 - (banner.actionText ? actionBtn.width + 8 : 0)
            text: banner.text
            color: banner.bannerText
            font.pixelSize: desk ? (desk.textSmall || 12) : banner.deskTheme.textSmall
            elide: Text.ElideRight
        }

        QuietButton {
            id: actionBtn
            anchors.verticalCenter: parent.verticalCenter
            visible: Boolean(banner.actionText)
            text: banner.actionText
            plain: true
            onClicked: banner.actionClicked()
        }
    }
}
