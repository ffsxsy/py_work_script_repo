import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import PmsUi

/** 0x1826 PQ command：工程值编辑 + 发送（与参数同一行）。 */
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
        return q === "1826" || q === "0x1826" || q === "pq"
    }

    component EngField: ColumnLayout {
        id: engRoot
        property alias label: lbl.text
        property string value: ""
        property bool hit: false
        property string tip: ""
        signal valueEdited(string v)

        spacing: 1
        Layout.fillWidth: true
        Layout.minimumWidth: 64
        Rectangle {
            Layout.fillWidth: true
            radius: Theme.radiusSm
            color: engRoot.hit ? Theme.cellSearchHit : "transparent"
            border.color: engRoot.hit ? Theme.cellSearchHitBorder : "transparent"
            border.width: engRoot.hit ? 1 : 0
            implicitHeight: lbl.implicitHeight + 2
            Label {
                id: lbl
                anchors.fill: parent
                anchors.margins: 1
                color: engRoot.hit ? Theme.textPrimary : Theme.textSecondary
                font.pixelSize: 10
                font.bold: engRoot.hit
                elide: Text.ElideRight
            }
            HoverHandler { id: engLblHover }
            ToolTip.visible: engLblHover.hovered && engRoot.tip.length > 0
            ToolTip.text: engRoot.tip
            ToolTip.delay: 280
        }
        TextField {
            id: field
            text: engRoot.value
            font.pixelSize: 12
            font.family: "Consolas"
            font.bold: engRoot.hit
            horizontalAlignment: Text.AlignHCenter
            selectByMouse: true
            implicitHeight: 28
            Layout.fillWidth: true
            background: Rectangle {
                radius: Theme.radiusSm
                color: engRoot.hit ? Theme.cellSearchHit : Theme.surfaceHigh
                border.color: engRoot.hit ? Theme.cellSearchHitBorder : Theme.border
                border.width: engRoot.hit ? 2 : 1
            }
            HoverHandler { id: engFieldHover }
            ToolTip.visible: engFieldHover.hovered && engRoot.tip.length > 0
            ToolTip.text: engRoot.tip
            ToolTip.delay: 280
            onEditingFinished: {
                if (text !== engRoot.value)
                    engRoot.valueEdited(text)
            }
        }
        onValueChanged: {
            if (!field.activeFocus)
                field.text = value
        }
    }

    RowLayout {
        anchors.fill: parent
        spacing: Theme.spaceXs

        EngField {
            label: "P preset %"
            value: root.model.pPreset
            hit: root.labelHit("P preset %")
            tip: {
                const t = root.model.slotTip(0)
                return t === undefined || t === null ? "" : String(t)
            }
            onValueEdited: (v) => { root.model.pPreset = v }
        }
        EngField {
            label: "Q preset %"
            value: root.model.qPreset
            hit: root.labelHit("Q preset %")
            tip: {
                const t = root.model.slotTip(1)
                return t === undefined || t === null ? "" : String(t)
            }
            onValueEdited: (v) => { root.model.qPreset = v }
        }
        EngField {
            label: "Ibat ref"
            value: root.model.ibatRef
            hit: root.labelHit("Ibat ref")
            tip: {
                const t = root.model.slotTip(2)
                return t === undefined || t === null ? "" : String(t)
            }
            onValueEdited: (v) => { root.model.ibatRef = v }
        }
        EngField {
            label: "Vbat ref"
            value: root.model.vbatRef
            hit: root.labelHit("Vbat ref")
            tip: {
                const t = root.model.slotTip(3)
                return t === undefined || t === null ? "" : String(t)
            }
            onValueEdited: (v) => { root.model.vbatRef = v }
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
            HoverHandler { id: sendHover }
            ToolTip.visible: sendHover.hovered
            ToolTip.text: "发送 0x1826"
            ToolTip.delay: 280
        }
    }
}
