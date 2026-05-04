# HyperCube v0.0.1 → v0.1.0 implementation plan

Goal: **end-to-end dev pipeline** — eight **test** camera feeds → **rectilinear atlas** → **four “360 quadrant” outputs** ingestible by **Unity Cube** passthrough slots, plus **localized face / eye cues** for tracking shims. Target tag **`v0.1.0`** when the checklist below is complete.

---

## Scope boundaries (v0.1.0)

| In scope | Out of scope (later) |
|----------|----------------------|
| **Synthetic or file-based** “8 cameras” (MJPEG files, looping clips, or USB cams mapped to 8 logical IDs) | Real eight-camera genlock / production calibration |
| **Rectilinear 5120×2880 atlas** (4×2 @ 1280×720 per cell, or configurable) | Full GPU equirect warp shipping on AMD |
| **Four quadrant video streams** to Unity (see transport) | 8K HEVC/AV1 at production bitrates |
| **Per-station face anchor** in **atlas UV space** or **world-space** via UDP | Lenticular / full stereo reprojection |
| **Unity**: bind streams to **`CubePassthroughSources`** + **`CubeFaceTrackingProviderBase`** stub | Polished latency hiding, FEC, multi-NIC striping |

---

## Transport split (important)

### Video (four quadrants) — **not** `HoloCadeUDPTransport`

`HoloCadeUDPTransport` (`HoloCade_Unity/Runtime/Core/Networking/HoloCadeUDPTransport.cs`) wraps a **small binary frame**: `SendBytes` caps payload at **255 bytes** per packet. It is intended for **haptics / control / telemetry**, not video.

**v0.1.0 recommendation**

- **Four parallel TCP listeners** on the vision box (e.g. ports **18001–18004**), each sending **MJPEG** (`multipart/x-mixed-replace`) or **length-prefixed JPEG** chunks for one quadrant. MJPEG is easy to parse in Unity for a first vertical slice.
- **Alternative:** one **HTTP** server with four paths `/q0` … `/q3` and `UnityWebRequest` + `Texture2D.LoadImage` (slower but simplest smoke test).

**Unity:** small **`HyperCubeStreamIngest`** (new runtime script under HoloCade Cube or HoloSnake) that decodes each stream into a **`Texture2D`** or **`RenderTexture`**, then assigns **`CubePassthroughSources`** fields (runtime instance, not only asset refs) for N/S/E/W → map **quadrant index → portal side** per your authored convention (document the mapping table).

### Face / eye “localized updates” — **HoloCade UDP-compatible**, small payloads

**Yes, use the same framing as HoloCade** so Unity can reuse **`HoloCadeUDPTransport`** (or a thin sibling) **without** bloating packets:

- Encode **per side** (North / South / East / West): e.g. **eye center** in **atlas-normalized** `(u,v)` plus **confidence** and **`uint32` sequence** — fits as **multiple `SendFloat` / `SendInt32` calls on dedicated channels** (one scalar per packet today), or a **struct ≤ ~240 bytes** if you later raise the cap.
- **Python sender:** implement **`BuildBinaryPacket`** mirror: `[0xAA][type][channel][payload…][xor_crc8]` matching `HoloCadeUDPTransport.CalculateCRC` (XOR over all bytes before CRC).
- **Channel map (draft):** reserve bands e.g. **100–119** for HyperCube pose (floats for `u,v`, confidence; int for seq; optional world-space later). Document in code as constants shared with Unity.

**Why not one big protobuf on UDP here?** Stay under existing limits until you add **`HyperCubeUDPTransport`** with a **64 KiB** cap or fragmentation — not required for v0.1.0 if you use **float channels**.

---

## HyperCube (Python) — module layout

