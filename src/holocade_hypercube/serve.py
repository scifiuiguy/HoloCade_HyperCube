# Copyright (c) 2025 AJ Campbell. Licensed under the MIT License.
"""Run vision loop: 8 synthetic feeds → atlas → 4 quadrants → TCP JPEG to Unity + HoloCade UDP pose."""

from __future__ import annotations

import argparse
import asyncio
import socket
import struct
import time
from pathlib import Path

import yaml

from holocade_hypercube.atlas.packer import pack_four_by_two
from holocade_hypercube.feeds.synthetic import synthetic_frame
from holocade_hypercube.protocol.holocade_udp import build_float, build_int32
from holocade_hypercube.quadrants.split import four_vertical_bands


def encode_jpeg(bgr) -> bytes:
    import cv2

    ok, buf = cv2.imencode(".jpg", bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
    if not ok:
        raise RuntimeError("jpeg encode failed")
    return buf.tobytes()


def dump_atlas_png(path: Path) -> None:
    import cv2

    frames = [synthetic_frame(i) for i in range(8)]
    atlas = pack_four_by_two(frames)
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), atlas)


async def tcp_send_jpeg_frame(writer: asyncio.StreamWriter, jpeg: bytes) -> None:
    header = struct.pack(">I", len(jpeg))
    writer.write(header + jpeg)
    await writer.drain()


def load_config(path: Path | None) -> dict:
    if path is None or not path.is_file():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def pose_packets(seq: int) -> list[bytes]:
    """Stub atlas-normalized u,v per side + shared seq on int channel Sequence."""
    from holocade_hypercube.pose_channels import HyperCubePoseChannelIds as ch

    pairs = [
        (ch.NorthU, ch.NorthV, 0.52, 0.48),
        (ch.SouthU, ch.SouthV, 0.48, 0.52),
        (ch.EastU, ch.EastV, 0.50, 0.50),
        (ch.WestU, ch.WestV, 0.49, 0.51),
    ]
    packets: list[bytes] = []
    for uc, vc, u, v in pairs:
        packets.append(build_float(uc, u))
        packets.append(build_float(vc, v))
    packets.append(build_int32(ch.Sequence, seq))
    return packets


async def run_serve(cfg: dict) -> None:
    unity_host = str(cfg.get("unity_host", "127.0.0.1"))
    ports = cfg.get("quadrant_tcp_ports", [18001, 18002, 18003, 18004])
    pose_host = str(cfg.get("pose_udp_host", unity_host))
    pose_port = int(cfg.get("pose_udp_port", 18100))
    fps = float(cfg.get("fps", 30.0))
    period = 1.0 / max(1.0, fps)

    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    writers: list[asyncio.StreamWriter | None] = [None] * 4

    async def ensure_connection(idx: int) -> asyncio.StreamWriter:
        nonlocal writers
        w = writers[idx]
        if w is not None and not w.transport.is_closing():
            return w
        port = int(ports[idx])
        reader, writer = await asyncio.open_connection(unity_host, port)
        writers[idx] = writer
        return writer

    seq = 0
    try:
        while True:
            t0 = time.perf_counter()
            frames = [synthetic_frame(i) for i in range(8)]
            atlas = pack_four_by_two(frames)
            quads = four_vertical_bands(atlas)
            for i, q in enumerate(quads):
                jpeg = encode_jpeg(q)
                try:
                    w = await ensure_connection(i)
                    await tcp_send_jpeg_frame(w, jpeg)
                except (ConnectionRefusedError, OSError, asyncio.CancelledError) as e:
                    writers[i] = None
                    print(f"[hypercube] quadrant {i} send failed ({e}); will retry")

            for pkt in pose_packets(seq):
                udp_sock.sendto(pkt, (pose_host, pose_port))
            seq = (seq + 1) & 0x7FFFFFFF

            elapsed = time.perf_counter() - t0
            await asyncio.sleep(max(0.0, period - elapsed))
    finally:
        udp_sock.close()
        for w in writers:
            if w is not None and not w.transport.is_closing():
                w.close()
                try:
                    await w.wait_closed()
                except Exception:
                    pass


def main() -> None:
    parser = argparse.ArgumentParser(description="HoloCade HyperCube vision service")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_dump = sub.add_parser("dump-atlas", help="Write 5120x2880 synthetic atlas PNG and exit")
    p_dump.add_argument("-o", "--output", type=Path, default=Path("out/atlas.png"))

    p_serve = sub.add_parser("serve", help="Stream quadrants to Unity + UDP pose")
    p_serve.add_argument("-c", "--config", type=Path, default=None, help="YAML config (see config.example.yaml)")

    args = parser.parse_args()
    if args.cmd == "dump-atlas":
        dump_atlas_png(args.output)
        print(f"wrote {args.output}")
        return
    if args.cmd == "serve":
        cfg = load_config(args.config)
        try:
            asyncio.run(run_serve(cfg))
        except KeyboardInterrupt:
            print("stopped")


if __name__ == "__main__":
    main()
