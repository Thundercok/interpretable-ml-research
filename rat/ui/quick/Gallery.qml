import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: desk
    objectName: "gallery"
    width: 700
    height: 640
    property bool darkMode: false
    property bool reduceMotion: true
    property url mascotSource
    property string previewScene: "idle"

    property DeskTheme deskTheme: DeskTheme { darkMode: desk.darkMode; reduceMotion: desk.reduceMotion }
    readonly property color ink: deskTheme.ink
    readonly property color muted: deskTheme.muted
    readonly property color paperColor: deskTheme.paperColor
    readonly property color inputColor: deskTheme.inputColor
    readonly property color windowColor: deskTheme.windowColor
    readonly property color backingColor: deskTheme.backingColor
    readonly property color edge: deskTheme.edge
    readonly property color accent: deskTheme.accent
    readonly property color accentText: deskTheme.accentText
    readonly property color warningInk: deskTheme.warningInk
    readonly property color pdfInk: deskTheme.pdfInk
    readonly property color sheetPaperColor: deskTheme.sheetPaperColor
    readonly property color errorSurface: deskTheme.errorSurface
    readonly property color errorEdge: deskTheme.errorEdge
    readonly property color errorInk: deskTheme.errorInk
    readonly property color selectedSurface: deskTheme.selectedSurface
    readonly property color selectedEdge: deskTheme.selectedEdge
    readonly property color utilitySurface: deskTheme.utilitySurface
    readonly property color hoverSurface: deskTheme.hoverSurface

    readonly property int textCaption: deskTheme.textCaption
    readonly property int textSmall: deskTheme.textSmall
    readonly property int textBody: deskTheme.textBody
    readonly property int textLarge: deskTheme.textLarge
    readonly property int textTitle: deskTheme.textTitle
    readonly property int textDisplay: deskTheme.textDisplay

    readonly property int radiusSmall: deskTheme.radiusSmall
    readonly property int radiusMedium: deskTheme.radiusMedium
    readonly property int radiusLarge: deskTheme.radiusLarge

    color: windowColor

    ColumnLayout {
        x: 24; y: 24
        width: parent.width - 48
        spacing: 14

        Label {
            text: "RAT Design System — Gallery"
            font.pixelSize: desk.textTitle
            font.weight: Font.Bold
            color: desk.ink
        }

        Card {
            Layout.fillWidth: true
            implicitHeight: 140
            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 12
                spacing: 4
                Label { text: "Display (24px)"; font.pixelSize: desk.textDisplay; color: desk.ink; font.weight: Font.Bold }
                Label { text: "Title (18px)"; font.pixelSize: desk.textTitle; color: desk.ink; font.weight: Font.DemiBold }
                Label { text: "Large (14px)"; font.pixelSize: desk.textLarge; color: desk.ink }
                Label { text: "Body (13px)"; font.pixelSize: desk.textBody; color: desk.ink }
            }
        }

        RowLayout {
            spacing: 12
            QuietButton { text: "QuietButton" }
            QuietButton { text: "Primary"; primary: true }
            IconButton { glyph: "eye" }
            IconButton { glyph: "search" }
            Chip { label: "Chip Normal" }
            Chip { label: "Chip Active"; active: true }
            Badge { text: "Badge" }
        }

        DeskProgress {
            Layout.fillWidth: true
            value: 0.65
        }

        Banner {
            Layout.fillWidth: true
            text: "Thông báo mẫu: Hệ thiết kế đã được token hóa thành công."
            type: "info"
            iconName: "alert"
            actionText: "Xem chi tiết"
        }

        Card {
            Layout.fillWidth: true
            implicitHeight: 160
            EmptyState {
                anchors.fill: parent
                anchors.margins: 16
                iconName: "document"
                title: "Chưa có tài liệu"
                subtitle: "Thả tệp PDF vào đây hoặc gõ câu lệnh để bắt đầu."
                actionText: "Chọn tệp PDF"
            }
        }
    }
}
