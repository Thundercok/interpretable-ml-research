import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: sidePdfPane
    objectName: "sidePdfPane"
    visible: desk.isSideBySidePdfActive
    x: 0
    width: Math.max(300, Math.min(460, Math.floor((parent.width - 16) * 0.44)))
    radius: 16
    color: desk.paperColor
    border.color: desk.edge
    clip: true
    z: 1

    RowLayout {
        id: sidePdfHeader
        x: 14
        y: 10
        width: parent.width - 28
        height: 24
        spacing: 6

        DeskIcon { name: "pdf"; color: desk.pdfInk; width: 14; height: 14; Layout.preferredWidth: 14; Layout.preferredHeight: 14 }
        Label {
            text: desk.liveSnapshot.fileName || "Tài liệu PDF"
            elide: Text.ElideMiddle
            font.pixelSize: 12
            font.weight: Font.Medium
            color: desk.ink
            Layout.fillWidth: true
        }
        IconButton {
            glyph: "chevron-left"
            iconSize: 11
            implicitWidth: 18
            implicitHeight: 20
            enabled: (desk.liveSnapshot.previewPageNumber || 1) > 1
            Accessible.name: "Trang trước"
            onClicked: {
                if (desk.liveController) {
                    var p = (desk.liveSnapshot.previewPageNumber || 1) - 1;
                    desk.liveController.previewPdfPage(p);
                }
            }
        }
        Label {
            text: (desk.liveSnapshot.previewPageNumber || 1) + " / " + (desk.liveSnapshot.pageCount || 1)
            font.pixelSize: 12
            color: desk.muted
        }
        IconButton {
            glyph: "chevron-right"
            iconSize: 11
            implicitWidth: 18
            implicitHeight: 20
            enabled: (desk.liveSnapshot.previewPageNumber || 1) < (desk.liveSnapshot.pageCount || 1)
            Accessible.name: "Trang sau"
            onClicked: {
                if (desk.liveController) {
                    var p = (desk.liveSnapshot.previewPageNumber || 1) + 1;
                    desk.liveController.previewPdfPage(p);
                }
            }
        }
        QuietButton {
            iconName: "external"
            iconSize: 12
            leftPadding: 4
            rightPadding: 4
            topPadding: 2
            bottomPadding: 2
            Accessible.name: "Mở PDF gốc"
            onClicked: {
                if (desk.liveController && desk.liveSnapshot.activeContext) {
                    desk.liveController.openOriginalPdf();
                }
            }
        }
    }

    Rectangle {
        id: sidePdfSep
        x: 14
        y: 38
        width: parent.width - 28
        height: 1
        color: desk.edge
    }

    Rectangle {
        id: snippetBanner
        visible: Boolean(desk.liveSnapshot.previewSnippet)
        anchors.top: sidePdfSep.bottom
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.topMargin: 6
        anchors.leftMargin: 12
        anchors.rightMargin: 12
        implicitHeight: snippetLabel.implicitHeight + 10
        radius: 8
        color: desk.utilitySurface
        border.width: 1
        border.color: desk.selectedEdge
        Label {
            id: snippetLabel
            anchors.fill: parent
            anchors.margins: 5
            text: "Đối chiếu: “" + desk.cleanSnippetText(desk.liveSnapshot.previewSnippet || "") + "”"
            font.pixelSize: 11
            color: desk.accent
            elide: Text.ElideRight
            maximumLineCount: 2
            wrapMode: Text.Wrap
        }
    }

    Flickable {
        anchors.top: snippetBanner.visible ? snippetBanner.bottom : sidePdfSep.bottom
        anchors.topMargin: snippetBanner.visible ? 6 : 8
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.margins: 8
        clip: true
        contentWidth: width
        contentHeight: sidePdfImage.status === Image.Ready && sidePdfImage.implicitWidth > 0
            ? Math.round(width * (sidePdfImage.implicitHeight / Math.max(1, sidePdfImage.implicitWidth)))
            : height

        Image {
            id: sidePdfImage
            width: parent.width
            height: implicitWidth > 0 ? Math.round(width * (implicitHeight / implicitWidth)) : parent.height
            fillMode: Image.PreserveAspectFit
            smooth: true
            mipmap: true
            cache: false
            source: (desk.liveMode && desk.isSideBySidePdfActive && desk.liveSnapshot.activeContext && desk.liveSnapshot.activeContext.path)
                ? desk.liveController.fullPageSnapshot(desk.liveSnapshot.activeContext.path, desk.liveSnapshot.previewPageNumber || 1, 1000)
                : ""
        }
    }
}
