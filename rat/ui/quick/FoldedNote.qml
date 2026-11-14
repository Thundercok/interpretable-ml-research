import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Button {
    id: note
    objectName: "notice"
    property real composerX: 0
    property real composerY: 0
    property real composerWidth: 580
    visible: !desk.expanded && desk.hasWorkbench
    x: composerX + 126
    y: composerY - height + (desk.hasAnswerPreview ? 12 : 7)
    width: desk.hasAnswerPreview || (desk.liveMode && desk.liveSnapshot.busy) || desk.hasFinderPreview ? Math.min(360, composerWidth - 126) : Math.min(228, composerWidth - 126)
    height: desk.hasAnswerPreview ? Math.max(76, Math.min(112, minPreviewContent.implicitHeight + topPadding + bottomPadding)) : desk.hasFinderPreview || desk.hasPagePreview || (desk.liveMode && desk.liveSnapshot.busy) ? Math.max(48, minPreviewContent.implicitHeight + topPadding + bottomPadding) : desk.noticeVisible ? 61 : 48
    rotation: -1.2
    z: 3
    Accessible.name: desk.hasFinderPreview
        ? ("Gợi ý tìm kiếm: " + (desk.allFinderHits[0].title || "") + " (" + (desk.allFinderHits[0].kind === "application" ? "Ứng dụng" : "Tệp") + ") tại " + (desk.allFinderHits[0].display_path || desk.allFinderHits[0].path || "") + ". Mở gợi ý")
        : desk.hasAnswerPreview
            ? (desk.noticeVisible ? "Kết quả mới. " : "") + desk.previewMeta + ". " + desk.previewBody + ". Mở câu trả lời đầy đủ"
            : desk.liveMode && desk.liveSnapshot.busy
                ? desk.liveSnapshot.status + ". Mở tiến trình"
                : desk.hasPagePreview
                    ? desk.pagePreviewTitle + ". " + desk.liveSnapshot.fileName + ". Mở lại nội dung trang"
                    : desk.noticeVisible
                        ? "Có kết quả mới, mở workbench"
                        : "Mở lại workbench"
    onClicked: desk.openWorkbench()
    background: Rectangle {
        radius: 12
        antialiasing: true
        color: note.hovered ? desk.backingColor : desk.paperColor
        border.width: note.visualFocus ? 2 : 1
        border.color: note.visualFocus ? desk.accent : desk.edge
    }
    contentItem: ColumnLayout {
        id: minPreviewContent
        spacing: 6
        RowLayout {
            Layout.fillWidth: true
            spacing: 8
            Label {
                objectName: "minAnswerExcerpt"
                Layout.fillWidth: true
                text: desk.hasFinderPreview
                    ? ("Gợi ý: " + (desk.allFinderHits[0].title || "Tìm kiếm"))
                    : desk.hasReadingPreview ? "Bàn xem · " + ((desk.liveSnapshot.readingSession || {}).cards || []).length + " lá"
                    : desk.hasAnswerPreview ? desk.previewBody : desk.liveMode && desk.liveSnapshot.busy ? desk.liveSnapshot.status : desk.liveMode && desk.liveSnapshot.errorCode ? "Xem thông báo" : desk.hasPagePreview ? desk.pagePreviewTitle : desk.phase === "working" ? "Xem tiến trình" : "Xem kết quả"
                textFormat: Text.PlainText
                color: desk.hasAnswerPreview || desk.hasFinderPreview ? desk.ink : desk.accent
                font.pixelSize: 13
                font.family: desk.liveSnapshot.answerPreviewIsCode ? "Menlo" : Qt.application.font.family
                wrapMode: desk.liveSnapshot.answerPreviewIsCode ? Text.NoWrap : Text.Wrap
                maximumLineCount: 3
                elide: Text.ElideRight
            }
            DeskIcon { name: "chevron-up"; color: desk.accent; Layout.preferredWidth: 14; Layout.preferredHeight: 14; Layout.alignment: Qt.AlignTop }
        }
        RowLayout {
            visible: desk.hasAnswerPreview || desk.hasPagePreview || desk.hasFinderPreview || desk.hasReadingPreview || desk.noticeVisible
            Layout.fillWidth: true
            spacing: 5
            Rectangle { visible: desk.noticeVisible; implicitWidth: 5; implicitHeight: 5; radius: 3; color: desk.accent }
            Label {
                objectName: "minAnswerMetadata"
                Layout.fillWidth: true
                text: desk.hasFinderPreview
                    ? ((desk.allFinderHits[0].kind === "application" ? "Ứng dụng" : "Tệp") + " · " + (desk.allFinderHits[0].display_path || desk.allFinderHits[0].path || "") + " (" + desk.allFinderHits.length + " kết quả)")
                    : desk.hasReadingPreview ? (((desk.liveSnapshot.readingSession || {}).chart || {}).name || "Chưa mở hồ sơ lá số")
                    : desk.hasAnswerPreview ? desk.previewMeta : desk.hasPagePreview ? desk.liveSnapshot.fileName : "Kết quả mới"
                textFormat: Text.PlainText
                font.pixelSize: 11
                color: desk.incompletePreview || desk.liveSnapshot.answerVerification === "FAIL" ? desk.warningInk : desk.muted
                wrapMode: desk.hasPagePreview || desk.hasFinderPreview ? Text.NoWrap : Text.Wrap
                maximumLineCount: 1
                elide: desk.hasPagePreview || desk.hasFinderPreview ? Text.ElideMiddle : Text.ElideRight
            }
        }
    }
    topPadding: desk.hasAnswerPreview ? 10 : 6
    bottomPadding: desk.hasAnswerPreview ? 22 : 17
    leftPadding: 16
    rightPadding: 16
}
