import QtQuick

// One place for the paper/sage palette. Each desk creates one and re-exports the names on its
// root (`desk.ink`, `desk.accent`, ...), so the other files in this folder keep reading `desk.*`.
QtObject {
    property bool darkMode: false

    readonly property color ink: darkMode ? "#eef0e9" : "#2c302a"
    readonly property color muted: darkMode ? "#b7bdaf" : "#62695e"
    readonly property color paperColor: darkMode ? "#272d25" : "#fdfdf9"
    readonly property color inputColor: darkMode ? "#2b3227" : "#fdfefb"
    readonly property color backingColor: darkMode ? "#3a4332" : "#e8ece1"
    readonly property color edge: darkMode ? "#424d39" : "#e0e5d8"
    readonly property color accent: darkMode ? "#c0d2a7" : "#4f6740"
    readonly property color accentText: darkMode ? "#24301b" : "#fafcf5"
    readonly property color warningInk: darkMode ? "#e4bb89" : "#916329"
    readonly property color pdfInk: darkMode ? "#dbaa9f" : "#a15e50"
    readonly property color selectedSurface: darkMode ? "#2d3727" : "#edf4e8"
    readonly property color selectedEdge: darkMode ? "#46593d" : "#b5ceaa"
    readonly property color utilitySurface: darkMode ? "#242820" : "#f0f4ea"
    readonly property color hoverSurface: darkMode ? "#2a3125" : "#f1f6ed"
}
