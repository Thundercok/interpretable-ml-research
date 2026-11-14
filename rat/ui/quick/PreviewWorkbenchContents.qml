import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ColumnLayout {
    id: previewContents
    visible: !desk.liveMode
    Layout.fillWidth: true
    spacing: 6

    RowLayout {
        Layout.fillWidth: true
        Label {
            Layout.fillWidth: true
            text: "Tối đa bao nhiêu tín chỉ mỗi học kỳ?"
            textFormat: Text.PlainText
            color: desk.muted
            font.pixelSize: 12
            wrapMode: Text.Wrap
        }
        QuietButton { objectName: "foldButton"; text: ""; iconName: "minus"; Accessible.name: "Thu workbench"; onClicked: desk.foldWorkbench() }
    }
    Label {
        visible: desk.phase === "working" || desk.phase === "result"
        Layout.fillWidth: true
        text: desk.phase === "working" ? "Mình đang đối chiếu quy chế." : "Tối đa 24 tín chỉ cho học kỳ chính."
        textFormat: Text.PlainText
        color: desk.ink
        font.pixelSize: 20
        font.weight: Font.Medium
        wrapMode: Text.Wrap
    }
    Label {
        visible: desk.phase === "result"
        Layout.fillWidth: true
        text: "Với học kỳ hè, giới hạn là 12 tín chỉ."
        color: desk.ink
        font.pixelSize: 14
        wrapMode: Text.Wrap
    }
    Label {
        visible: desk.phase === "result"
        Layout.fillWidth: true
        text: "Nhớ kiểm tra điều kiện tiên quyết và lịch học trước khi đăng ký."
        color: desk.muted
        font.pixelSize: 13
        wrapMode: Text.Wrap
    }
    RowLayout {
        visible: desk.phase === "working"
        Layout.fillWidth: true
        Label { text: "Luồng thao tác minh họa"; color: desk.muted; font.pixelSize: 12; Layout.fillWidth: true; wrapMode: Text.Wrap }
        QuietButton {
            objectName: "trailMode"
            text: desk.compactTrail ? "Xem trực quan" : "Xem gọn"
            onClicked: desk.compactTrail = !desk.compactTrail
        }
    }
    ColumnLayout {
        visible: desk.phase === "working" && !desk.compactTrail
        Layout.fillWidth: true
        spacing: 11
        Repeater {
            model: ["✓  Đọc yêu cầu", "✓  Đọc tài liệu được chọn", "●  Đối chiếu điều kiện", "○  Soạn câu trả lời"]
            Label { required property string modelData; text: modelData; color: desk.ink; font.pixelSize: 13; Layout.fillWidth: true; wrapMode: Text.Wrap }
        }
    }
    Label {
        visible: desk.phase === "working" && desk.compactTrail
        text: "●  Đối chiếu điều kiện · 3 / 4"
        color: desk.ink
        font.pixelSize: 13
        Layout.fillWidth: true
        wrapMode: Text.Wrap
    }
    Label {
        visible: desk.sourceOpen
        text: "Quy chế học vụ · bản mẫu\nHọc kỳ chính tối đa 24 tín chỉ; học kỳ hè tối đa 12 tín chỉ."
        color: desk.muted
        font.pixelSize: 13
        Layout.fillWidth: true
        wrapMode: Text.Wrap
    }
    Label {
        visible: desk.logOpen && desk.phase === "result"
        text: "Đã nhận yêu cầu → Đọc đoạn tài liệu → Đối chiếu hai học kỳ → Tạo câu trả lời."
        color: desk.muted
        font.pixelSize: 13
        Layout.fillWidth: true
        wrapMode: Text.Wrap
    }
}
