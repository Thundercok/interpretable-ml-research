import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ColumnLayout {
    id: previewScenePicker
    visible: !desk.liveMode
    x: 32
    y: 20
    width: parent.width - 64
    spacing: 6
    RowLayout {
        Layout.fillWidth: true
        spacing: 10
        Label { text: desk.liveMode ? "RAT · PDF offline" : "RAT · Qt Quick · Nội dung minh họa"; color: desk.muted; font.pixelSize: 12; Layout.fillWidth: desk.liveMode }
        ComboBox {
            id: scenePicker
            objectName: "scenePicker"
            textRole: "label"
            valueRole: "scene"
            implicitWidth: 205
            Accessible.name: "Trạng thái minh họa"
            visible: !desk.liveMode
            currentIndex: ["idle", "unread", "folded", "startup", "receiving", "working", "result"].indexOf(desk.sceneKey)
            model: [
                {label: "Mặc định · Simple", scene: "idle"},
                {label: "Simple · Có !", scene: "unread"},
                {label: "Simple · Đã xem", scene: "folded"},
                {label: "Khởi động RAT", scene: "startup"},
                {label: "Đang nhận yêu cầu", scene: "receiving"},
                {label: "Workbench · Đang làm", scene: "working"},
                {label: "Workbench · Kết quả", scene: "result"}
            ]
            onActivated: desk.previewScene = currentValue
        }
    }
}
