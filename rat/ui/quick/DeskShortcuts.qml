import QtQuick

Item {
    id: deskShortcuts

    Shortcut {
        sequences: ["Ctrl+Shift+L", "Meta+Shift+L"]
        enabled: desk.liveMode && !desk.liveSnapshot.busy
        onActivated: desk.liveController.quickLookSelection()
    }
    Shortcut {
        sequences: ["Ctrl+Shift+R", "Meta+Shift+R"]
        enabled: desk.liveMode && !desk.liveSnapshot.busy
        onActivated: { desk.liveController.openReadingDesk(); if (desk.editor) desk.editor.forceActiveFocus() }
    }
    Shortcut {
        sequence: "Ctrl+F"
        enabled: desk.liveMode && Boolean(desk.liveSnapshot.fileName)
        onActivated: desk.openPdfSearch()
    }
    Shortcut {
        sequence: "Meta+F"
        enabled: desk.liveMode && Boolean(desk.liveSnapshot.fileName)
        onActivated: desk.openPdfSearch()
    }
    Shortcut {
        sequences: [StandardKey.Close, StandardKey.Quit]
        enabled: desk.liveMode
        onActivated: desk.closeRequested()
    }
    Shortcut {
        sequence: "Escape"
        enabled: true
        onActivated: desk.handleEscape()
    }
    Shortcut {
        sequence: "Ctrl+Shift+A"
        enabled: desk.liveMode
        onActivated: {
            if (desk.liveSnapshot.view === "apps") {
                var restored = desk.liveController.closeAppsView()
                if (desk.editor) desk.editor.text = restored
            } else {
                desk.liveController.openAppsView(desk.editor ? desk.editor.text : "")
            }
            if (desk.editor) desk.editor.forceActiveFocus()
        }
    }
    Shortcut {
        sequence: "Meta+Shift+A"
        enabled: desk.liveMode
        onActivated: {
            if (desk.liveSnapshot.view === "apps") {
                var restored = desk.liveController.closeAppsView()
                if (desk.editor) desk.editor.text = restored
            } else {
                desk.liveController.openAppsView(desk.editor ? desk.editor.text : "")
            }
            if (desk.editor) desk.editor.forceActiveFocus()
        }
    }
    Shortcut {
        sequences: ["Ctrl+,", "Meta+,"]
        enabled: desk.liveMode
        onActivated: {
            if (desk.liveController) {
                if (desk.liveSnapshot.view === "settings") desk.liveController.closeSettings()
                else desk.liveController.openSettings()
            }
        }
    }
    Shortcut {
        sequence: "Ctrl+L"
        enabled: desk.hasWorkbench
        onActivated: { if (desk.expanded) desk.foldWorkbench(); else desk.openWorkbench() }
    }
    Shortcut {
        sequence: "Meta+L"
        enabled: desk.hasWorkbench
        onActivated: { if (desk.expanded) desk.foldWorkbench(); else desk.openWorkbench() }
    }
    Shortcut {
        sequence: "Ctrl+Y"
        enabled: desk.liveMode && desk.liveSnapshot.view === "finder" && desk.selectedFinderIndex >= 0 && desk.selectedFinderIndex < (desk.visibleFinderHits || []).length
        onActivated: desk.liveController.previewSelectedHit(desk.selectedFinderIndex)
    }
    Shortcut {
        sequence: "Meta+Y"
        enabled: desk.liveMode && desk.liveSnapshot.view === "finder" && desk.selectedFinderIndex >= 0 && desk.selectedFinderIndex < (desk.visibleFinderHits || []).length
        onActivated: desk.liveController.previewSelectedHit(desk.selectedFinderIndex)
    }
    Shortcut {
        sequence: "Tab"
        enabled: desk.liveMode && desk.liveSnapshot.view === "finder" && desk.selectedFinderIndex >= 0 && desk.selectedFinderIndex < (desk.visibleFinderHits || []).length
        onActivated: {
            var idx = desk.selectedFinderIndex
            desk.selectedFinderIndex = -1
            desk.liveController.adoptSelectedHit(idx, desk.editor ? desk.editor.text : "")
            if (desk.editor) desk.editor.forceActiveFocus()
        }
    }
}
