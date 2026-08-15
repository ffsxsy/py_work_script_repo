import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Material
import QtQuick.Layouts
import PmsUi

Item {
    id: root
    required property var page

    readonly property string verifyTone: {
        const s = String(root.page.verifyStatus)
        if (s.indexOf("成功") >= 0)
            return "success"
        if (s.indexOf("失败") >= 0)
            return "danger"
        if (s.indexOf("中") >= 0)
            return "warning"
        return "neutral"
    }

    Timer {
        id: fitTimer
        interval: 0
        repeat: false
        onTriggered: {
            periodicView.forceLayout()
            paramView.forceLayout()
        }
    }

    function scheduleFit() {
        fitTimer.restart()
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.spaceSm
        spacing: Theme.spaceSm

        SectionCard {
            Layout.fillWidth: true
            Layout.fillHeight: false
            implicitHeight: commBody.implicitHeight + Theme.spaceMd * 2

            ColumnLayout {
                id: commBody
                anchors.fill: parent
                anchors.leftMargin: Theme.sectionBarWidth + Theme.spaceMd
                anchors.rightMargin: Theme.spaceMd
                anchors.topMargin: Theme.spaceMd
                anchors.bottomMargin: Theme.spaceMd
                spacing: Theme.spaceSm

            RowLayout {
                Layout.fillWidth: true
                spacing: Theme.spaceMd
                Label {
                    text: "通信"
                    font.bold: true
                    font.pixelSize: Theme.fontTitle
                    color: Theme.accent
                }
                Label {
                    text: "PCS ID (dd)"
                    color: Theme.textSecondary
                    font.pixelSize: Theme.fontCaption
                }
                TextField {
                    id: mcuIdField
                    implicitHeight: 32
                    implicitWidth: 64
                    horizontalAlignment: Text.AlignHCenter
                    selectByMouse: true
                    text: "0x" + Number(root.page.mcuId).toString(16).padStart(2, "0")
                    onEditingFinished: {
                        const raw = String(text).trim().replace(/^0x/i, "")
                        const parsed = parseInt(raw, 16)
                        if (Number.isNaN(parsed)) {
                            text = "0x" + Number(root.page.mcuId).toString(16).padStart(2, "0")
                            return
                        }
                        const clamped = Math.max(0, Math.min(255, parsed))
                        text = "0x" + Number(clamped).toString(16).padStart(2, "0")
                        root.page.mcuId = clamped
                    }
                    Connections {
                        target: root.page
                        function onMcuIdChanged() {
                            if (!mcuIdField.activeFocus)
                                mcuIdField.text = "0x" + Number(root.page.mcuId).toString(16).padStart(2, "0")
                        }
                    }
                }
                Label {
                    text: "Host ID (ss)"
                    color: Theme.textSecondary
                    font.pixelSize: Theme.fontCaption
                }
                TextField {
                    id: hostIdField
                    implicitHeight: 32
                    implicitWidth: 64
                    horizontalAlignment: Text.AlignHCenter
                    selectByMouse: true
                    text: "0x" + Number(root.page.hostId).toString(16).padStart(2, "0")
                    onEditingFinished: {
                        const raw = String(text).trim().replace(/^0x/i, "")
                        const parsed = parseInt(raw, 16)
                        if (Number.isNaN(parsed)) {
                            text = "0x" + Number(root.page.hostId).toString(16).padStart(2, "0")
                            return
                        }
                        const clamped = Math.max(0, Math.min(255, parsed))
                        text = "0x" + Number(clamped).toString(16).padStart(2, "0")
                        root.page.hostId = clamped
                    }
                    Connections {
                        target: root.page
                        function onHostIdChanged() {
                            if (!hostIdField.activeFocus)
                                hostIdField.text = "0x" + Number(root.page.hostId).toString(16).padStart(2, "0")
                        }
                    }
                }
                Button {
                    text: "校验通信"
                    highlighted: true
                    implicitHeight: 32
                    enabled: root.page.busReady
                    onClicked: root.page.verify()
                }
                StatusPill {
                    text: root.page.verifyStatus
                    tone: root.verifyTone
                    Layout.fillWidth: false
                }
                Item { Layout.fillWidth: true }
            }
            }
        }

        SectionCard {
            Layout.fillWidth: true
            Layout.preferredHeight: Math.round(root.height * 0.28)
            Layout.minimumHeight: 160
            ColumnLayout {
                anchors.fill: parent
                anchors.leftMargin: Theme.sectionBarWidth + Theme.spaceMd
                anchors.rightMargin: Theme.spaceMd
                anchors.topMargin: Theme.spaceMd
                anchors.bottomMargin: Theme.spaceMd
                spacing: Theme.spaceSm

            RowLayout {
                Layout.fillWidth: true
                spacing: Theme.spaceMd
                Label {
                    text: "周期测量"
                    font.bold: true
                    font.pixelSize: Theme.fontTitle
                    color: Theme.accent
                }
                Label {
                    text: "每帧 ID+P1–P4 · 每行 8 帧 · 定时发 1810"
                    color: Theme.textMuted
                    font.pixelSize: Theme.fontCaption
                }
                Label {
                    text: "周期"
                    color: Theme.textSecondary
                    font.pixelSize: Theme.fontCaption
                }
                TextField {
                    id: periodField
                    implicitHeight: 32
                    implicitWidth: 72
                    horizontalAlignment: Text.AlignHCenter
                    selectByMouse: true
                    text: String(root.page.periodMs)
                    validator: IntValidator { bottom: 50; top: 10000 }
                    onEditingFinished: {
                        const parsed = parseInt(text, 10)
                        if (Number.isNaN(parsed)) {
                            text = String(root.page.periodMs)
                            return
                        }
                        const clamped = Math.max(50, Math.min(10000, parsed))
                        text = String(clamped)
                        root.page.periodMs = clamped
                    }
                    Connections {
                        target: root.page
                        function onPeriodMsChanged() {
                            if (!periodField.activeFocus)
                                periodField.text = String(root.page.periodMs)
                        }
                    }
                }
                Label {
                    text: "ms"
                    color: Theme.textMuted
                    font.pixelSize: Theme.fontCaption
                }
                Button {
                    text: "开始周期"
                    highlighted: true
                    implicitHeight: 32
                    enabled: root.page.busReady
                    onClicked: root.page.pollStart()
                }
                Button {
                    text: "停止周期"
                    flat: true
                    implicitHeight: 32
                    enabled: root.page.busReady
                    onClicked: root.page.pollStop()
                    background: Rectangle {
                        radius: Theme.radiusSm
                        color: parent.down ? Theme.surfaceHover : "transparent"
                        border.color: Theme.border
                        border.width: 1
                    }
                }
                Label {
                    text: "搜索"
                    color: Theme.textSecondary
                    font.pixelSize: Theme.fontCaption
                }
                TextField {
                    id: periodicSearchField
                    Layout.preferredWidth: 160
                    Layout.fillWidth: true
                    Layout.maximumWidth: 280
                    implicitHeight: 32
                    placeholderText: "参数名 / ID（实时高亮）"
                    selectByMouse: true
                    text: root.page.periodicSearch
                    onTextChanged: root.page.periodicSearch = text
                }
                Item { Layout.fillWidth: true }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                radius: Theme.radiusSm
                color: Theme.bg
                border.color: Theme.border
                clip: true
                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 1
                    spacing: 0
                    HorizontalHeaderView {
                        id: periodicHeader
                        syncView: periodicView
                        Layout.fillWidth: true
                        implicitHeight: 24
                        clip: true
                        delegate: Rectangle {
                            implicitHeight: 24
                            required property var model
                            readonly property string hdrText: String(model.display ?? "")
                            readonly property bool isIdHdr: hdrText.indexOf("ID") === 0
                            color: isIdHdr ? Theme.cellId : Theme.headerBg
                            border.color: Theme.borderSubtle
                            Text {
                                anchors.fill: parent
                                text: hdrText
                                color: Theme.textSecondary
                                font.pixelSize: 10
                                font.bold: true
                                horizontalAlignment: Text.AlignHCenter
                                verticalAlignment: Text.AlignVCenter
                                elide: Text.ElideRight
                            }
                        }
                    }
                    TableView {
                        id: periodicView
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        clip: true
                        interactive: false
                        model: root.page.periodicModel
                        columnSpacing: 0
                        rowSpacing: 0
                        boundsBehavior: Flickable.StopAtBounds
                        columnWidthProvider: function (column) {
                            return Math.max(28, Math.floor(width / Math.max(1, columns)))
                        }
                        rowHeightProvider: function (row) {
                            return Math.max(20, Math.floor(height / Math.max(1, rows)))
                        }
                        onWidthChanged: root.scheduleFit()
                        onHeightChanged: root.scheduleFit()
                        delegate: Rectangle {
                            required property int row
                            required property int column
                            required property var display
                            required property var toolTip
                            required property var matched
                            readonly property bool isId: column % 5 === 0
                            readonly property bool groupStart: column > 0 && column % 5 === 0
                            readonly property bool isUnknown: String(display ?? "").endsWith("!")
                            readonly property bool isHit: matched === true
                            readonly property string cellText: String(display ?? "")
                            readonly property bool isEmpty: cellText === "" || cellText === "—"
                            color: {
                                if (isHit)
                                    return Theme.cellSearchHit
                                if (isUnknown)
                                    return Theme.cellUnknown
                                if (isId)
                                    return row % 2 ? Theme.cellIdAlt : Theme.cellId
                                return row % 2 ? Theme.zebraB : Theme.zebraA
                            }
                            border.color: isHit ? Theme.cellSearchHitBorder : Theme.borderSubtle
                            border.width: isHit ? 2 : 1
                            Rectangle {
                                visible: groupStart
                                anchors.left: parent.left
                                anchors.top: parent.top
                                anchors.bottom: parent.bottom
                                width: 2
                                color: Theme.groupSep
                                z: 1
                            }
                            Text {
                                anchors.fill: parent
                                anchors.margins: 1
                                text: cellText
                                color: isEmpty ? Theme.textMuted : Theme.textPrimary
                                font.pixelSize: Theme.fontTable
                                font.family: "Consolas"
                                font.bold: isId || isHit
                                elide: Text.ElideRight
                                verticalAlignment: Text.AlignVCenter
                                horizontalAlignment: Text.AlignHCenter
                            }
                            HoverHandler { id: measHover }
                            ToolTip.visible: measHover.hovered && !!(toolTip)
                            ToolTip.text: toolTip ?? ""
                            ToolTip.delay: 400
                        }
                    }
                }
            }
            }
        }

        SectionCard {
            Layout.fillWidth: true
            Layout.fillHeight: true

            ColumnLayout {
                anchors.fill: parent
                anchors.leftMargin: Theme.sectionBarWidth + Theme.spaceMd
                anchors.rightMargin: Theme.spaceMd
                anchors.topMargin: Theme.spaceMd
                anchors.bottomMargin: Theme.spaceMd
                spacing: Theme.spaceSm

            RowLayout {
                Layout.fillWidth: true
                spacing: Theme.spaceMd
                Label {
                    text: "命令 / 参数下发"
                    font.bold: true
                    font.pixelSize: Theme.fontTitle
                    color: Theme.accent
                }
                Item { Layout.fillWidth: true }
            }

            SplitView {
                Layout.fillWidth: true
                Layout.fillHeight: true
                orientation: Qt.Horizontal
                handle: Rectangle {
                    implicitWidth: 4
                    color: Theme.borderSubtle
                }

                Pane {
                    SplitView.preferredWidth: Math.round(root.width * 0.40)
                    SplitView.minimumWidth: 400
                    SplitView.maximumWidth: 560
                    padding: Theme.spaceSm
                    background: Rectangle {
                        color: Theme.surface
                        radius: Theme.radiusSm
                        border.color: Theme.border
                    }
                    ColumnLayout {
                        anchors.fill: parent
                        spacing: Theme.spaceXs
                        Label {
                            text: "命令区（0x1826 PQ / 0x1827 PcCommand）"
                            font.bold: true
                            color: Theme.primary
                            font.pixelSize: Theme.fontCaption
                        }
                        Label {
                            text: "0x1826 PQ"
                            font.bold: true
                            color: Theme.accent
                            font.pixelSize: Theme.fontCaption
                        }
                        PqCommand {
                            Layout.fillWidth: true
                            Layout.fillHeight: false
                            implicitHeight: 48
                            model: root.page.pqCmd
                            searchQuery: root.page.paramSearch
                        }
                        Label {
                            text: "0x1827 PcCommand"
                            font.bold: true
                            color: Theme.accent
                            font.pixelSize: Theme.fontCaption
                        }
                        PcCommand {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            model: root.page.pcCmd
                            searchQuery: root.page.paramSearch
                        }
                    }
                }

                Pane {
                    SplitView.fillWidth: true
                    padding: Theme.spaceSm
                    background: Rectangle {
                        color: Theme.surface
                        radius: Theme.radiusSm
                        border.color: Theme.border
                    }
                    ColumnLayout {
                        anchors.fill: parent
                        spacing: Theme.spaceXs
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: Theme.spaceSm
                            Label {
                                text: "参数区（0x1830–0x1848）"
                                font.bold: true
                                font.pixelSize: Theme.fontCaption
                                color: Theme.primary
                            }
                            Button {
                                text: "获取参数"
                                highlighted: true
                                implicitHeight: 28
                                enabled: root.page.busReady
                                onClicked: root.page.fetchParams()
                            }
                            Label {
                                text: "搜索"
                                color: Theme.textSecondary
                                font.pixelSize: Theme.fontCaption
                            }
                            TextField {
                                id: paramSearchField
                                Layout.preferredWidth: 160
                                Layout.fillWidth: true
                                Layout.maximumWidth: 280
                                implicitHeight: 28
                                placeholderText: "参数名 / ID（实时高亮）"
                                selectByMouse: true
                                text: root.page.paramSearch
                                onTextChanged: root.page.paramSearch = text
                            }
                        }
                        Label {
                            text: "P1–P4 可编辑，点 ▶ 下发"
                            color: Theme.textMuted
                            font.pixelSize: Theme.fontCaption
                        }
                        Rectangle {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            radius: Theme.radiusSm
                            color: Theme.bg
                            border.color: Theme.border
                            clip: true
                            ColumnLayout {
                                anchors.fill: parent
                                anchors.margins: 1
                                spacing: 0
                                HorizontalHeaderView {
                                    id: paramHeader
                                    syncView: paramView
                                    Layout.fillWidth: true
                                    implicitHeight: 24
                                    clip: true
                                    delegate: Rectangle {
                                        implicitHeight: 24
                                        required property var model
                                        readonly property string hdrText: String(model.display ?? "")
                                        readonly property bool isIdHdr: hdrText.indexOf("ID") === 0
                                        color: isIdHdr ? Theme.cellId : Theme.headerBg
                                        border.color: Theme.borderSubtle
                                        Text {
                                            anchors.fill: parent
                                            text: hdrText
                                            color: Theme.textSecondary
                                            font.pixelSize: 10
                                            font.bold: true
                                            horizontalAlignment: Text.AlignHCenter
                                            verticalAlignment: Text.AlignVCenter
                                            elide: Text.ElideRight
                                        }
                                    }
                                }
                                TableView {
                                    id: paramView
                                    Layout.fillWidth: true
                                    Layout.fillHeight: true
                                    clip: true
                                    interactive: false
                                    model: root.page.paramModel
                                    columnSpacing: 0
                                    rowSpacing: 0
                                    boundsBehavior: Flickable.StopAtBounds
                                    columnWidthProvider: function (column) {
                                        const n = Math.max(1, columns)
                                        const sendW = Theme.sendBtnWidth
                                        const nSend = 2
                                        if (column % 6 === 5)
                                            return sendW
                                        return Math.max(36, Math.floor((width - sendW * nSend) / (n - nSend)))
                                    }
                                    rowHeightProvider: function (row) {
                                        return Math.max(24, Math.floor(height / Math.max(1, rows)))
                                    }
                                    onWidthChanged: root.scheduleFit()
                                    onHeightChanged: root.scheduleFit()
                                    delegate: Rectangle {
                                        required property int row
                                        required property int column
                                        required property var display
                                        required property var toolTip
                                        required property var matched
                                        readonly property bool isSend: column % 6 === 5
                                        readonly property bool isId: column % 6 === 0
                                        readonly property bool groupStart: column > 0 && column % 6 === 0
                                        readonly property bool isUnknown: String(display ?? "").endsWith("!")
                                        readonly property bool isHit: matched === true
                                        readonly property bool canEdit: !isSend && !isId
                                                                         && !isUnknown
                                                                         && root.page.paramCellEditable(row, column)
                                        readonly property string cellText: String(display ?? "")
                                        readonly property bool isEmpty: cellText === "" || cellText === "—"
                                        color: {
                                            if (isHit)
                                                return Theme.cellSearchHit
                                            if (isUnknown)
                                                return Theme.cellUnknown
                                            if (isSend)
                                                return Theme.surface
                                            if (isId)
                                                return row % 2 ? Theme.cellIdAlt : Theme.cellId
                                            if (canEdit)
                                                return row % 2 ? Theme.cellEditAlt : Theme.cellEdit
                                            return row % 2 ? Theme.zebraB : Theme.zebraA
                                        }
                                        border.color: isHit ? Theme.cellSearchHitBorder : Theme.borderSubtle
                                        border.width: isHit ? 2 : 1

                                        Rectangle {
                                            visible: groupStart
                                            anchors.left: parent.left
                                            anchors.top: parent.top
                                            anchors.bottom: parent.bottom
                                            width: 2
                                            color: Theme.groupSep
                                            z: 1
                                        }

                                        HoverHandler { id: evtHover }
                                        ToolTip.visible: evtHover.hovered && !!(toolTip) && !isSend
                                        ToolTip.text: toolTip ?? ""
                                        ToolTip.delay: 400

                                            Text {
                                            anchors.fill: parent
                                            anchors.margins: 1
                                            visible: !canEdit && !isSend
                                            text: cellText
                                            color: isEmpty ? Theme.textMuted : Theme.textPrimary
                                            font.pixelSize: Theme.fontTable
                                            font.family: "Consolas"
                                            font.bold: isId || isHit
                                            elide: Text.ElideRight
                                            verticalAlignment: Text.AlignVCenter
                                            horizontalAlignment: isId ? Text.AlignHCenter : Text.AlignLeft
                                        }

                                        TextInput {
                                            id: paramEdit
                                            anchors.fill: parent
                                            anchors.margins: 1
                                            visible: canEdit
                                            text: display ?? ""
                                            color: Theme.textPrimary
                                            font.pixelSize: Theme.fontTable
                                            font.family: "Consolas"
                                            selectByMouse: true
                                            clip: true
                                            verticalAlignment: TextInput.AlignVCenter
                                            leftPadding: 2
                                            rightPadding: 2
                                            property string modelText: display ?? ""
                                            onModelTextChanged: {
                                                if (!activeFocus)
                                                    text = modelText
                                            }
                                            onEditingFinished: {
                                                root.page.setParamCell(row, column, text)
                                            }
                                            Keys.onReturnPressed: {
                                                root.page.setParamCell(row, column, text)
                                                focus = false
                                            }
                                            Keys.onEnterPressed: {
                                                root.page.setParamCell(row, column, text)
                                                focus = false
                                            }
                                        }

                                        Button {
                                            anchors.centerIn: parent
                                            visible: isSend && !isUnknown
                                            width: parent.width - 2
                                            height: parent.height - 2
                                            flat: true
                                            text: "▶"
                                            enabled: root.page.busReady
                                            onClicked: root.page.paramCellClicked(row, column)
                                            HoverHandler { id: sendHover }
                                            ToolTip.visible: sendHover.hovered
                                            ToolTip.text: toolTip || "发送此帧"
                                            ToolTip.delay: 400
                                            background: Rectangle {
                                                radius: Theme.radiusSm
                                                color: {
                                                    if (!parent.enabled)
                                                        return "transparent"
                                                    if (parent.down)
                                                        return Theme.accentDim
                                                    if (sendHover.hovered)
                                                        return Theme.cellAction
                                                    return "transparent"
                                                }
                                            }
                                            contentItem: Text {
                                                text: parent.text
                                                color: parent.enabled ? Theme.accent : Theme.textMuted
                                                font.pixelSize: 16
                                                font.bold: true
                                                horizontalAlignment: Text.AlignHCenter
                                                verticalAlignment: Text.AlignVCenter
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 24
            radius: Theme.radiusSm
            color: Theme.surfaceHigh
            border.color: Theme.borderSubtle
            border.width: 1

            function formatStatus(plain) {
                let t = String(plain ?? "")
                t = t.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
                const tx = Theme.primary
                const rx = Theme.accent
                t = t.replace(/\bTX\b/g, `<b><font color="${tx}">TX</font></b>`)
                t = t.replace(/\bRX\b/g, `<b><font color="${rx}">RX</font></b>`)
                return t
            }

            Text {
                anchors.fill: parent
                anchors.leftMargin: Theme.spaceMd
                anchors.rightMargin: Theme.spaceMd
                textFormat: Text.RichText
                text: parent.formatStatus(root.page.statusText)
                color: Theme.textSecondary
                font.pixelSize: Theme.fontCaption
                elide: Text.ElideRight
                verticalAlignment: Text.AlignVCenter
            }
        }
    }
}
