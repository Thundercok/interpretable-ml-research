import QtQuick

// One place for the paper/sage palette and design tokens.
// Each desk creates one and re-exports the names on its root (`desk.ink`, `desk.accent`, ...),
// so the other files in this folder keep reading `desk.*`.
QtObject {
    id: theme
    property bool darkMode: false
    property bool reduceMotion: false

    // Color tokens by role
    readonly property color ink: darkMode ? "#eef0e9" : "#2c302a"
    readonly property color muted: darkMode ? "#b7bdaf" : "#62695e"
    readonly property color paperColor: darkMode ? "#272d25" : "#fdfdf9"
    readonly property color inputColor: darkMode ? "#2b3227" : "#fdfefb"
    readonly property color windowColor: darkMode ? "#181c16" : "#f4f6f0"
    readonly property color backingColor: darkMode ? "#3a4332" : "#e8ece1"
    readonly property color labBackingColor: darkMode ? "#1f241c" : "#e8ece1"
    readonly property color edge: darkMode ? "#424d39" : "#e0e5d8"
    readonly property color accent: darkMode ? "#c0d2a7" : "#4f6740"
    readonly property color accentText: darkMode ? "#24301b" : "#fafcf5"
    readonly property color warningInk: darkMode ? "#e4bb89" : "#916329"
    readonly property color pdfInk: darkMode ? "#dbaa9f" : "#a15e50"
    readonly property color wrongInk: darkMode ? "#dbaa9f" : "#a15e50"
    readonly property color priorityHighInk: "#c0392b"
    readonly property color pureWhite: "#ffffff"
    readonly property color selectedSurface: darkMode ? "#2d3727" : "#edf4e8"
    readonly property color selectedEdge: darkMode ? "#46593d" : "#b5ceaa"
    readonly property color utilitySurface: darkMode ? "#242820" : "#f0f4ea"
    readonly property color hoverSurface: darkMode ? "#2a3125" : "#f1f6ed"
    readonly property color scrollThumb: darkMode ? "#6a7761" : "#809277"
    readonly property color scrollThumbHover: darkMode ? "#c8d4bf" : "#4a5940"
    readonly property color sheetPaperColor: "#fdfdf9"
    readonly property color speechEdge: "#dce3d4"
    readonly property color speechSelection: "#dbe7d1"

    // Error tokens
    readonly property color errorSurface: darkMode ? "#3d2522" : "#fbeeed"
    readonly property color errorEdge: darkMode ? "#6e3b35" : "#e8c5c0"
    readonly property color errorInk: darkMode ? "#f0aaa0" : "#a13d30"

    // Reading desk card & slot tokens
    readonly property color readingSlotBg: darkMode ? "#303329" : "#f9f5eb"
    readonly property color readingSlotBorder: darkMode ? "#74654a" : "#c9b58c"
    readonly property color readingCardBackBg: darkMode ? "#242720" : "#eee6d4"
    readonly property color readingCardBackBorder: darkMode ? "#58624e" : "#c4b595"
    readonly property color readingCardBackStroke: darkMode ? "#6e7960" : "#a89b7b"
    readonly property color readingCardFrontBorder: darkMode ? "#534b3b" : "#e4d8c0"
    readonly property color readingCardFrontStroke: darkMode ? "#c7b58e" : "#8a7144"
    readonly property color readingDraftBg: darkMode ? "#292c25" : "#fdfbf7"
    readonly property color readingDraftBorder: darkMode ? "#474b3e" : "#dfd7c5"
    readonly property color readingBadgeBg: darkMode ? "#343c2c" : "#e8efe1"
    readonly property color readingBadgeBorder: darkMode ? "#516244" : "#b8cca6"
    readonly property color readingDoneBg: darkMode ? "#23261f" : "#f4f6f0"
    readonly property color readingDoneBorder: darkMode ? "#555b4a" : "#c6cfbc"

    // Typography tokens (6 bậc: 11, 12, 13, 14, 18, 24)
    readonly property int textCaption: 11
    readonly property int textSmall: 12
    readonly property int textBody: 13
    readonly property int textLarge: 14
    readonly property int textTitle: 18
    readonly property int textDisplay: 24

    // Corner radius tokens (3 bậc: 4, 8, 12 + pill)
    readonly property int radiusSmall: 4
    readonly property int radiusMedium: 8
    readonly property int radiusLarge: 12

    // Spacing tokens (bội số 4: 4, 8, 12, 16, 24)
    readonly property int space1: 4
    readonly property int space2: 8
    readonly property int space3: 12
    readonly property int space4: 16
    readonly property int space6: 24

    // Motion durations (3 bậc, tắt hết khi reduceMotion)
    readonly property int motionFast: reduceMotion ? 0 : 70
    readonly property int motionBase: reduceMotion ? 0 : 140
    readonly property int motionSlow: reduceMotion ? 0 : 220
}
