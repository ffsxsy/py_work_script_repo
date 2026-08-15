import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Material
import QtQuick.Layouts
import PmsUi

Item {
    id: root
    required property var model
    property string searchQuery: ""

    function labelHit(text) {
        const q = String(root.searchQuery).trim().toLowerCase()
        if (!q)
            return false
        const t = String(text).toLowerCase()
        if (t.indexOf(q) >= 0)
            return true
        return q === "1827" || q === "0x1827" || q === "pccommand" || q === "pc"
    }

    component CompactCheck: CheckBox {
        id: chkRoot
        font.pixelSize: 11
        padding: 0
        topPadding: 0
        bottomPadding: 0
        leftPadding: 2
        spacing: 4
        implicitHeight: 22
        Layout.fillWidth: true
        Layout.preferredHeight: 22
        property bool hit: root.labelHit(text)
        property string tip: {
            const t = root.model.fieldTip(text)
            return t === undefined || t === null ? "" : String(t)
        }
        background: Rectangle {
            radius: Theme.radiusSm
            color: chkRoot.hit ? Theme.cellSearchHit : "transparent"
            border.color: chkRoot.hit ? Theme.cellSearchHitBorder : "transparent"
            border.width: chkRoot.hit ? 1 : 0
        }
        contentItem: Text {
            text: chkRoot.text
            font.pixelSize: chkRoot.font.pixelSize
            font.bold: chkRoot.hit
            color: chkRoot.enabled ? Theme.textPrimary : Theme.textMuted
            leftPadding: chkRoot.indicator.width + chkRoot.spacing
            verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight
            wrapMode: Text.NoWrap
        }
        HoverHandler { id: chkHover }
        ToolTip.visible: chkHover.hovered && chkRoot.tip.length > 0
        ToolTip.text: chkRoot.tip
        ToolTip.delay: 280
    }

    component SpinField: ColumnLayout {
        id: spinRoot
        property alias label: lbl.text
        property int from: 0
        property int to: 100
        property int value: 0
        property bool hit: root.labelHit(label)
        property string tip: {
            const t = root.model.fieldTip(label)
            return t === undefined || t === null ? "" : String(t)
        }
        signal valueEdited(int v)

        spacing: 1
        Layout.fillWidth: true
        Layout.minimumWidth: 56
        Rectangle {
            Layout.fillWidth: true
            radius: Theme.radiusSm
            color: spinRoot.hit ? Theme.cellSearchHit : "transparent"
            border.color: spinRoot.hit ? Theme.cellSearchHitBorder : "transparent"
            border.width: spinRoot.hit ? 1 : 0
            implicitHeight: lbl.implicitHeight + 2
            Label {
                id: lbl
                anchors.fill: parent
                anchors.margins: 1
                color: spinRoot.hit ? Theme.textPrimary : Theme.textSecondary
                font.pixelSize: 10
                font.bold: spinRoot.hit
                elide: Text.ElideRight
            }
            HoverHandler { id: spinLblHover }
            ToolTip.visible: spinLblHover.hovered && spinRoot.tip.length > 0
            ToolTip.text: spinRoot.tip
            ToolTip.delay: 280
        }
        TextField {
            id: field
            text: String(spinRoot.value)
            font.pixelSize: 12
            font.bold: spinRoot.hit
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            selectByMouse: true
            implicitHeight: 28
            leftPadding: 4
            rightPadding: 4
            topPadding: 2
            bottomPadding: 2
            Layout.fillWidth: true
            Layout.minimumWidth: 56
            background: Rectangle {
                radius: Theme.radiusSm
                color: spinRoot.hit ? Theme.cellSearchHit : Theme.surfaceHigh
                border.color: spinRoot.hit ? Theme.cellSearchHitBorder : Theme.border
                border.width: spinRoot.hit ? 2 : 1
            }
            HoverHandler { id: spinFieldHover }
            ToolTip.visible: spinFieldHover.hovered && spinRoot.tip.length > 0
            ToolTip.text: spinRoot.tip
            ToolTip.delay: 280
            validator: IntValidator {
                bottom: spinRoot.from
                top: spinRoot.to
            }
            onEditingFinished: {
                const parsed = parseInt(text, 10)
                if (Number.isNaN(parsed)) {
                    text = String(spinRoot.value)
                    return
                }
                const clamped = Math.max(spinRoot.from, Math.min(spinRoot.to, parsed))
                text = String(clamped)
                if (clamped !== spinRoot.value)
                    spinRoot.valueEdited(clamped)
            }
        }
        onValueChanged: {
            if (!field.activeFocus)
                field.text = String(value)
        }
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: Theme.spaceSm

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: false
            spacing: Theme.spaceXs
            SpinField {
                label: "TraceDS"
                from: 0; to: 255
                value: root.model.traceNumDownSample
                onValueEdited: (v) => { root.model.traceNumDownSample = v }
            }
            SpinField {
                label: "Select"
                from: 0; to: 255
                value: root.model.select
                onValueEdited: (v) => { root.model.select = v }
            }
            SpinField {
                label: "Dcmd_Pcmd"
                from: -32768; to: 32767
                value: root.model.fsw
                onValueEdited: (v) => { root.model.fsw = v }
            }
            SpinField {
                label: "Qcmd"
                from: -900; to: 900
                value: root.model.phase
                onValueEdited: (v) => { root.model.phase = v }
            }
            SpinField {
                label: "TraceGrp"
                from: 0; to: 7
                value: root.model.traceGroup
                onValueEdited: (v) => { root.model.traceGroup = v }
            }
            Button {
                text: "发送"
                enabled: root.model.busReady
                Layout.alignment: Qt.AlignBottom
                Layout.preferredWidth: 64
                Layout.minimumWidth: 56
                Layout.preferredHeight: 28
                Layout.minimumHeight: 28
                Layout.fillWidth: false
                onClicked: root.model.pulseSend()
                background: Rectangle {
                    radius: Theme.radiusSm
                    color: {
                        if (!parent.enabled)
                            return Theme.cellActionDisabled
                        return parent.down ? Theme.pulseGreenDim : Theme.pulseGreen
                    }
                }
                contentItem: Text {
                    text: parent.text
                    color: parent.enabled ? "white" : Theme.textMuted
                    font.bold: true
                    font.pixelSize: Theme.fontBody
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
                HoverHandler { id: pcSendHover }
                ToolTip.visible: pcSendHover.hovered
                ToolTip.text: "发送 0x1827"
                ToolTip.delay: 280
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumHeight: 120
            spacing: Theme.spaceSm

            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.preferredWidth: 2
                radius: Theme.radiusSm
                color: Theme.bg
                border.color: Theme.border

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: Theme.spaceSm
                    spacing: Theme.spaceSm
                    Label {
                        text: "RunMode"
                        font.bold: true
                        color: Theme.primary
                        font.pixelSize: Theme.fontCaption
                        background: Rectangle {
                            visible: root.labelHit("RunMode")
                            color: Theme.cellSearchHit
                            radius: Theme.radiusSm
                            border.color: Theme.cellSearchHitBorder
                        }
                    }
                    ComboBox {
                        id: modeBox
                        Layout.fillWidth: true
                        implicitHeight: 32
                        model: root.model.runModeLabels
                        currentIndex: root.model.runMode
                        onActivated: (idx) => { root.model.runMode = idx }
                        delegate: ItemDelegate {
                            id: modeItem
                            width: modeBox.popup.width
                            implicitHeight: 22
                            required property string modelData
                            readonly property bool isHover: modeBox.highlightedIndex === index
                            contentItem: Text {
                                text: modeItem.modelData
                                color: modeItem.isHover ? Theme.accent : Theme.textPrimary
                                font.pixelSize: Theme.fontCaption
                                leftPadding: Theme.spaceSm
                                verticalAlignment: Text.AlignVCenter
                                elide: Text.ElideRight
                            }
                            background: Rectangle {
                                color: modeItem.isHover ? Theme.surfaceHover : Theme.surfaceHigh
                            }
                        }
                        background: Rectangle {
                            radius: Theme.radiusSm
                            color: root.labelHit(modeBox.currentText) || root.labelHit("RunMode")
                                   ? Theme.cellSearchHit : Theme.surfaceHigh
                            border.color: root.labelHit(modeBox.currentText) || root.labelHit("RunMode")
                                          ? Theme.cellSearchHitBorder : Theme.border
                            border.width: root.labelHit(modeBox.currentText) || root.labelHit("RunMode") ? 2 : 1
                        }
                        HoverHandler { id: modeHover }
                        ToolTip.visible: modeHover.hovered
                        ToolTip.text: {
                            const t = root.model.fieldTip("RunMode")
                            return t === undefined || t === null ? "" : String(t)
                        }
                        ToolTip.delay: 280
                        Connections {
                            target: root.model
                            function onRunModeChanged() {
                                if (modeBox.currentIndex !== root.model.runMode)
                                    modeBox.currentIndex = root.model.runMode
                            }
                        }
                    }
                    Item { Layout.fillHeight: true }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.preferredWidth: 3
                radius: Theme.radiusSm
                color: Theme.bg
                border.color: Theme.border

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: Theme.spaceSm
                    spacing: Theme.spaceXs
                    Label {
                        text: "Flags"
                        font.bold: true
                        color: Theme.primary
                        font.pixelSize: Theme.fontCaption
                    }
                    GridLayout {
                        Layout.fillWidth: true
                        Layout.alignment: Qt.AlignTop
                        columns: 2
                        columnSpacing: Theme.spaceSm
                        rowSpacing: 2
                        CompactCheck {
                            text: "TraceScope"
                            checked: root.model.traceScope
                            onToggled: root.model.traceScope = checked
                        }
                        CompactCheck {
                            text: "BoardTest"
                            checked: root.model.boardTest
                            onToggled: root.model.boardTest = checked
                        }
                        CompactCheck {
                            text: "MasterReset"
                            checked: root.model.masterReset
                            onToggled: root.model.masterReset = checked
                        }
                        CompactCheck {
                            text: "UseACBVoltage"
                            checked: root.model.useExtVolt
                            onToggled: root.model.useExtVolt = checked
                        }
                        CompactCheck {
                            text: "DisableSVM"
                            checked: root.model.disableSvm
                            onToggled: root.model.disableSvm = checked
                        }
                        CompactCheck {
                            text: "DisableVmidReg"
                            checked: root.model.disableVmidReg
                            onToggled: root.model.disableVmidReg = checked
                        }
                        CompactCheck {
                            text: "ResetIacDamp"
                            checked: root.model.resetIacDamp
                            onToggled: root.model.resetIacDamp = checked
                        }
                        CompactCheck {
                            text: "ResetIacHarmAtt"
                            checked: root.model.resetIacHarmAtt
                            onToggled: root.model.resetIacHarmAtt = checked
                        }
                        CompactCheck {
                            text: "ResetIacDcAtt"
                            checked: root.model.resetIacDcAtt
                            onToggled: root.model.resetIacDcAtt = checked
                        }
                    }
                    Item { Layout.fillHeight: true }
                }
            }
        }
    }
}
