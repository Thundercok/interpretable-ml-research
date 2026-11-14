import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Repeater {
    id: searchResultsView
    model: desk.searchHits
    ColumnLayout {
        required property var modelData
        Layout.fillWidth: true
        spacing: 6
        Rectangle { Layout.fillWidth: true; height: 1; color: desk.edge }
        RowLayout {
            Layout.fillWidth: true
            Label { text: (modelData.page_label && String(modelData.page_label) !== String(modelData.page)) ? ("Trang " + modelData.page + " · nhãn " + modelData.page_label) : ("Trang " + modelData.page); textFormat: Text.PlainText; color: desk.accent; font.pixelSize: 13; font.weight: Font.Medium; Layout.fillWidth: true; wrapMode: Text.Wrap }
            QuietButton { objectName: "readHit_" + modelData.page; text: "Đọc trang"; trailingIconName: "arrow-right"; trailingIconSize: 12; onClicked: { desk.readerDisplayMode = "matched"; desk.liveController.openSearchHit(modelData.page) } }
        }
        PdfSnapshotCard {
            id: hitSnapshotCard
            objectName: "searchSnapshot_" + modelData.page
            activeSnapshot: desk.liveSnapshot.view === "search"
            pdfPath: modelData.path || ""
            pdfPage: modelData.page || 0
            matchQuery: desk.liveSnapshot.searchQuery || ""
            matchSnippet: modelData.snippet || ""
            maxCardHeight: 132
            Accessible.name: "Ảnh chụp đoạn khớp tại trang PDF " + modelData.page + ", bấm để đọc trang"
            onActivated: { desk.readerDisplayMode = "matched"; desk.liveController.openSearchHit(modelData.page) }
        }
        Label {
            visible: !hitSnapshotCard.snapshotReady && text !== ""
            text: String(modelData.snippet || "").replace(/\s+/g, " ").trim()
            textFormat: Text.PlainText
            color: desk.muted
            font.pixelSize: 12
            wrapMode: Text.Wrap
            maximumLineCount: 2
            elide: Text.ElideRight
            Layout.fillWidth: true
        }
    }
}
