import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: snapCard
    property DeskTheme deskTheme: DeskTheme {}
    property bool activeSnapshot: true
    property string pdfPath: ""
    property int pdfPage: 0
    property string matchQuery: ""
    property string matchSnippet: ""
    property int maxCardHeight: 132
    signal activated()

    readonly property string snapshotUrl: (desk.liveMode && activeSnapshot && pdfPath.length > 0 && pdfPage > 0)
        ? desk.liveController.pageSnapshot(pdfPath, pdfPage, matchQuery, matchSnippet)
        : ""
    readonly property bool snapshotReady: snapImage.status === Image.Ready && snapImage.implicitWidth > 0 && snapImage.implicitHeight > 0
    readonly property real targetWidth: Math.max(200, (typeof resultScroll !== "undefined" ? resultScroll.availableWidth : width) - 18)

    visible: activeSnapshot && snapshotUrl.length > 0
    Layout.fillWidth: true
    implicitHeight: snapshotReady
        ? Math.min(maxCardHeight, Math.max(58, Math.round(targetWidth * (snapImage.implicitHeight / Math.max(1, snapImage.implicitWidth))) + 8))
        : 0
    radius: 8
    color: desk ? desk.sheetPaperColor : snapCard.deskTheme.sheetPaperColor
    border.width: snapMouse.containsMouse ? 1.5 : 1
    border.color: snapMouse.containsMouse ? desk.accent : desk.edge
    clip: true
    Accessible.role: Accessible.Button

    Image {
        id: snapImage
        anchors.fill: parent
        anchors.margins: 4
        source: snapCard.snapshotUrl
        fillMode: Image.PreserveAspectFit
        smooth: true
        mipmap: true
        cache: false
        Accessible.ignored: true
    }

    Rectangle {
        visible: snapMouse.containsMouse
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.margins: 6
        radius: 4
        color: Qt.rgba(desk.paperColor.r, desk.paperColor.g, desk.paperColor.b, 0.92)
        border.width: 1
        border.color: desk.selectedEdge
        implicitWidth: openHintLabel.implicitWidth + 10
        implicitHeight: 20
        Label {
            id: openHintLabel
            anchors.centerIn: parent
            text: "Đọc trang " + snapCard.pdfPage + " →"
            color: desk.accent
            font.pixelSize: 11
            font.weight: Font.Medium
        }
    }

    MouseArea {
        id: snapMouse
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: snapCard.activated()
    }
}
