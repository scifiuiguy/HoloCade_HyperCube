# Copyright (c) 2025 AJ Campbell. Licensed under the MIT License.
"""Run vision loop: 8 synthetic feeds → atlas → 4 quadrants → TCP JPEG to Unity + HoloCade UDP pose."""

from __future__ import annotations

import argparse
import asyncio
import socket
import struct
import time
from pathlib import Path

import cv2
import numpy as np
import yaml

from holocade_hypercube.atlas.packer import CELL_H, CELL_W, pack_four_by_two
from holocade_hypercube.calibration import StereoRectifier, stereo_rectifier_from_config
from holocade_hypercube.feeds.pipeline_test_video import (
    PipelineTestVideoConfig,
    PipelineTestVideoPlayer,
    pipeline_test_video_frames,
)
from holocade_hypercube.feeds.synthetic import synthetic_frame
from holocade_hypercube.protocol.holocade_udp import build_float, build_int32
from holocade_hypercube.quadrants.split import four_vertical_bands
from holocade_hypercube.stereo_depth import StereoDepthResult, stereo_depth_estimator_from_config


def encode_jpeg(bgr) -> bytes:
    ok, buf = cv2.imencode(".jpg", bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
    if not ok:
        raise RuntimeError("jpeg encode failed")
    return buf.tobytes()


def _image_orientation(width: int, height: int) -> str:
    return "landscape" if width >= height else "portrait"


def _fit_to_cell_same_orientation(image_bgr, cell_width: int, cell_height: int):
    src_h, src_w = image_bgr.shape[:2]
    if src_h == cell_height and src_w == cell_width:
        return image_bgr
    src_orientation = _image_orientation(src_w, src_h)
    dst_orientation = _image_orientation(cell_width, cell_height)
    if src_orientation != dst_orientation:
        raise ValueError(
            f"orientation mismatch: source {src_w}x{src_h} is {src_orientation}, "
            f"cell {cell_width}x{cell_height} is {dst_orientation}"
        )

    src_aspect = src_w / src_h
    dst_aspect = cell_width / cell_height

    if src_aspect > dst_aspect:
        crop_w = int(src_h * dst_aspect)
        x0 = max(0, (src_w - crop_w) // 2)
        cropped = image_bgr[:, x0 : x0 + crop_w]
    else:
        crop_h = int(src_w / dst_aspect)
        y0 = max(0, (src_h - crop_h) // 2)
        cropped = image_bgr[y0 : y0 + crop_h, :]
    return cv2.resize(cropped, (cell_width, cell_height), interpolation=cv2.INTER_AREA)


def _pipeline_test_png_frames(
    cfg: dict, cell_width: int, cell_height: int, rectifier: StereoRectifier | None = None
):
    images_dir = Path(str(cfg.get("pipeline_test_images_dir", "pipeline-test-images")))
    left_name = str(cfg.get("pipeline_test_left_image", "face_left.png"))
    right_name = str(cfg.get("pipeline_test_right_image", "face_right.png"))
    left_path = images_dir / left_name
    right_path = images_dir / right_name
    left = cv2.imread(str(left_path), cv2.IMREAD_COLOR)
    right = cv2.imread(str(right_path), cv2.IMREAD_COLOR)
    if left is None:
        raise FileNotFoundError(f"pipeline_test_png missing left image: {left_path}")
    if right is None:
        raise FileNotFoundError(f"pipeline_test_png missing right image: {right_path}")
    if rectifier is not None and rectifier.active:
        left, right = rectifier.rectify_pair(left, right)
    left = _fit_to_cell_same_orientation(left, cell_width, cell_height)
    right = _fit_to_cell_same_orientation(right, cell_width, cell_height)
    # Logical camera order: L,R repeated across four side pairs.
    return [left, right, left, right, left, right, left, right]


def _depth_debug_viz(result: StereoDepthResult) -> "cv2.typing.MatLike | None":
    if result.depth_z_m is None:
        return None
    z = result.depth_z_m
    valid = result.valid_mask
    if not valid.any():
        return None
    zmin = float(np.percentile(z[valid], 5))
    zmax = float(np.percentile(z[valid], 95))
    if not (zmax > zmin):
        return None
    zn = (np.clip(z, zmin, zmax) - zmin) / (zmax - zmin)
    img = (zn * 255.0).astype(np.uint8)
    img[~valid] = 0
    return cv2.applyColorMap(img, cv2.COLORMAP_TURBO)


def _valid_mask_viz(result: StereoDepthResult) -> "cv2.typing.MatLike":
    m = (result.valid_mask.astype(np.uint8) * 255)
    return cv2.cvtColor(m, cv2.COLOR_GRAY2BGR)


def _disparity_viz(result: StereoDepthResult) -> "cv2.typing.MatLike":
    # Visualize ROI disparity (not full-frame) so we can see sign/structure quickly.
    d = result.disparity_px
    if d.size == 0:
        return np.zeros((8, 8, 3), dtype=np.uint8)
    dv = d.copy()
    # Robust stretch using percentiles over finite values.
    finite = np.isfinite(dv)
    if not finite.any():
        return np.zeros((d.shape[0], d.shape[1], 3), dtype=np.uint8)
    lo = float(np.percentile(dv[finite], 5))
    hi = float(np.percentile(dv[finite], 95))
    if not (hi > lo):
        hi = lo + 1.0
    dn = (np.clip(dv, lo, hi) - lo) / (hi - lo)
    img = (dn * 255.0).astype(np.uint8)
    return cv2.applyColorMap(img, cv2.COLORMAP_TURBO)


def _build_frames(
    cfg: dict,
    cell_width: int,
    cell_height: int,
    rectifier: StereoRectifier | None = None,
    video_player: PipelineTestVideoPlayer | None = None,
):
    feed_mode = str(cfg.get("feed_mode", "synthetic")).strip().lower()
    if feed_mode == "synthetic":
        return [synthetic_frame(i, width=cell_width, height=cell_height) for i in range(8)]
    if feed_mode == "pipeline_test_png":
        return _pipeline_test_png_frames(
            cfg, cell_width=cell_width, cell_height=cell_height, rectifier=rectifier
        )
    if feed_mode == "pipeline_test_video":
        if video_player is None:
            raise ValueError("pipeline_test_video requires a video player")
        return pipeline_test_video_frames(
            video_player,
            cell_width=cell_width,
            cell_height=cell_height,
            rectifier=rectifier,
            fit_to_cell_same_orientation=_fit_to_cell_same_orientation,
        )
    raise ValueError(f"unsupported feed_mode: {feed_mode}")


def _build_quadrants_from_atlas(
    cfg: dict,
    atlas,
    cell_width: int,
    cell_height: int,
    out_width: int | None,
    out_height: int | None,
):
    quadrant_layout_mode = str(cfg.get("quadrant_layout_mode", "vertical_bands")).strip().lower()
    if quadrant_layout_mode == "vertical_bands":
        return four_vertical_bands(
            atlas,
            cell_width=cell_width,
            cell_height=cell_height,
            out_width=out_width,
            out_height=out_height,
        )
    if quadrant_layout_mode == "atlas_preview":
        return [atlas, atlas, atlas, atlas]
    raise ValueError(f"unsupported quadrant_layout_mode: {quadrant_layout_mode}")


def dump_atlas_png(path: Path, cfg: dict) -> None:
    cell_width = int(cfg.get("cell_width", CELL_W))
    cell_height = int(cfg.get("cell_height", CELL_H))
    rectifier = stereo_rectifier_from_config(cfg)
    frames = _build_frames(cfg, cell_width=cell_width, cell_height=cell_height, rectifier=rectifier)
    atlas = pack_four_by_two(frames, cell_width=cell_width, cell_height=cell_height)
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
    cell_width = int(cfg.get("cell_width", CELL_W))
    cell_height = int(cfg.get("cell_height", CELL_H))
    out_width = cfg.get("quadrant_output_width")
    out_height = cfg.get("quadrant_output_height")

    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    writers: list[asyncio.StreamWriter | None] = [None] * 4

    async def ensure_connection(idx: int) -> asyncio.StreamWriter:
        nonlocal writers
        w = writers[idx]
        if w is not None and not w.transport.is_closing():
            return w
        port = int(ports[idx])
        # On some Windows setups, connecting to a closed localhost port can hang
        # rather than raising ConnectionRefusedError quickly. Bound the connect time.
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(unity_host, port),
            timeout=0.25,
        )
        writers[idx] = writer
        return writer

    rectifier = stereo_rectifier_from_config(cfg)
    depth_estimator = stereo_depth_estimator_from_config(cfg)
    depth_debug_every_n = int(cfg.get("stereo_depth_debug_every_n", 0))
    depth_debug_out_dir = Path(str(cfg.get("stereo_depth_debug_out_dir", "out")))
    video_player: PipelineTestVideoPlayer | None = None
    if str(cfg.get("feed_mode", "synthetic")).strip().lower() == "pipeline_test_video":
        video_player = PipelineTestVideoPlayer(PipelineTestVideoConfig.from_cfg(cfg))
    seq = 0
    try:
        while True:
            t0 = time.perf_counter()
            frames = _build_frames(
                cfg,
                cell_width=cell_width,
                cell_height=cell_height,
                rectifier=rectifier,
                video_player=video_player,
            )

            # v0.0.5: stereo depth (CPU SGBM fallback).
            if (
                depth_estimator is not None
                and str(cfg.get("feed_mode", "synthetic")).strip().lower() == "pipeline_test_png"
                and len(frames) >= 2
            ):
                result = depth_estimator.estimate(
                    frames[0],
                    frames[1],
                    Q=rectifier.Q if rectifier.active else None,
                    roi_cfg=cfg,
                )
                if depth_debug_every_n > 0 and (seq % depth_debug_every_n) == 0:
                    viz = _depth_debug_viz(result)
                    if viz is not None:
                        depth_debug_out_dir.mkdir(parents=True, exist_ok=True)
                        cv2.imwrite(str(depth_debug_out_dir / f"depth_debug_{seq:06d}.png"), viz)
                        cv2.imwrite(
                            str(depth_debug_out_dir / f"depth_valid_{seq:06d}.png"),
                            _valid_mask_viz(result),
                        )
                        cv2.imwrite(
                            str(depth_debug_out_dir / f"depth_disp_{seq:06d}.png"),
                            _disparity_viz(result),
                        )
                    else:
                        depth_debug_out_dir.mkdir(parents=True, exist_ok=True)
                        fallback = frames[0].copy()
                        cv2.putText(
                            fallback,
                            "depth_debug: no valid depth",
                            (20, 60),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            1.2,
                            (0, 0, 255),
                            3,
                            cv2.LINE_AA,
                        )
                        cv2.imwrite(str(depth_debug_out_dir / f"depth_debug_{seq:06d}_noviz.png"), fallback)
                        cv2.imwrite(
                            str(depth_debug_out_dir / f"depth_valid_{seq:06d}.png"),
                            _valid_mask_viz(result),
                        )
                        cv2.imwrite(
                            str(depth_debug_out_dir / f"depth_disp_{seq:06d}.png"),
                            _disparity_viz(result),
                        )
            atlas = pack_four_by_two(frames, cell_width=cell_width, cell_height=cell_height)
            quads = _build_quadrants_from_atlas(
                cfg,
                atlas,
                cell_width=cell_width,
                cell_height=cell_height,
                out_width=out_width,
                out_height=out_height,
            )
            for i, q in enumerate(quads):
                jpeg = encode_jpeg(q)
                try:
                    w = await ensure_connection(i)
                    await tcp_send_jpeg_frame(w, jpeg)
                except (TimeoutError, ConnectionRefusedError, OSError, asyncio.CancelledError) as e:
                    writers[i] = None
                    print(f"[hypercube] quadrant {i} send failed ({e}); will retry")

            for pkt in pose_packets(seq):
                udp_sock.sendto(pkt, (pose_host, pose_port))
            seq = (seq + 1) & 0x7FFFFFFF

            elapsed = time.perf_counter() - t0
            await asyncio.sleep(max(0.0, period - elapsed))
    finally:
        if video_player is not None:
            video_player.close()
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

    p_dump = sub.add_parser("dump-atlas", help="Write atlas PNG and exit")
    p_dump.add_argument("-o", "--output", type=Path, default=Path("out/atlas.png"))
    p_dump.add_argument("-c", "--config", type=Path, default=None, help="YAML config (see config.example.yaml)")

    p_serve = sub.add_parser("serve", help="Stream quadrants to Unity + UDP pose")
    p_serve.add_argument("-c", "--config", type=Path, default=None, help="YAML config (see config.example.yaml)")

    args = parser.parse_args()
    if args.cmd == "dump-atlas":
        cfg = load_config(args.config)
        dump_atlas_png(args.output, cfg)
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
