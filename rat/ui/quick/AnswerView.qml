import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ColumnLayout {
    id: answerView
    property alias answerText: answerText
    visible: desk.liveMode && desk.liveSnapshot.view === "answer"
    Layout.fillWidth: true
    spacing: desk.emptyCancelledAnswer ? 8 : 12

                    ColumnLayout {
                        visible: desk.liveSnapshot.view === "answer"
                        Layout.fillWidth: true
                        spacing: 8
                        Rectangle {
                            id: answerQuestionCard
                            objectName: "answerQuestionCard"
                            Layout.fillWidth: true
                            implicitHeight: questionCardCol.implicitHeight + 18
                            radius: desk.cardRadius
                            color: desk.utilitySurface
                            border.width: answerQuestion.visualFocus ? 1.5 : 1
                            border.color: answerQuestion.visualFocus ? desk.accent : desk.edge

                            Rectangle {
                                x: 0
                                y: 8
                                width: 3.5
                                height: Math.max(14, parent.height - 16)
                                radius: 2
                                color: desk.accent
                            }

                            ColumnLayout {
                                id: questionCardCol
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.top: parent.top
                                anchors.leftMargin: 13
                                anchors.rightMargin: 11
                                anchors.topMargin: 8
                                spacing: 3

                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 6
                                    Label {
                                        text: "BẠN HỎI"
                                        font.pixelSize: 11
                                        font.weight: Font.DemiBold
                                        font.letterSpacing: 0.5
                                        color: desk.accent
                                    }
                                    Item { Layout.fillWidth: true }
                                    DeskIcon {
                                        visible: (desk.liveSnapshot.userQuery || "").length > 48
                                        name: desk.answerQuestionOpen ? "chevron-up" : "chevron-down"
                                        color: desk.muted
                                        width: 12
                                        height: 12
                                        Layout.preferredWidth: 12
                                        Layout.preferredHeight: 12
                                    }
                                }

                                Button {
                                    id: answerQuestion
                                    objectName: "answerQuestion"
                                    Layout.fillWidth: true
                                    padding: 0
                                    leftPadding: 0
                                    rightPadding: 0
                                    hoverEnabled: true
                                    Accessible.name: "Câu hỏi: " + (desk.liveSnapshot.userQuery || "")
                                    Accessible.description: "Mở hoặc thu câu hỏi đầy đủ"
                                    onClicked: desk.answerQuestionOpen = !desk.answerQuestionOpen
                                    contentItem: Label {
                                        leftPadding: 0
                                        text: desk.liveSnapshot.userQuery || ""
                                        textFormat: Text.PlainText
                                        font.pixelSize: 14
                                        font.weight: Font.Medium
                                        color: desk.ink
                                        wrapMode: desk.answerQuestionOpen ? Text.Wrap : Text.NoWrap
                                        elide: desk.answerQuestionOpen ? Text.ElideNone : Text.ElideRight
                                    }
                                    background: Item {}
                                    // ToolTip.visible
                                    ToolTip.delay: 600
                                    ToolTip.text: desk.liveSnapshot.userQuery || ""
                                }
                            }
                        }

                        Rectangle {
                            id: evidenceProcessCard
                            objectName: "evidenceProcessCard"
                            visible: Boolean(desk.liveSnapshot.processSteps && desk.liveSnapshot.processSteps.length > 0)
                            Layout.fillWidth: true
                            implicitHeight: evidenceProcessCol.implicitHeight + 12
                            radius: desk.cardRadius
                            color: desk.utilitySurface
                            border.width: 1
                            border.color: desk.edge

                            ColumnLayout {
                                id: evidenceProcessCol
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.top: parent.top
                                anchors.leftMargin: 8
                                anchors.rightMargin: 8
                                anchors.topMargin: 6
                                spacing: 6

                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 4

                                    Repeater {
                                        id: processStepsRepeater
                                        objectName: "processStepsRepeater"
                                        model: desk.liveSnapshot.processSteps || []

                                        RowLayout {
                                            spacing: 4
                                            Rectangle {
                                                radius: 4
                                                color: (modelData.status === "verified_fail") ? Qt.rgba(desk.warningInk.r, desk.warningInk.g, desk.warningInk.b, 0.14) :
                                                       (modelData.status === "unverified") ? desk.utilitySurface :
                                                       desk.selectedSurface
                                                border.width: 1
                                                border.color: (modelData.status === "verified_fail") ? desk.warningInk :
                                                              (modelData.status === "unverified") ? desk.edge :
                                                              desk.selectedEdge
                                                implicitHeight: 20
                                                implicitWidth: chipInnerRow.implicitWidth + 8
                                                RowLayout {
                                                    id: chipInnerRow
                                                    anchors.centerIn: parent
                                                    spacing: 3
                                                    DeskIcon {
                                                        name: modelData.iconName || "check"
                                                        color: (modelData.status === "verified_fail") ? desk.warningInk :
                                                               (modelData.status === "unverified") ? desk.muted :
                                                               desk.accent
                                                        width: 10
                                                        height: 10
                                                        Layout.preferredWidth: 10
                                                        Layout.preferredHeight: 10
                                                    }
                                                    Label {
                                                        text: evidenceProcessCard.width < 340 ? (modelData.shortTitle || "") : (modelData.fullTitle || "")
                                                        font.pixelSize: 11
                                                        font.weight: Font.Medium
                                                        color: (modelData.status === "verified_fail") ? desk.warningInk :
                                                               (modelData.status === "unverified") ? desk.muted :
                                                               desk.accent
                                                    }
                                                }
                                            }

                                            Label {
                                                visible: index < (processStepsRepeater.count - 1)
                                                text: "→"
                                                color: desk.muted
                                                font.pixelSize: 11
                                            }
                                        }
                                    }

                                    Item { Layout.fillWidth: true }

                                    QuietButton {
                                        id: processDetailsToggle
                                        objectName: "processDetailsToggle"
                                        text: evidenceProcessCard.width < 340 ? "" : "Chi tiết"
                                        trailingIconName: desk.processDetailsOpen ? "chevron-up" : "chevron-down"
                                        trailingIconSize: 10
                                        topPadding: 2
                                        bottomPadding: 2
                                        leftPadding: 4
                                        rightPadding: 4
                                        font.pixelSize: 11
                                        Accessible.name: (desk.processDetailsOpen ? "Thu gọn" : "Xem") + " chi tiết đối chiếu"
                                        Accessible.role: Accessible.Button
                                        checkable: true
                                        checked: desk.processDetailsOpen
                                        onClicked: desk.processDetailsOpen = !desk.processDetailsOpen
                                    }
                                }

                                ColumnLayout {
                                    id: processDetailsContent
                                    objectName: "processDetailsContent"
                                    visible: desk.processDetailsOpen
                                    Layout.fillWidth: true
                                    spacing: 4

                                    Rectangle { Layout.fillWidth: true; height: 1; color: desk.edge; opacity: 0.6 }

                                    RowLayout {
                                        Layout.fillWidth: true
                                        spacing: 6
                                        Label {
                                            text: "Mục tiêu tìm:"
                                            font.pixelSize: 12
                                            font.weight: Font.Medium
                                            color: desk.muted
                                        }
                                        Label {
                                            text: desk.liveSnapshot.userQuery || "Trích xuất thông tin đối chiếu"
                                            font.pixelSize: 12
                                            color: desk.ink
                                            Layout.fillWidth: true
                                            elide: Text.ElideRight
                                        }
                                    }

                                    RowLayout {
                                        Layout.fillWidth: true
                                        spacing: 6
                                        Label {
                                            text: "Phạm vi đọc:"
                                            font.pixelSize: 12
                                            font.weight: Font.Medium
                                            color: desk.muted
                                        }
                                        Label {
                                            text: desk.liveSnapshot.answerReadScope || (desk.liveSnapshot.fileName ? desk.liveSnapshot.fileName + " · Toàn văn / Đoạn trích" : "Tài liệu được chọn")
                                            font.pixelSize: 12
                                            color: desk.ink
                                            Layout.fillWidth: true
                                            elide: Text.ElideRight
                                        }
                                    }

                                    RowLayout {
                                        Layout.fillWidth: true
                                        spacing: 6
                                        Label {
                                            text: "Kiểm chứng:"
                                            font.pixelSize: 12
                                            font.weight: Font.Medium
                                            color: desk.muted
                                        }
                                        Label {
                                            text: desk.liveSnapshot.answerVerification === "PASS" ? "Đạt kiểm tra đối chiếu nguồn gốc" : (desk.liveSnapshot.answerVerification === "FAIL" ? "Kiểm tra không khớp nội dung" : "Tổng hợp từ tài liệu")
                                            font.pixelSize: 12
                                            color: desk.liveSnapshot.answerVerification === "FAIL" ? desk.warningInk : desk.accent
                                            font.weight: Font.Medium
                                            Layout.fillWidth: true
                                        }
                                    }

                                    Repeater {
                                        model: desk.liveSnapshot.processSteps || []
                                        ColumnLayout {
                                            Layout.fillWidth: true
                                            spacing: 2
                                            visible: Boolean(modelData.detail || modelData.thought)
                                            RowLayout {
                                                Layout.fillWidth: true
                                                spacing: 6
                                                Label {
                                                    text: (modelData.shortTitle || "Bước") + ":"
                                                    font.pixelSize: 12
                                                    font.weight: Font.Medium
                                                    color: desk.muted
                                                }
                                                Label {
                                                    text: modelData.detail || ""
                                                    font.pixelSize: 12
                                                    color: desk.ink
                                                    Layout.fillWidth: true
                                                    elide: Text.ElideRight
                                                }
                                            }
                                            Label {
                                                visible: Boolean(modelData.thought)
                                                text: modelData.thought || ""
                                                font.pixelSize: 12
                                                font.italic: true
                                                color: desk.muted
                                                Layout.fillWidth: true
                                                wrapMode: Text.Wrap
                                                leftPadding: 12
                                            }
                                        }
                                    }
                                }
                            }
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 6
                            Label {
                                text: "CHUỘT TRẢ LỜI"
                                font.pixelSize: 11
                                font.weight: Font.DemiBold
                                font.letterSpacing: 0.5
                                color: desk.muted
                            }
                            Label {
                                id: answerDocSep
                                visible: Boolean(answerDocumentLabel.text)
                                text: "·"
                                font.pixelSize: 12
                                color: desk.muted
                                opacity: 0.7
                            }
                            Label {
                                id: answerDocumentLabel
                                objectName: "answerDocumentLabel"
                                visible: Boolean(text)
                                text: {
                                    if (desk.liveSnapshot.answerSources && desk.liveSnapshot.answerSources.length > 0 && desk.liveSnapshot.answerSources[0].title) {
                                        return desk.liveSnapshot.answerSources[0].title
                                    }
                                    return desk.liveSnapshot.fileName || ""
                                }
                                font.pixelSize: 12
                                font.weight: Font.Medium
                                color: desk.accent
                                elide: Text.ElideMiddle
                                Layout.maximumWidth: resultPaper.width < 500 ? 160 : 260
                                HoverHandler { id: docLabelHover }
                                ToolTip.visible: docLabelHover.hovered
                                ToolTip.text: answerDocumentLabel.text
                            }
                            Label {
                                visible: Boolean(answerStatus.text)
                                text: "·"
                                font.pixelSize: 12
                                color: desk.muted
                                opacity: 0.7
                            }
                            Label {
                                id: answerStatus
                                objectName: "answerStatus"
                                visible: Boolean(text)
                                Layout.fillWidth: true
                                text: {
                                    if (desk.liveSnapshot.answerSources && desk.liveSnapshot.answerSources.length > 0 && desk.liveSnapshot.answerVerification === "UNKNOWN") {
                                        return (desk.liveSnapshot.answerReadScope ? desk.liveSnapshot.answerReadScope + " · " : "") + "Tổng hợp từ tài liệu"
                                    }
                                    return (desk.liveSnapshot.answerReadScope ? desk.liveSnapshot.answerReadScope + " · " : "") + (desk.liveSnapshot.status || "")
                                }
                                textFormat: Text.PlainText
                                wrapMode: Text.NoWrap
                                elide: Text.ElideRight
                                color: desk.muted
                                font.pixelSize: 12
                            }
                            Item { visible: !Boolean(answerStatus.text); Layout.fillWidth: true }
                            Rectangle {
                                visible: desk.liveSnapshot.answerVerification === "PASS" || desk.liveSnapshot.answerVerification === "FAIL"
                                radius: 4
                                color: desk.liveSnapshot.answerVerification === "FAIL" ? Qt.rgba(desk.warningInk.r, desk.warningInk.g, desk.warningInk.b, 0.14) : desk.selectedSurface
                                border.width: 1
                                border.color: desk.liveSnapshot.answerVerification === "FAIL" ? desk.warningInk : desk.selectedEdge
                                implicitWidth: verifBadgeLabel.implicitWidth + 10
                                implicitHeight: 18
                                Label {
                                    id: verifBadgeLabel
                                    anchors.centerIn: parent
                                    text: desk.liveSnapshot.answerVerification === "PASS" ? "Đạt kiểm tra" : "Chưa đạt"
                                    font.pixelSize: 11
                                    font.weight: Font.Medium
                                    color: desk.liveSnapshot.answerVerification === "FAIL" ? desk.warningInk : desk.accent
                                }
                            }
                        }
                    }
                    TextArea {
                        id: answerText
                        objectName: "answerText"
                        visible: desk.liveSnapshot.view === "answer" && !desk.emptyCancelledAnswer
                        Layout.fillWidth: true
                        Layout.preferredHeight: contentHeight
                        text: desk.displayedAnswerHtml
                        textFormat: TextEdit.RichText
                        wrapMode: TextEdit.Wrap
                        readOnly: true
                        selectByMouse: true
                        persistentSelection: true
                        color: desk.ink
                        selectionColor: desk.accent
                        selectedTextColor: desk.accentText
                        font.pixelSize: 14
                        padding: 0
                        background: null
                        Accessible.name: "Câu trả lời của trợ lý"
                    }
                    Rectangle {
                        id: evidenceSourceCard
                        objectName: "evidenceSourceCard"
                        visible: desk.liveSnapshot.view === "answer" && !desk.emptyCancelledAnswer && (desk.liveSnapshot.answerSources || []).length > 0
                        Layout.fillWidth: true
                        implicitHeight: evidenceSourceCol.implicitHeight + 18
                        radius: desk.cardRadius
                        color: desk.utilitySurface
                        border.width: 1
                        border.color: desk.edge

                        ColumnLayout {
                            id: evidenceSourceCol
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.top: parent.top
                            anchors.leftMargin: 12
                            anchors.rightMargin: 12
                            anchors.topMargin: 10
                            spacing: 8

                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 6

                                DeskIcon { name: "file"; color: desk.accent; width: 13; height: 13; Layout.preferredWidth: 13; Layout.preferredHeight: 13 }

                                Label {
                                    id: evidenceSourceTitle
                                    objectName: "evidenceSourceTitle"
                                    text: {
                                        if (desk.liveSnapshot.answerSources && desk.liveSnapshot.answerSources.length > 0) {
                                            const s = desk.liveSnapshot.answerSources[0]
                                            return "Nguồn: " + (s.title || desk.liveSnapshot.fileName || "Tài liệu") + (s.page > 0 ? (" · Trang " + s.page) : "") + (s.section ? (" · " + s.section) : "")
                                        }
                                        return "Nguồn: " + (desk.liveSnapshot.fileName || "")
                                    }
                                    font.pixelSize: 12
                                    font.weight: Font.Medium
                                    color: desk.ink
                                    elide: Text.ElideMiddle
                                    Layout.fillWidth: true
                                }

                                QuietButton {
                                    id: expandContextButton
                                    objectName: "expandContextButton"
                                    text: resultPaper.width < 520 ? "" : (desk.contextExpanded ? "Thu gọn" : (resultPaper.width < 620 ? "+ Ngữ cảnh" : "Mở rộng ngữ cảnh"))
                                    iconName: desk.contextExpanded ? "minus" : "plus"
                                    iconSize: 11
                                    topPadding: 3
                                    bottomPadding: 3
                                    leftPadding: resultPaper.width < 520 ? 4 : 6
                                    rightPadding: resultPaper.width < 520 ? 4 : 6
                                    font.pixelSize: 12
                                    Accessible.name: desk.contextExpanded ? "Thu gọn về đoạn trích ngắn" : "Mở rộng ngữ cảnh xung quanh đoạn trích"
                                    Accessible.role: Accessible.Button
                                    ToolTip.visible: hovered
                                    ToolTip.text: desk.contextExpanded ? "Thu gọn về đoạn trích ngắn" : "Mở rộng ngữ cảnh xung quanh đoạn trích"
                                    onClicked: {
                                        if (!desk.contextExpanded && desk.liveController)
                                            desk.expandedEvidenceText = desk.liveController.getExpandedContext(0)
                                        desk.contextExpanded = !desk.contextExpanded
                                    }
                                }

                                QuietButton {
                                    id: copyCitationButton
                                    objectName: "copyCitationButton"
                                    text: resultPaper.width < 520 ? "" : (desk.sourceCopied ? "Đã chép" : (resultPaper.width < 620 ? "Chép" : "Chép trích dẫn"))
                                    iconName: desk.sourceCopied ? "check" : "copy"
                                    iconSize: 11
                                    topPadding: 3
                                    bottomPadding: 3
                                    leftPadding: resultPaper.width < 520 ? 4 : 6
                                    rightPadding: resultPaper.width < 520 ? 4 : 6
                                    font.pixelSize: 12
                                    Accessible.name: "Sao chép trích dẫn và nguồn"
                                    Accessible.role: Accessible.Button
                                    ToolTip.visible: hovered
                                    ToolTip.text: desk.sourceCopied ? "Đã sao chép vào bộ nhớ tạm" : "Sao chép trích dẫn và nguồn"
                                    onClicked: {
                                        const citation = evidenceSourceSnippet.text + (evidenceSourceTitle.text ? ("\n\n— " + evidenceSourceTitle.text) : "")
                                        if (desk.liveController.copyCitation(citation)) {
                                            desk.sourceCopied = true
                                            sourceCopyFeedback.restart()
                                        }
                                    }
                                }

                                QuietButton {
                                    id: openExternalPdfButton
                                    objectName: "openExternalPdfButton"
                                    text: resultPaper.width < 520 ? "" : (resultPaper.width < 620 ? "Mở PDF" : "Mở PDF gốc")
                                    iconName: resultPaper.width < 520 ? "external" : ""
                                    trailingIconName: resultPaper.width < 520 ? "" : "external"
                                    iconSize: 11
                                    trailingIconSize: 11
                                    topPadding: 3
                                    bottomPadding: 3
                                    leftPadding: resultPaper.width < 520 ? 4 : 6
                                    rightPadding: resultPaper.width < 520 ? 4 : 6
                                    font.pixelSize: 12
                                    Accessible.name: "Mở tài liệu bằng ứng dụng PDF bên ngoài"
                                    Accessible.role: Accessible.Button
                                    ToolTip.visible: hovered
                                    ToolTip.text: "Mở tài liệu bằng ứng dụng PDF bên ngoài"
                                    onClicked: desk.liveController.openOriginal()
                                }
                            }

                            Rectangle { Layout.fillWidth: true; height: 1; color: desk.edge; opacity: 0.6 }

                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 8

                                Rectangle {
                                    Layout.preferredWidth: 3
                                    Layout.fillHeight: true
                                    radius: 1.5
                                    color: desk.accent
                                    opacity: 0.8
                                }

                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 4

                                    Rectangle {
                                        visible: desk.contextExpanded
                                        radius: 4
                                        color: desk.selectedSurface
                                        border.width: 1
                                        border.color: desk.selectedEdge
                                        implicitHeight: 18
                                        implicitWidth: expandedTagLabel.implicitWidth + 8
                                        Label {
                                            id: expandedTagLabel
                                            anchors.centerIn: parent
                                            text: "Ngữ cảnh mở rộng"
                                            font.pixelSize: 11
                                            font.weight: Font.Medium
                                            color: desk.accent
                                        }
                                    }

                                    Label {
                                        id: evidenceSourceSnippet
                                        objectName: "evidenceSourceSnippet"
                                        Layout.fillWidth: true
                                        text: {
                                            var raw = "Chưa có đoạn nguồn cho tham chiếu này."
                                            if (desk.liveSnapshot.answerSources && desk.liveSnapshot.answerSources.length > 0) {
                                                const s = desk.liveSnapshot.answerSources[0]
                                                if (desk.contextExpanded) {
                                                    if (s.extendedSnippet && s.extendedSnippet.length > (s.snippet || "").length) {
                                                        raw = s.extendedSnippet
                                                    } else if (desk.expandedEvidenceText) {
                                                        raw = desk.expandedEvidenceText
                                                    } else {
                                                        raw = s.snippet || raw
                                                    }
                                                } else {
                                                    raw = s.snippet || raw
                                                }
                                            }
                                            return desk.cleanSnippetText(raw)
                                        }
                                        font.pixelSize: 12
                                        lineHeight: 1.3
                                        color: desk.ink
                                        wrapMode: Text.Wrap
                                        textFormat: Text.PlainText
                                    }
                                }
                            }
                        }
                    }
                    ColumnLayout {
                        id: answerReferences
                        objectName: "answerReferences"
                        visible: desk.liveSnapshot.view === "answer" && !desk.emptyCancelledAnswer
                        Layout.fillWidth: true
                        spacing: 8
                        Item { Layout.preferredHeight: 4 }
                        Rectangle { Layout.fillWidth: true; height: 1; color: desk.edge }
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 6
                            QuietButton {
                                objectName: "answerSourcesToggle"
                                visible: (desk.liveSnapshot.answerSources || []).length > 0
                                text: (desk.liveSnapshot.answerSources || []).length + " tham chiếu"
                                iconName: desk.answerSourcesOpen ? "chevron-down" : "chevron-right"
                                iconSize: 13
                                leftPadding: 0
                                topPadding: 4
                                bottomPadding: 4
                                Accessible.name: (desk.answerSourcesOpen ? "Thu" : "Mở") + " tham chiếu của lượt trả lời"
                                Accessible.role: Accessible.Button
                                checkable: true
                                checked: desk.answerSourcesOpen
                                onClicked: desk.answerSourcesOpen = !desk.answerSourcesOpen
                            }
                            Item { Layout.fillWidth: true }
                            Label {
                                objectName: "answerVerification"
                                text: desk.liveSnapshot.answerVerification === "PASS" ? "Đạt kiểm tra được báo cáo"
                                    : desk.liveSnapshot.answerVerification === "FAIL" ? "Kiểm tra chưa đạt" : "Chưa được xác minh"
                                color: desk.liveSnapshot.answerVerification === "FAIL" ? desk.warningInk : desk.muted
                                font.pixelSize: 12
                                wrapMode: Text.Wrap
                                Accessible.description: desk.liveSnapshot.answerVerification === "FAIL"
                                    ? "Bước kiểm tra báo câu trả lời chưa khớp với nguồn. Hãy mở nguồn để đối chiếu."
                                    : (desk.liveSnapshot.answerVerification !== "PASS" ? "Chưa có bước kiểm tra nào xác nhận câu trả lời này. Hãy mở nguồn để tự đối chiếu." : "")
                                HoverHandler { id: verificationHover }
                                ToolTip.visible: verificationHover.hovered && desk.liveSnapshot.answerVerification !== "PASS"
                                ToolTip.delay: 600
                                ToolTip.text: Accessible.description
                            }
                        }
                        ColumnLayout {
                            visible: desk.answerSourcesOpen
                            Layout.fillWidth: true
                            spacing: 8
                            Repeater {
                                model: desk.liveSnapshot.view === "answer" ? (desk.liveSnapshot.answerSources || []) : []
                                ColumnLayout {
                                    required property var modelData
                                    required property int index
                                    Layout.fillWidth: true
                                    spacing: 6
                                    RowLayout {
                                        Layout.fillWidth: true
                                        spacing: 8
                                        DeskIcon { name: "file"; color: desk.muted; Layout.preferredWidth: 14; Layout.preferredHeight: 14 }
                                        Label {
                                            text: modelData.title + (modelData.readScope ? " · " + modelData.readScope : "")
                                            textFormat: Text.PlainText
                                            font.pixelSize: 12
                                            color: desk.muted
                                            wrapMode: Text.Wrap
                                            Layout.fillWidth: true
                                        }
                                        QuietButton {
                                            objectName: "openAnswerSource_" + index
                                            visible: true
                                            enabled: Boolean(modelData.canOpen)
                                            text: modelData.label || (modelData.page > 0 ? ("Trang " + modelData.page) : "Chưa xác định trang")
                                            Accessible.name: (modelData.canOpen ? "Đọc trang " : "Tham chiếu: ") + text + ", " + modelData.title
                                            topPadding: 4
                                            bottomPadding: 4
                                            onClicked: {
                                                if (modelData.canOpen) {
                                                    if (desk.isSideBySidePdfActive) {
                                                        desk.liveController.previewPdfPageWithSnippet(modelData.page, modelData.snippet || "")
                                                    } else {
                                                        desk.liveController.openAnswerSource(index)
                                                    }
                                                }
                                            }
                                        }
                                    }
                                    PdfSnapshotCard {
                                        objectName: "sourceSnapshot_" + index
                                        activeSnapshot: desk.answerSourcesOpen && Boolean(modelData.canOpen)
                                        pdfPath: modelData.path || ""
                                        pdfPage: modelData.page || 0
                                        matchQuery: ""
                                        matchSnippet: modelData.snippet || ""
                                        maxCardHeight: 108
                                        Accessible.name: "Ảnh chụp tham chiếu trang PDF " + modelData.page + ", bấm để đọc trang"
                                        onActivated: {
                                            if (desk.isSideBySidePdfActive) {
                                                desk.liveController.previewPdfPageWithSnippet(modelData.page, modelData.snippet || "")
                                            } else {
                                                desk.liveController.openAnswerSource(index)
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }

}
