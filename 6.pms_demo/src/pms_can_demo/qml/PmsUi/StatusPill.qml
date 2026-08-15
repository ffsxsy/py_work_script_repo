import QtQuick
import QtQuick.Layouts

/**
 * 状态胶囊：灰 / 绿 / 琥珀 / 红。
 * tone: "neutral" | "success" | "warning" | "danger" | "accent"
 */
Rectangle {
    id: root
    property string text: ""
    property string tone: "neutral"
    property bool showDot: true

    readonly property color _fg: {
        switch (tone) {
        case "success": return Theme.success
        case "warning": return Theme.warning
        case "danger": return Theme.danger
        case "accent": return Theme.accent
        default: return Theme.textMuted
        }
    }
    readonly property color _bg: {
        switch (tone) {
        case "success": return Theme.successDim
        case "warning": return Theme.warningDim
        case "danger": return Theme.dangerDim
        case "accent": return Theme.accentDim
        default: return Theme.surfaceHover
        }
    }

    implicitHeight: 28
    implicitWidth: row.implicitWidth + Theme.spaceMd * 2
    radius: height / 2
    color: _bg
    border.color: _fg
    border.width: 1

    RowLayout {
        id: row
        anchors.centerIn: parent
        spacing: Theme.spaceXs
        Rectangle {
            visible: root.showDot
            width: 8
            height: 8
            radius: 4
            color: root._fg
        }
        Text {
            text: root.text
            color: Theme.textPrimary
            font.pixelSize: Theme.fontCaption
            elide: Text.ElideRight
            Layout.maximumWidth: 360
        }
    }
}
