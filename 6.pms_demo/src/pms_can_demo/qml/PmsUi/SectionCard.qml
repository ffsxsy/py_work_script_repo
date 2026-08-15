import QtQuick
import PmsUi

/** 分区卡片背景：左侧强调色条。子项自行 anchors / Layout。 */
Item {
    id: root

    Rectangle {
        z: -1
        anchors.fill: parent
        color: Theme.surfaceHigh
        radius: Theme.radiusMd
        border.color: Theme.borderSubtle
        border.width: 1
        Rectangle {
            anchors.left: parent.left
            anchors.top: parent.top
            anchors.bottom: parent.bottom
            width: Theme.sectionBarWidth
            color: Theme.accent
        }
    }
}
