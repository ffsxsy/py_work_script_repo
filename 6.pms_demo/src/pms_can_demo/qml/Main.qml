import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Material
import QtQuick.Layouts
import PmsUi

ApplicationWindow {
    id: win
    width: 1440
    height: 900
    minimumWidth: 1280
    minimumHeight: 800
    visible: true
    visibility: Window.Maximized
    title: "PMS CAN Demo"
    color: Theme.bg

    Material.theme: Material.Light
    Material.accent: Theme.accent
    Material.primary: Theme.primary
    Material.background: Theme.bg
    Material.foreground: Theme.textPrimary

    font.pixelSize: Theme.fontBody

    header: ToolBar {
        id: topBar
        Material.elevation: Theme.elevationToolbar
        background: Rectangle {
            color: Theme.surface
            Rectangle {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                height: 1
                color: Theme.borderSubtle
            }
        }

        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: Theme.spaceMd
            anchors.rightMargin: Theme.spaceMd
            spacing: Theme.spaceSm

            Label {
                text: "设备"
                color: Theme.textSecondary
                font.pixelSize: Theme.fontCaption
            }
            ComboBox {
                model: app.deviceLabels
                currentIndex: app.deviceIndex
                enabled: !app.busOpen
                implicitHeight: 32
                Layout.preferredWidth: 168
                onActivated: (idx) => { app.deviceIndex = idx }
            }

            Label {
                text: "通道"
                color: Theme.textSecondary
                font.pixelSize: Theme.fontCaption
            }
            ComboBox {
                model: ["0", "1"]
                currentIndex: app.channel
                enabled: !app.busOpen
                implicitHeight: 32
                Layout.preferredWidth: 64
                onActivated: (idx) => { app.channel = idx }
            }

            Label {
                text: "波特率"
                color: Theme.textSecondary
                font.pixelSize: Theme.fontCaption
            }
            ComboBox {
                model: app.bitrateLabels
                currentIndex: app.bitrateIndex
                enabled: !app.busOpen
                implicitHeight: 32
                Layout.preferredWidth: 100
                onActivated: (idx) => { app.bitrateIndex = idx }
            }

            Button {
                text: "打开总线"
                implicitHeight: 32
                enabled: !app.busOpen
                onClicked: app.openBus()
                background: Rectangle {
                    radius: Theme.radiusSm
                    color: {
                        if (!parent.enabled)
                            return Theme.cellActionDisabled
                        return parent.down ? Theme.pulseGreenDim : Theme.accent
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
            }
            Button {
                text: "关闭总线"
                flat: true
                implicitHeight: 32
                enabled: app.busOpen
                onClicked: app.closeBus()
                background: Rectangle {
                    radius: Theme.radiusSm
                    color: parent.down ? Theme.surfaceHover : "transparent"
                    border.color: parent.enabled ? Theme.border : Theme.borderSubtle
                    border.width: 1
                }
                contentItem: Text {
                    text: parent.text
                    color: parent.enabled ? Theme.textSecondary : Theme.textMuted
                    font.pixelSize: Theme.fontBody
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
            }

            Item { Layout.fillWidth: true }

            StatusPill {
                text: app.busOpen ? "已打开" : "关闭"
                tone: app.busOpen ? "success" : "neutral"
                HoverHandler { id: busHover }
                ToolTip.visible: busHover.hovered
                ToolTip.text: app.busStatus
                ToolTip.delay: 300
            }
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.spaceSm
        spacing: Theme.spaceSm

        TabBar {
            id: tabBar
            Layout.fillWidth: true
            Material.accent: Theme.accent
            background: Rectangle {
                color: Theme.surfaceHigh
                radius: Theme.radiusMd
                border.color: Theme.borderSubtle
                border.width: 1
            }
            Repeater {
                model: app.pageCount
                TabButton {
                    required property int index
                    readonly property var pageObj: app.pageAt(index)
                    text: pageObj.title + (pageObj.unknownAlert ? " ⚠" : "")
                    width: Math.max(110, Math.floor((win.width - Theme.spaceSm * 4) / Math.max(1, app.pageCount)))
                    font.pixelSize: Theme.fontCaption
                    background: Rectangle {
                        color: {
                            if (pageObj.unknownAlert)
                                return Theme.tabAlert
                            return parent.checked ? Theme.accentDim : "transparent"
                        }
                        radius: Theme.radiusSm
                    }
                }
            }
            onCurrentIndexChanged: app.currentPage = currentIndex
        }

        Frame {
            Layout.fillWidth: true
            Layout.fillHeight: true
            padding: 0
            background: Rectangle {
                color: Theme.surface
                radius: Theme.radiusLg
                border.color: Theme.borderSubtle
                border.width: 1
            }

            StackLayout {
                anchors.fill: parent
                anchors.margins: 2
                currentIndex: tabBar.currentIndex
                Repeater {
                    model: app.pageCount
                    DevicePage {
                        required property int index
                        page: app.pageAt(index)
                    }
                }
            }
        }
    }

    Dialog {
        id: errDlg
        title: "打开总线失败"
        modal: true
        standardButtons: Dialog.Ok
        anchors.centerIn: parent
        Material.background: Theme.surfaceHigh
        Label {
            id: errLabel
            wrapMode: Text.Wrap
            width: 400
            color: Theme.textPrimary
        }
    }

    Connections {
        target: app
        function onErrorDialog(msg) {
            errLabel.text = msg
            errDlg.open()
        }
    }

    onClosing: app.shutdown()
}