```
src/holocade_hypercube/
  __init__.py
  version.py
  config.py                 # YAML or dataclass: ports, paths, atlas layout
  feeds/
    base.py                 # FrameSource protocol
    file_mjpeg.py           # 8 paths, loop
    synthetic.py            # colored tiles + optional noise (no hardware)
  atlas/
    packer.py               # 8 → 5120x2880 rectilinear grid
    pair_selector.py        # L/R per pair (stub: fixed or bbox heuristic)
  output/
    quadrants.py            # crop atlas → 4 textures (same res or downscale)
    tcp_mjpeg_server.py     # asyncio: 4 ports, non-blocking send
  net/
    holocade_udp_pose.py    # XOR-CRC packets, SendFloat-compatible
  pipeline.py               # asyncio main: acquire → pack → quadrant → encode → net
  cli.py                    # `uv run python -m holocade_hypercube serve`
```

**v0.1.0 pipeline steps**

1. **Acquire** eight frames (same wall-clock `t`; monotonic `frame_id`).
2. **Optional:** run **MediaPipe Face Landmarker** on **full atlas** or **per-tile crops** → **bbox centers** → drive **`pair_selector`** (which camera tile is “live” for that station).
3. **`packer`:** write eight cells into **5120×2880** BGR/RGB buffer.
4. **`quadrants`:** define **four** fixed ROIs that correspond to your **360° partition** (for v0.1, literal **quarter-annulus in UV** can be approximated by **four large crops** or **four pre-authoured rects** in atlas space — document that this is a **stand-in** until real equirect unwrap exists).
5. **Encode** each quadrant to **JPEG** (OpenCV `imencode`).
6. **Serve** TCP MJPEG + **emit UDP pose** bundle per frame (or 30 Hz decimated).

---

## Unity (HoloCade / HoloSnake) — minimal additions

1. **`HyperCubeQuadrantReceiver`** — four lightweight coroutines or **Unity.Collections** jobs that read TCP streams, decode JPEG → **`Texture2D`**, upload to GPU.
2. **`CubePassthroughRuntimeBinder`** — assigns textures to the rig (reference `CubeRigController` / `CubePassthroughSources` — may require **public setter** or **ScriptableObject** duplicate at runtime if asset is immutable).
3. **`HyperCubeUDPTrackingShim` : `CubeFaceTrackingProviderBase`** — reads last **`HoloCadeUDPTransport`** float cache for channels **100–119**, converts **(u,v) atlas** → **approximate world eye** using **`CubeRigController`** side anchors / monitor dims (`TryGetCubeDimensionsMeters` / side transforms). v0.1 can use **flat billboard** approximation.
4. **Scene wiring:** vision PC IP, ports, UDP bind on game PC.

---

## Milestone slices (suggested tags)

| Tag | Deliverable |
|-----|----------------|
| **v0.0.2** | Eight `FileMjpeg` sources + atlas packer + **offline** PNG dump (sanity). |
| **v0.0.3** | TCP MJPEG **one** quadrant from Python; **netcat** or browser smoke. |
| **v0.0.4** | Four TCP MJPEG servers; Python **UDP pose** XOR-CRC verified with **unit test** against golden vectors from C#. |
| **v0.0.5** | Unity: one quadrant → one **`CubePassthroughSources`** slot + visible portal. |
| **v0.0.6** | Unity: four quadrants + **channel map** doc; **L/R selector** stub in Python. |
| **v0.0.7** | MediaPipe on atlas (multi-face) → **station assignment** by atlas region; UDP drives **`CubeFaceTrackingProviderBase`**. |
| **v0.1.0** | README “run book”, default **config.example.yaml**, **Windows + Linux** smoke notes, version bump. |

---

## Risks & mitigations (v0.1.0)

- **JPEG CPU cost @ 60fps × 4:** drop to **30fps** for v0.1 or lower quadrant res.
- **Unity decode on main thread:** move to **AsyncGPUReadback**-friendly path or **native plugin** in v0.2.
- **UDP coexisting with Cabinet Pi traffic:** use **dedicated UDP port** and **VLAN**; do not share the Pico command port.

---

## Version file

Bump **`pyproject.toml`** / **`__version__`** to **`0.1.0`** only when the **v0.1.0** checklist is green; keep **`0.0.x`** during the slices above.
