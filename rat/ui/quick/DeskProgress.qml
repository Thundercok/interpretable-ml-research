import QtQuick
import QtQuick.Controls

ProgressBar {
    id: progress
    property DeskTheme deskTheme: DeskTheme {}
    implicitHeight: 3
    background: Rectangle {
        radius: 2
        color: desk ? desk.edge : progress.deskTheme.edge
    }
    contentItem: Item {
        clip: true
        Rectangle {
            id: progressSegment
            width: Math.max(24, parent.width * 0.24)
            height: parent.height
            radius: 2
            color: desk ? desk.accent : progress.deskTheme.accent
            NumberAnimation on x {
                from: -progressSegment.width
                to: progress.width
                duration: 1350
                loops: Animation.Infinite
                running: progress.visible && !(desk && desk.reduceMotion)
            }
        }
    }
}
