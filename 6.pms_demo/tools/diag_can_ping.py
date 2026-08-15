"""真盒裸收发诊断：区分「收包坏了」vs「MCU 没回」。

用法（先关掉 ZCANPRO / 本 GUI）::

    cd 6.pms_demo
    uv run python tools/diag_can_ping.py
    uv run python tools/diag_can_ping.py --channel 1
    uv run python tools/diag_can_ping.py --ota-sdk C:/home/win11_py_dev/can_OTA_1218
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from ctypes import c_int
from pathlib import Path

from can_zlg import CanBus, CanFrame, DeviceType
from can_zlg.frame import encode_raw_can_id
from can_zlg.sdk import load_zlgcan_module, resolve_sdk_dir
from can_zlg.zlg_bus import ZlgCanBus, _cwd


def _hex(data: bytes) -> str:
    return " ".join(f"{b:02X}" for b in data)


def _dump_rx(bus: CanBus, *, seconds: float, label: str) -> int:
    print(f"--- {label}（{seconds:.1f}s）---")
    deadline = time.monotonic() + seconds
    n = 0
    while time.monotonic() < deadline:
        remain_ms = max(1, int((deadline - time.monotonic()) * 1000))
        frame = bus.recv(timeout_ms=min(200, remain_ms))
        if frame is None:
            continue
        n += 1
        ext = "EXT" if frame.is_extended else "STD"
        print(
            f"  RX#{n} {ext} ID=0x{frame.can_id:08X} "
            f"DLC={len(frame.data)} data=[{_hex(frame.data)}]"
        )
    print(f"  → 共收到 {n} 帧")
    return n


def _self_echo_test(bus: ZlgCanBus, *, can_id: int, data: bytes) -> int:
    """transmit_type=2 自发自收：不依赖 MCU，专测本机收包路径。"""
    print("--- 自发自收自检（transmit_type=2，不经总线对端）---")
    raw_id = encode_raw_can_id(can_id, is_extended=True, is_remote=False)
    with _cwd(bus._sdk_dir):  # noqa: SLF001
        msgs = (bus._zlg.ZCAN_Transmit_Data * 1)()  # noqa: SLF001
        msgs[0].transmit_type = 2
        frame = msgs[0].frame
        if hasattr(frame, "eff"):
            frame.eff = 1
            frame.rtr = 0
            if hasattr(frame, "err"):
                frame.err = 0
            frame.can_id = can_id & 0x1FFFFFFF
        else:
            frame.can_id = raw_id
        frame.can_dlc = len(data)
        for i, b in enumerate(data):
            frame.data[i] = b
        ret = bus._zcan.Transmit(bus._channel_handle, msgs, 1)  # noqa: SLF001
        print(f"  Transmit(ret={ret}) type=2 ID=0x{can_id:08X} data=[{_hex(data)}]")
        time.sleep(0.05)
        n = bus._zcan.GetReceiveNum(bus._channel_handle, bus._zlg.ZCAN_TYPE_CAN)  # noqa: SLF001
        print(f"  GetReceiveNum={n}")
        got_total = 0
        if n:
            rcv, got = bus._zcan.Receive(bus._channel_handle, min(int(n), 16), c_int(0))  # noqa: SLF001
            got_total = int(got)
            for i in range(got_total):
                f = rcv[i].frame
                cid = int(f.can_id) & 0x1FFFFFFF
                dlc = int(f.can_dlc)
                print(f"  ECHO#{i + 1} ID=0x{cid:08X} DLC={dlc} data=[{_hex(bytes(f.data[:dlc]))}]")
    return got_total


def main() -> int:
    p = argparse.ArgumentParser(description="PMS CAN 真盒诊断")
    p.add_argument("--channel", type=int, default=0)
    p.add_argument("--bitrate", type=int, default=500_000)
    p.add_argument("--ss", type=int, default=0x00, help="上位机地址 ss")
    p.add_argument("--dd", type=int, default=0x02, help="下位机地址 dd")
    p.add_argument("--listen-only", action="store_true", help="不发送，只听")
    p.add_argument("--dlc8", action="store_true", help="校验载荷补到 8 字节")
    p.add_argument(
        "--ota-sdk",
        type=str,
        default="",
        help="改用 can_OTA_1218 目录作 SDK（含 zlgcan.py/dll）",
    )
    args = p.parse_args()

    if args.ota_sdk:
        os.environ["CAN_ZLG_SDK_DIR"] = str(Path(args.ota_sdk).resolve())

    tx_id = (0x1806 << 16) | ((args.dd & 0xFF) << 8) | (args.ss & 0xFF)
    rx_id = (0x1A06 << 16) | ((args.ss & 0xFF) << 8) | (args.dd & 0xFF)
    payload = (b"\x01" + b"\x00" * 7) if args.dlc8 else b"\x01"
    raw = encode_raw_can_id(tx_id, is_extended=True, is_remote=False)
    sdk = resolve_sdk_dir()

    print(f"sdk={sdk}")
    print(f"device=USBCAN-2E-U ch={args.channel} bitrate={args.bitrate}")
    print(f"TX ID=0x{tx_id:08X} (raw=0x{raw:08X}) data=[{_hex(payload)}]")
    print(f"期望 RX ID=0x{rx_id:08X}")

    # 预检结构体：确认 eff 位域存在
    zlg = load_zlgcan_module(sdk)
    sample = zlg.ZCAN_CAN_FRAME()
    print(f"ZCAN_CAN_FRAME.has_eff={hasattr(sample, 'eff')} size fields ok")

    try:
        bus = CanBus.open(
            DeviceType.USBCAN_2E_U,
            channel=args.channel,
            bitrate=args.bitrate,
        )
    except Exception as exc:
        print(f"打开失败: {exc}", file=sys.stderr)
        return 1

    try:
        if not isinstance(bus, ZlgCanBus):
            print("非 ZlgCanBus，跳过自发自收自检")
        else:
            echo_n = _self_echo_test(bus, can_id=tx_id, data=payload)
            if echo_n == 0:
                print(
                    "结论A：自发自收也是 0 帧 → 本机收包/启动通道异常"
                    "（或通道号不对）。请改 --channel 1 再试；"
                    "或 --ota-sdk 指向 can_OTA_1218。"
                )
            else:
                print("结论A：自发自收有回显 → 本机 RX 路径基本正常，问题在总线/MCU 应答。")

        if args.listen_only:
            _dump_rx(bus, seconds=3.0, label="只听")
            return 0

        print("发送前先听 0.3s…")
        _dump_rx(bus, seconds=0.3, label="发送前")

        bus.send(CanFrame(can_id=tx_id, data=payload, is_extended=True))
        if isinstance(bus, ZlgCanBus):
            with _cwd(bus._sdk_dir):  # noqa: SLF001
                n_pending = bus._zcan.GetReceiveNum(  # noqa: SLF001
                    bus._channel_handle, bus._zlg.ZCAN_TYPE_CAN
                )
            print(f"正常发送后立即 GetReceiveNum={n_pending}")

        print("已 Transmit(type=0)，开始收 2.0s…")
        n = _dump_rx(bus, seconds=2.0, label="发送后")
        if n == 0:
            print(
                "结论B：正常发送后 2s 仍 0 帧。"
                "请用 ZCANPRO 看总线上有无 0x18060200 / 0x1A060002；"
                "并试 --channel 1 / --dlc8 / --ota-sdk。"
            )
            return 2
        ids: list[int] = []
        bus.send(CanFrame(can_id=tx_id, data=payload, is_extended=True))
        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline:
            frame = bus.recv(timeout_ms=100)
            if frame is None:
                continue
            ids.append(frame.can_id)
            if frame.can_id == rx_id:
                print(f"成功：收到期望应答 0x{rx_id:08X} data=[{_hex(frame.data)}]")
                return 0
        print(f"有 RX 但无匹配 0x{rx_id:08X}；本轮见到 ID={[hex(i) for i in ids]}")
        return 3
    finally:
        bus.close()
        print("已 CloseDevice")


if __name__ == "__main__":
    raise SystemExit(main())
