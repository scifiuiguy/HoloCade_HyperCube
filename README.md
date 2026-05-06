# HoloCade HyperCube (Linux vision service)

Companion repository for **HoloCade Cube** deployments that split **camera capture + MediaPipe + passthrough compositing** onto a **Linux Mini-ITX**, while **Unity on Windows** runs the game and display rig.

Canonical hardware and topology narrative: **`../CubeModule_README.md`** (dual PC, Ethernet, per-display flank stereo cameras).

---

## Unity loopback (dev)

1. In a scene with **`CubeRigController`**, add **`HyperCubeQuadrantTcpHost`** (default ports **18001–18004**), **`HoloCadeUDPTransport`** (**Role** = **Local listener**, **listener port** **18100**, bind **0.0.0.0**), **`HyperCubePassthroughBinder`** (wire `cubeRig` + `quadrantHost`), and optionally **`HyperCubePoseTrackingProvider`** on the same object as `CubeRigController`’s **`faceTrackingProvider`** (assign the **`HoloCadeUDPTransport`**, **`cubeRoot`** = rig transform).  
2. Enter Play Mode so TCP listeners and UDP bind are active.  
3. From this repo: `uv run hypercube-serve serve -c config.example.yaml` (or copy to `config.yaml`). HyperCube connects **outbound** to Unity and sends **big-endian uint32 + JPEG** per quadrant per frame, plus **HoloCade-compatible UDP** pose packets.

Ports are set in **`config.example.yaml`**; mirror the same values on the Unity components.

---

## Network baseline (vision ↔ game PC)

Documentation assumes **two Mini-ITX units** (reference: **AOOSTAR MACO** or equivalent), each with **dual 2.5GbE** on the **default** BOM. The HyperCube service should target **compressed** passthrough (**AV1** preferred where encode/decode are both controlled; **HEVC** as fallback) and may **stripe** high-bitrate traffic across **both NICs** (two cable runs) for aggregate headroom.

**Optional ~US$400 upgrade:** each MACO can use **OCuLink** to a **PCIe x4 riser** plus **dual-port SFP28** NICs and a **DAC** for a **direct 25Gb/s-class** link between vision and game PCs (see **`CubeModule_README.md`** for a **Gemini-estimated parts list** ~**$381** new). That path is **not** onboard RJ45 10G—it is **SFP28**. **USB4 10G-T dongles** remain another optional path.

---

## Python environment (`uv` + `.venv`)

