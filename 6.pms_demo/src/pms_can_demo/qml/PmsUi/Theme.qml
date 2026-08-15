pragma Singleton
import QtQuick

/**
 * 工业上位机 · 浅色护眼令牌（柔和灰蓝底 + 青绿强调，非刺眼纯白/纯黑）。
 * 禁止在页面散落魔法色值；统一引用 Theme.*。
 */
QtObject {
    readonly property color bg: "#eef2f6"
    readonly property color surface: "#f8fafc"
    readonly property color surfaceHigh: "#ffffff"
    readonly property color surfaceHover: "#e8eef5"
    readonly property color border: "#c5d0de"
    readonly property color borderSubtle: "#d9e2ec"

    readonly property color textPrimary: "#1e293b"
    readonly property color textSecondary: "#475569"
    readonly property color textMuted: "#64748b"

    readonly property color accent: "#0f766e"
    readonly property color accentDim: "#99f6e4"
    readonly property color primary: "#0369a1"
    readonly property color success: "#059669"
    readonly property color successDim: "#d1fae5"
    readonly property color warning: "#d97706"
    readonly property color warningDim: "#fef3c7"
    readonly property color danger: "#dc2626"
    readonly property color dangerDim: "#fee2e2"
    readonly property color dangerHover: "#b91c1c"
    readonly property color pulseGreen: "#10b981"
    readonly property color pulseGreenDim: "#047857"

    readonly property color zebraA: "#ffffff"
    readonly property color zebraB: "#f1f5f9"
    readonly property color cellId: "#e8eef5"
    readonly property color cellIdAlt: "#dfe7f0"
    readonly property color cellEdit: "#eef8ff"
    readonly property color cellEditAlt: "#f7fbff"
    readonly property color cellAction: "#ccfbf1"
    readonly property color cellActionDisabled: "#e2e8f0"
    readonly property color cellUnknown: "#ffedd5"
    readonly property color cellSearchHit: "#fde047"
    readonly property color cellSearchHitBorder: "#ca8a04"
    readonly property color headerBg: "#e2e8f0"
    readonly property color groupSep: "#94a3b8"
    readonly property color tabAlert: "#fef3c7"

    readonly property int radiusSm: 6
    readonly property int radiusMd: 10
    readonly property int radiusLg: 14
    readonly property int spaceXs: 4
    readonly property int spaceSm: 8
    readonly property int spaceMd: 12
    readonly property int spaceLg: 16
    readonly property int spaceXl: 24

    readonly property int fontCaption: 12
    readonly property int fontBody: 13
    readonly property int fontTitle: 15
    readonly property int fontTable: 11
    readonly property int fontMono: 11

    readonly property int elevationToolbar: 2
    readonly property int elevationCard: 1
    readonly property int sectionBarWidth: 4
    readonly property int sendBtnWidth: 44
}
