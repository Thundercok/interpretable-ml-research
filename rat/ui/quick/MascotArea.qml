import QtQuick

Item {
    id: mascotItem
    objectName: "mascotCrop"
    property real composerX: 0
    property real composerY: 0
    property real reactionOffsetX: 0
    property real reactionOffsetY: 0
    property real reactionRot: 0

    visible: !desk.expanded && !desk.liveSnapshot.busy
    x: Math.max(4, composerX - 110) + reactionOffsetX
    y: composerY - 116 + reactionOffsetY
    width: 122
    height: 116
    clip: true
    z: 4
    rotation: reactionRot

    function triggerPokeReaction(streak) {
        if (desk.reduceMotion) return
        if (mascotWobble.running) mascotWobble.stop()
        if (mascotStartle.running) mascotStartle.stop()
        if (mascotShudder.running) mascotShudder.stop()

        if (streak === 1) {
            mascotWobble.restart()
        } else if (streak === 2) {
            mascotStartle.restart()
        } else {
            mascotShudder.restart()
        }
    }

    Image {
        width: 180
        height: width * (sourceSize.height / Math.max(1, sourceSize.width))
        source: desk.mascotSource
        fillMode: Image.PreserveAspectFit
        smooth: true
        Accessible.ignored: true
    }
    MouseArea {
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: desk.pokeRat()
    }
    SequentialAnimation {
        id: mascotWobble
        NumberAnimation { target: mascotItem; property: "reactionOffsetY"; from: 0; to: -6; duration: 80; easing.type: Easing.OutQuad }
        NumberAnimation { target: mascotItem; property: "reactionRot"; from: 0; to: 3; duration: 60 }
        NumberAnimation { target: mascotItem; property: "reactionRot"; from: 3; to: -3; duration: 80 }
        NumberAnimation { target: mascotItem; property: "reactionRot"; from: -3; to: 0; duration: 60 }
        NumberAnimation { target: mascotItem; property: "reactionOffsetY"; from: -6; to: 0; duration: 100; easing.type: Easing.OutBounce }
        onStopped: {
            mascotItem.reactionOffsetY = 0
            mascotItem.reactionRot = 0
        }
    }
    SequentialAnimation {
        id: mascotStartle
        NumberAnimation { target: mascotItem; property: "reactionOffsetY"; from: 0; to: -14; duration: 70; easing.type: Easing.OutQuad }
        NumberAnimation { target: mascotItem; property: "reactionRot"; from: 0; to: -6; duration: 50 }
        NumberAnimation { target: mascotItem; property: "reactionRot"; from: -6; to: 5; duration: 60 }
        NumberAnimation { target: mascotItem; property: "reactionRot"; from: 5; to: 0; duration: 60 }
        NumberAnimation { target: mascotItem; property: "reactionOffsetY"; from: -14; to: 0; duration: 120; easing.type: Easing.OutBounce }
        onStopped: {
            mascotItem.reactionOffsetY = 0
            mascotItem.reactionRot = 0
        }
    }
    SequentialAnimation {
        id: mascotShudder
        NumberAnimation { target: mascotItem; property: "reactionOffsetX"; from: 0; to: 4; duration: 40 }
        NumberAnimation { target: mascotItem; property: "reactionOffsetX"; from: 4; to: -4; duration: 40 }
        NumberAnimation { target: mascotItem; property: "reactionOffsetX"; from: -4; to: 4; duration: 40 }
        NumberAnimation { target: mascotItem; property: "reactionOffsetX"; from: 4; to: -4; duration: 40 }
        NumberAnimation { target: mascotItem; property: "reactionOffsetX"; from: -4; to: 0; duration: 40 }
        onStopped: {
            mascotItem.reactionOffsetX = 0
            mascotItem.reactionRot = 0
        }
    }
}