This repo uses **[uv](https://docs.astral.sh/uv/)** so dependencies are **locked** (`uv.lock`) and isolated in **`.venv/`** (not your global Python).

**Prerequisite:** [Install uv](https://docs.astral.sh/uv/getting-started/installation/) (one-time on each machine).

| Command | What it does |
|--------|----------------|
| `uv sync` | Create/update **`.venv`**, install **`pyproject.toml`** dependencies (MediaPipe pulls OpenCV). Uses **Python 3.11** via `.python-version`. |
| `uv sync --extra cuda` | Also install **PyTorch + torchvision** built for **CUDA 12.4** (large download; use on NVIDIA dev laptops like RTX 3070). |
| `uv lock` | Refresh **`uv.lock`** after you edit dependencies (or run `uv add <package>`). |
| `uv run python …` | Run a script with the venv active, e.g. `uv run python -c "import mediapipe as mp; print(mp.__version__)"`. |
| `uv run hypercube-serve dump-atlas -c config.yaml -o out/atlas.png` | Write atlas PNG using **`cell_width`/`cell_height`** and **`feed_mode`** from config (default synthetic still works without `-c`). |
| `uv run hypercube-serve serve -c config.yaml` | Stream **four TCP JPEG** quadrants to Unity + **UDP pose** (see **Unity loopback** below). |
| `uv run python -m unittest discover -s tests -v` | Run unit tests. |

**Add a dependency:** `uv add httpx` (example) — updates `pyproject.toml` and `uv.lock`.

**Commit:** check in **`pyproject.toml`** and **`uv.lock`**. Do **not** commit **`.venv/`** (already gitignored).

---

## Why this repo exists

- **MediaPipe in Unity (C#)** is not the preferred place for **multi-stream GPU inference** and custom compositing across eight (or more) physical cameras.
- **Python MediaPipe** (Tasks API: Face Landmarker, etc.) on Linux is a well-supported path for experimentation and production prototypes, with clear upgrade routes to C++ services if latency demands it.
- This repo will hold **Linux-side** capture, inference, **texture generation** (per-side and/or omnidirectional), and a **network server** that streams results to the Windows game PC.

---

## Suggested stack (starting point)

| Layer | Recommendation |
|-------|----------------|
| **Inference** | **Python 3.11+** + **`mediapipe`** Tasks (Face Landmarker, optional pose). Use one process per GPU or a worker pool; batch where the API allows. |
| **Compositing** (N×camera → equirect or tiled atlas) | Prefer **GPU** once CPU proves too slow. On **AMD** (typical with a **Ryzen 7** class Mini-ITX using **Radeon integrated** or discrete graphics), **CUDA is not available** (NVIDIA-only). Practical order: **CPU OpenCV** / **NumPy** prototypes → **Vulkan compute** (or **ROCm/HIP** if you standardize on ROCm-supported AMD GPUs and want PyTorch-style warps) → vendor-tuned paths as needed. **OpenCV’s CUDA module** only helps on NVIDIA. |
| **Video encode to Windows** | Depends on wire format: **NDI**, **SRT**, **AMD AMF** / **VA-API** (common on Linux with AMD), **custom UDP** + lightweight tile compression, or **raw tiles** on a fat link. **NVENC** applies only to NVIDIA. Document bandwidth and latency budgets alongside the protocol. |
| **Pose / metadata** | Small JSON or protobuf over **TCP/WebSocket** or a side channel multiplexed with video; include **monotonic timestamps** for Unity to align with frames. |

**AMD (Ryzen + Radeon) vs NVIDIA:** If the vision box is **AMD GPU**, plan compositing around **Vulkan compute** (portable, good fit for custom equirect/atlas warps) and/or **ROCm** where you need **PyTorch** on the GPU. **CUDA** remains the right answer only for **NVIDIA** stacks (**OpenCV CUDA**, TensorRT, NVENC). **MediaPipe** Tasks often run **CPU** or **TFLite**-style delegates first; treat GPU acceleration for inference as a separate validation step per platform build.

---

## Development on Windows 11 (e.g. RTX 3070 laptop, no Linux Mini-ITX yet)

You can do **most of the HyperCube *application* work** on the laptop; the missing box mainly delays **Linux-specific** I/O, **AMD GPU** paths, and **final latency** on real silicon.

**Straightforward on Windows now**

- **Python environment:** `mediapipe`, `opencv-python-headless`, **`torch` with CUDA** for the 3070 if you prototype warps or learning-style compositing on NVIDIA.
- **MediaPipe Tasks** (Face Landmarker, etc.), **batching**, **logging**, **unit tests**, and **synthetic / pre-recorded** multi-camera inputs (video files, duplicated streams, or a few USB webcams) to validate **per-frame logic**.
- **Wire protocol and server:** pose JSON/protobuf, timestamps, TCP/WebSocket or UDP framing, a **fake client** that replays captures—**all portable** to Linux later.
- **CPU compositing baseline:** equirect or atlas math in NumPy/OpenCV **CPU** first; correct before optimizing for GPU.
- **Unity side:** ingest mock packets / test pattern textures on the **same** Windows machine (loopback) without the vision PC.

**Optional Linux-like smoke tests**

- **WSL2 Ubuntu** with NVIDIA CUDA toolkit can approximate a Linux deploy for scripting and some native builds; GPU coverage in WSL depends on your driver stack—treat it as **supplementary**, not a full substitute for the real vision PC.

**Defer until Linux + AMD (or lab rig)**

- **Production compositor** on **Vulkan compute** or **ROCm**-backed PyTorch tuned for **Radeon**.
- **Linux capture** quirks: **v4l2** multi-device sync, **real eight streams**, USB bandwidth, headless systemd services.
- **Encode path** you will ship on AMD (**VA-API / AMF** vs dev-time **NVENC** experiments on the 3070).

**Practical split:** implement a **CompositorBackend** interface (CPU → PyTorch/CUDA on dev → Vulkan or CPU on prod) so **algorithmic** work stays shared while **GPU backends** swap per platform.

---

## Repository layout (evolving)

```
HoloCade_HyperCube/
  README.md                 # this file
  docs/                     # protocol drafts, calibration notes (as they land)
  pipeline-test-images/     # local only: drop flank PNGs here for v0.0.3 harness (gitignored)
  src/                      # Python package `holocade_hypercube`
```

Source layout will grow as services are implemented.

---

## Relationship to HoloCade_Unity

- **Unity** consumes **`CubePassthroughSources`** and **`CubeFaceTrackingProviderBase`**; those types stay in `HoloCade_Unity`.
- **HyperCube** is responsible for everything **up to** the network boundary: timestamps, calibrated warps, encoded frames, and pose packets compatible with the Windows ingest layer (to be implemented in Unity or a small native bridge).

---

## 🗺️ Roadmap

Full implementation checklist, module layout, risks, and milestone definitions: **`docs/VERSION_0_1_0_PLAN.md`**.

<details>
<summary><strong>v0.0.1 (Current — Pre-Alpha)</strong></summary>

<blockquote>

### ✅ Baseline
- ✅ **uv / Python scaffold** — `pyproject.toml`, `uv.lock`, `.python-version` (3.11), editable package `holocade_hypercube`
- ✅ **Hardware & transport docs** — dual **2.5GbE** default, optional **OCuLink + SFP28** BOM (see `CubeModule_README.md`), dev-on-Windows notes
- ✅ **v0.1.0 plan artifact** — `docs/VERSION_0_1_0_PLAN.md` (end-to-end slice definition)

</blockquote>

</details>

<details>
<summary><strong>v0.0.2 (Complete)</strong></summary>

<blockquote>

### ✅ Completed (v0.0.2)

#### Atlas & compositing
- ✅ **Rectilinear 5120×2880 packer** — `atlas/packer.py` (`pack_four_by_two`): default **4×2** grid @ **1280×720** per cell
- ✅ **Stand-in quadrant split** — `quadrants/split.py` (`four_vertical_bands`): atlas → **four vertical bands** for early TCP/JPEG smoke (**not** final equirect / annulus ROIs; those stay on the v0.1.0 plan)

#### Feeds
- ✅ **Eight synthetic BGR feeds** — `feeds/synthetic.py` (`synthetic_frame`): **NumPy-first** colored tiles per logical camera index (**no** v4l2, disk MJPEG loop, or USB mapping in this tag)

#### HoloCade-compatible pose (stub)
- ✅ **Binary packet builder** — `protocol/holocade_udp.py`: `[0xAA][type][channel][payload][xor_crc8]`, `build_float` / `build_int32`, CRC aligned with **`HoloCadeUDPTransport`** semantics
- ✅ **Draft pose channel IDs** — `pose_channels.py` (`HyperCubePoseChannelIds`): per-side **u,v** floats + shared **`Sequence`** int channel
- ✅ **Stub pose bundle in the serve loop** — `serve.py` emits placeholder **(u,v)** per cardinal side + **seq** each frame while **`serve`** runs

#### CLI, config, and packaging
- ✅ **`hypercube-serve` console script** — `pyproject.toml` → `holocade_hypercube.serve:main` with subcommands **`dump-atlas`** and **`serve`**
- ✅ **YAML-driven settings** — `config.example.yaml`: `unity_host`, `quadrant_tcp_ports` (**18001–18004**), `pose_udp_host` / `pose_udp_port` (**18100**), `fps`
- ✅ **Offline atlas PNG** — `uv run hypercube-serve dump-atlas -o out/atlas.png` (writes **5120×2880** synthetic atlas and exits)

#### Runtime loop (dev ↔ Unity loopback)
- ✅ **Outbound TCP quadrant JPEG** — per-quadrant **big-endian uint32 length + JPEG** to `unity_host`:**ports**; reconnects when a send fails (matches **Unity loopback** wiring in this README)
- ✅ **UDP pose datagrams** — same loop sends stub packets to the configured pose host/port

#### Tests
- ✅ **UDP packet unit test** — `tests/test_holocade_udp_packet.py` (marker, type, channel, float payload LE, XOR CRC8)

#### Explicitly out of scope for this tag
- [ ] **Eight `FileMjpeg` / USB** sources — carried forward as **[ ] Eight feeds from MJPEG files or USB** under **v0.1.0** below

</blockquote>

</details>

<details>
<summary><strong>v0.0.3 (Complete) — Static flank PNG harness</strong></summary>

<blockquote>

**Goal:** Feed **real still images** through the same **atlas → quadrant → TCP JPEG** path as production, so you can confirm **pixels** and **layout** in Unity **without** cameras or MJPEG files yet.

### ✅ Completed (v0.0.3)

#### Cell geometry — **portrait or landscape** (early; applies to test PNGs **and** live feeds)
- ✅ **Config-driven cell size** — YAML selects **`cell_width` × `cell_height`** (and thus atlas footprint), e.g. **landscape** `1280×720` *(default)* or **portrait** `720×1280`. Portrait sources are **not** forced into a landscape cell; orientation mismatch raises at runtime. Packing uses **`4·cell_w × 2·cell_h`**; optional **`quadrant_output_width` / `quadrant_output_height`** downscale TCP JPEG per quadrant.
- ✅ **Refactor hard-coded constants** — **`pack_four_by_two(..., cell_width, cell_height)`** drives atlas size; **`four_vertical_bands`** validates against derived atlas size and defaults output to cell dimensions; **`synthetic_frame(w,h)`** and **`dump-atlas`** (`-c config.yaml`) use the same contract. *(Legacy `CELL_W` / `CELL_H` / `ATLAS_*` in `packer.py` remain as defaults only.)*

#### `pipeline-test-images/` (local drops)
- ✅ **Directory** — `pipeline-test-images/` at repo root; raster assets **gitignored** (see `.gitignore`); filenames configurable (`pipeline_test_left_image` / `pipeline_test_right_image`; defaults `face_left.png`, `face_right.png`). See `pipeline-test-images/README.md`.
- ✅ **Eight logical cameras from two files** — load both as **BGR**; **resize/crop only when size ≠ cell**, **same orientation only** (no portrait→landscape rotation); indices **`L,R,L,R,L,R,L,R`**.
- ✅ **`feeds/` wiring** — **`feed_mode: pipeline_test_png`** implemented in **`serve.py`** (`_pipeline_test_png_frames`, `_fit_to_cell_same_orientation`). *Optional later refactor:* extract to **`feeds/pipeline_test_png.py`** + a small **FrameSource** protocol.
- ✅ **Config + CLI** — `feed_mode`, `pipeline_test_*`, `cell_width` / `cell_height`, **`quadrant_layout_mode`** (`vertical_bands` | `atlas_preview`); `hypercube-serve serve -c …` and **`dump-atlas -c …`**.

#### Validation
- ✅ **HyperCube + Unity loopback** — four TCP JPEG quadrants + stub UDP; **`pipeline_test_png`** mode exercised against portrait flank PNGs.

</blockquote>

</details>

<details>
<summary><strong>v0.0.4 (Complete) — Undistort + stereo rectification</strong></summary>

<blockquote>

**Goal:** Per **physical L/R pair**, apply **known intrinsics + extrinsics** so **epipolar lines align** before any stereo matcher or MediaPipe consumer.

### ✅ Completed (v0.0.4)

#### Calibration artifact format
- ✅ **JSON per stereo pair** — **camera matrices, distortion coeffs, stereo R|T**; configured via `stereo_rectify_mode` + `stereo_calibration_json` (example: `calibration/example_stereo_pair.json`).

#### Remap stage
- ✅ **Undistort + stereo rectification** — `cv2.stereoRectify` + `initUndistortRectifyMap` + `remap` applied in `pipeline_test_png` before `_fit_to_cell_same_orientation`; **no-op** when mode is `none`.

#### Docs
- ✅ **Capture + QC notes** — `docs/CAMERA_CALIBRATION.md` (Charuco, LED-metronome sync, pose diversity, GoPro cautions, factory jig concept including **five-panel “star”**).

</blockquote>

</details>

<details>
<summary><strong>v0.0.5 (Planned) — Stereo depth (Vulkan primary, CPU fallback)</strong></summary>

<blockquote>

**Goal:** **Dense or semi-dense depth** from **rectified L/R** on a **down-res ROI** (2–3 ft working range, **min/max disparity** clamp, **OOB** disables tracking).

- [ ] **Vulkan compute** path on **Radeon** target (SGM / AD-Census class or tuned simpler matcher first).
- [ ] **CPU fallback** — OpenCV `StereoSGBM` / `StereoBM` for Windows dev / bring-up.
- [ ] **Output** — disparity or **metric depth** map in a frame agreed with fusion (same clock as rectified left **preferred**, loose coupling OK per design).
- [ ] **Parallel to atlas** — stereo runs on **pair buffers**; **does not** require atlas-first packing.

</blockquote>

</details>

<details>
<summary><strong>v0.0.6 (Planned) — MediaPipe + L/R selection + fusion → `vec3`</strong></summary>

<blockquote>

**Goal:** **Sibling branch** to stereo: both consume **rectified RGB** (typical: **Face Landmarker** on **rectified left** or a **face ROI**); combine with **depth** for **Linux-side** head position.

- [ ] **MediaPipe Face Landmarker** — wire Tasks API; choose **input resolution** deliberately (atlas-wide **vs** per-station crop documented).
- [ ] **L/R flank policy** — stub **center + buffer** rule so **one** flank’s stream drives landmarks when appropriate (no dual tracking).
- [ ] **Fusion** — each frame (or each stereo frame): **latest (u,v)** landmark → **sample depth** at that location (patch median optional) → **back-project** to **`vec3`** in **camera / cube / world** (document frame); attach **confidence** + **seq**.
- [ ] **Not** the same compute module as Vulkan stereo — **pipeline graph** handoff (GPU → CPU or shared memory) is explicit.

</blockquote>

</details>

<details>
<summary><strong>v0.0.7 (Planned) — UDP `vec3` + Unity ingest</strong></summary>

<blockquote>

**Goal:** HoloCade-compatible **UDP** carries **3D head position** (and seq/confidence); **TCP JPEG quadrants** stay the **parallel** passthrough path (**no lockstep** with pose required for first ship; document optional timestamps).

- [ ] **Channel map** — extend `pose_channels.py` ↔ `HyperCubePoseChannelIds.cs` (e.g. **three floats per side** for position + existing **seq**; or per-player layout if cube grows beyond four sides).
- [ ] **Python emitter** — `build_float` × N per bundle; keep under **`HoloCadeUDPTransport`** per-packet limits unless a negotiated extension lands later.
- [ ] **Unity** — **`HoloCadeUDPTransport`** (listener) + **`HyperCubePoseTrackingProvider`** (or successor) read **`Vector3`** (not stub **u,v → fake Z**); `CubeRigController` / tracking hookup validated in Play Mode.
- [ ] **Golden-vector tests** — Python UDP bytes vs C# CRC/layout (extend `tests/test_holocade_udp_packet.py` or add vectors file).

</blockquote>

</details>

<details>
<summary><strong>v0.1.0 (Planned) — Release gate</strong></summary>

<blockquote>

**Goal:** Close the **dev vertical slice**: file or PNG/MJPEG feeds, **stand-in** quadrant ROIs (full **equirect** unwrap later), **run book**, tag **`v0.1.0`**, **`pyproject.toml` / `__version__` bump**.

#### Still on the checklist for this tag
- [ ] **Eight feeds from disk or live** — `pipeline-test-images` **PNG** harness ✅ *(v0.0.3)* **plus** optional **MJPEG file loops** / **USB** mapping into the same eight-slot contract; **same cell orientation** (portrait vs landscape) as config for test and live.
- [x] **Rectilinear atlas** for passthrough — **5120×2880** packer *(v0.0.2, landscape cells only)*; **v0.0.3+** generalizes atlas size from **configurable cell** `W×H` **× 4×2** (document portrait atlas footprint when `cell_height > cell_width`).
- [ ] **Four quadrant TCP JPEG** to Unity — ports **18001–18004** (or HTTP smoke); bind **`CubePassthroughSources`** at runtime (**`HyperCubePassthroughBinder`** path).
- [ ] **Four “360 quadrant” crops** — **stand-in** geometry (current vertical bands or improved ROIs); **not** final equirect until a later milestone.
- [ ] **Unity (HoloCade_Unity) — paired** — procedural **interior sphere** (or segmented sphere) mesh + UVs to display equirect / per-quadrant warps, replacing **temporary portal quads** in `CubeBase` when that contract is ready *(see **SDK roadmap → v0.1.4 → Cube equirect / sphere display**)*.
- [ ] **Optional CUDA stereo path** — parity or faster dev on NVIDIA; **Vulkan** remains primary for **Radeon** Mini-ITX.
- [ ] **Run book** — `config.example.yaml`, loopback + LAN steps, known limitations (self-view, sync).

#### Milestone tag index (v0.0.2 → v0.1.0)
- [x] **v0.0.2** — eight **synthetic** feeds + atlas + **`dump-atlas`** + stub UDP + TCP loop *(no file feeds)*  
- [x] **v0.0.3** — **`pipeline-test-images/`** two flank PNGs → **L,R×4** into eight slots → **portrait or landscape** cells per config → Unity **pixel/layout** validation  
- [x] **v0.0.4** — **Undistort + stereo rectify** maps applied per pair  
- [ ] **v0.0.5** — **Stereo depth** (Vulkan + CPU fallback), OOB gating  
- [ ] **v0.0.6** — **MediaPipe** + **L/R selection** + **depth + landmark → `vec3`** on Linux  
- [ ] **v0.0.7** — **UDP `vec3`** channel map + **Unity** provider + **golden vectors**  
- [ ] **v0.1.0** — **Release polish**, version bump, tag when above are green  

</blockquote>

</details>

<details>
<summary><strong>v0.2.0+ (Future)</strong></summary>

<blockquote>

### 🎯 Deferred
- [ ] **AV1 / HEVC** transport (replace or augment CPU MJPEG for 4K/8K-class passthrough)
- [ ] **GPU equirect / Vulkan** compositor on AMD vision hardware — **Unity:** align **procedural sphere UVs + materials** with the shipped equirect layout *(same HoloCade_Unity task as v0.1.0 “paired” bullet; finalize when this lands).*
- [ ] **Production capture** — v4l2 multi-device, genlock / trigger, real calibration

</blockquote>

</details>

---

## License

Align with the HoloCade / Cube licensing chosen for the wider project (e.g. MIT to match `HoloCade_Unity` where applicable).
