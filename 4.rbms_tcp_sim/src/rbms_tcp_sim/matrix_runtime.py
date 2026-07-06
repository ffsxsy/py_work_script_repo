"""Matrix 周期报文运行时状态与 payload 解析。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from rbms_tcp_sim.codec import write_matrix_field
from rbms_tcp_sim.matrix_config.csv_common import (
    CsvReloadState,
    MatrixCsvSettings,
    MatrixSignalValue,
    apply_signals,
    build_payload_from_signals,
    derive_signals,
    load_matrix_csv,
    reload_csv_if_changed,
)
from rbms_tcp_sim.matrix_config.generators import default_signals_for
from rbms_tcp_sim.matrix_config.profiles import MESSAGE_PROFILES, MessageProfile, get_profile
from rbms_tcp_sim.messages import (
    RBMS_STR_CTRL_HB_BIT_LEN,
    RBMS_STR_CTRL_HB_DATA_TYPE,
    RBMS_STR_CTRL_HB_SIGNAL,
    RBMS_STR_CTRL_HB_START_BIT,
    RBMS_SUMINFO_PAYLOAD_LEN,
)

_cached_default_suminfo_settings: MatrixCsvSettings | None = None


def _effective_animate(
    csv_animate: bool,
    *,
    allow_csv_animate: bool,
    force_animate: bool = False,
) -> bool:
    """联调默认固定 value；animate_payload=true 时才读 CSV animate 行。"""
    if force_animate:
        return True
    return allow_csv_animate and csv_animate


@dataclass
class MatrixMessageRuntime:
    """单条 Matrix 周期报文的 CSV 缓存与 tick。"""

    profile: MessageProfile
    signals: tuple[MatrixSignalValue, ...] = field(default_factory=tuple)
    config_path: str | None = None
    animate: bool = False
    allow_csv_animate: bool = False
    mtime_ns: int | None = None
    tick: int = 0

    def next_tick(self) -> int:
        self.tick += 1
        return self.tick


def default_suminfo_settings() -> MatrixCsvSettings:
    """内置 SumInfo 点表（来自 config/rbms_suminfo.csv 模板）。"""
    global _cached_default_suminfo_settings
    if _cached_default_suminfo_settings is None:
        profile = get_profile("suminfo")
        _cached_default_suminfo_settings = load_matrix_csv(
            profile.default_csv,
            skip_signals=profile.skip_signals,
        )
    return _cached_default_suminfo_settings


def default_suminfo_signals() -> tuple[MatrixSignalValue, ...]:
    return default_suminfo_settings().signals


def build_suminfo_payload_from_signals(
    signals: tuple[MatrixSignalValue, ...],
    *,
    str_ctrl_hb: int,
) -> bytes:
    """SumInfo payload：先按 CSV 编码全部信号，再覆盖 StrCtrlHb 为会话心跳值。"""
    buf = bytearray(RBMS_SUMINFO_PAYLOAD_LEN)
    payload_signals = tuple(s for s in signals if s.signal != RBMS_STR_CTRL_HB_SIGNAL)
    apply_signals(buf, payload_signals)
    hb_signal = next((s for s in signals if s.signal == RBMS_STR_CTRL_HB_SIGNAL), None)
    if hb_signal is not None:
        write_matrix_field(
            buf,
            start_bit=hb_signal.start_bit,
            bit_len=hb_signal.bit_len,
            raw=str_ctrl_hb & 0xFFFF,
            data_type=hb_signal.data_type,
        )
    else:
        write_matrix_field(
            buf,
            start_bit=RBMS_STR_CTRL_HB_START_BIT,
            bit_len=RBMS_STR_CTRL_HB_BIT_LEN,
            raw=str_ctrl_hb & 0xFFFF,
            data_type=RBMS_STR_CTRL_HB_DATA_TYPE,
        )
    return bytes(buf)


def load_message_runtime(
    name: str,
    *,
    config_path: Path | None,
    use_external: bool,
    allow_csv_animate: bool = False,
    force_animate: bool = False,
) -> MatrixMessageRuntime:
    profile = get_profile(name)
    csv_animate = False
    signals: tuple[MatrixSignalValue, ...]

    if use_external and config_path is not None:
        settings = load_matrix_csv(config_path, skip_signals=profile.skip_signals)
        signals = settings.signals
        csv_animate = settings.animate
    elif name == "suminfo":
        settings = default_suminfo_settings()
        signals = settings.signals
        csv_animate = settings.animate
    else:
        signals = default_signals_for(name)

    return MatrixMessageRuntime(
        profile=profile,
        signals=signals,
        config_path=str(config_path) if config_path is not None else None,
        animate=_effective_animate(
            csv_animate,
            allow_csv_animate=allow_csv_animate,
            force_animate=force_animate,
        ),
        allow_csv_animate=allow_csv_animate,
    )


def resolve_message_signals(runtime: MatrixMessageRuntime) -> tuple[MatrixSignalValue, ...]:
    if runtime.config_path is not None:
        cache = CsvReloadState(
            config_path=Path(runtime.config_path),
            signals=runtime.signals,
            animate=runtime.animate,
            mtime_ns=runtime.mtime_ns,
            skip_signals=runtime.profile.skip_signals,
        )
        signals = reload_csv_if_changed(cache)
        runtime.signals = cache.signals
        runtime.animate = _effective_animate(
            cache.animate,
            allow_csv_animate=runtime.allow_csv_animate,
        )
        runtime.mtime_ns = cache.mtime_ns
    else:
        signals = runtime.signals

    tick = runtime.next_tick()
    if runtime.animate:
        return derive_signals(signals, tick)
    return signals


def build_suminfo_payload(runtime: MatrixMessageRuntime, *, str_ctrl_hb: int) -> bytes:
    signals = resolve_message_signals(runtime)
    return build_suminfo_payload_from_signals(signals, str_ctrl_hb=str_ctrl_hb)


def build_message_payload(runtime: MatrixMessageRuntime) -> bytes:
    signals = resolve_message_signals(runtime)
    return build_payload_from_signals(runtime.profile.payload_len, signals)


def matrix_message_names_with_csv() -> frozenset[str]:
    return frozenset(MESSAGE_PROFILES.keys())
