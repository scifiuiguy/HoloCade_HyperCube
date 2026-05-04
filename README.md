# HoloCade HyperCube (Linux vision service)

Companion repository for **HoloCade Cube** deployments that split **camera capture + MediaPipe + passthrough compositing** onto a **Linux Mini-ITX**, while **Unity on Windows** runs the game and display rig.

Canonical hardware and topology narrative: **`../CubeModule_README.md`** (dual PC, Ethernet, per-display flank stereo cameras).

---

## Unity loopback (dev)

1. In a scene with **`CubeRigController`**, add **`HyperCubeQuadrantTcpHost`** (default ports **18001–18004**), **`HyperCubeUdpPoseReceiver`** (default **18100**), **`HyperCubePassthroughBinder`** (wire `cubeRig` + `quadrantHost`), and optionally **`HyperCubePoseTrackingProvider`** on the same object as `CubeRigController`’s **`faceTrackingProvider`** (assign `udpReceiver`, **`cubeRoot`** = rig transform).  
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
| `uv run hypercube-serve dump-atlas -o out/atlas.png` | Write a synthetic **5120×2880** atlas PNG (sanity check). |
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
  README.md           # this file
  docs/               # protocol drafts, calibration notes (as they land)
  src/                # Python package or scripts (placeholder)
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
<summary><strong>v0.1.0 (In-Progress)</strong></summary>

<blockquote>

### 🎯 Planned (v0.1.0)

#### Vision pipeline (Python)
- [ ] **Eight test camera feeds** — MJPEG files, synthetic tiles, and/or duplicated USB streams mapped to eight logical IDs
- [ ] **Rectilinear atlas** — pack to **5120×2880** (default **4×2** @ 1280×720; configurable)
- [ ] **Four “360 quadrant” outputs** — crop / partition atlas for Cube-facing delivery (v0.1 uses **stand-in** ROIs; full equirect unwrap later)
- [ ] **Optional MediaPipe** — Face Landmarker on atlas or tiles; **per-pair L/R** selection stub; **station → face** assignment by atlas region
- [ ] **TCP MJPEG (×4)** — e.g. ports **18001–18004** (or HTTP `/q0`…`/q3`) for Unity ingest (**not** HoloCade UDP — payload too large)

#### Pose & HoloCade UDP
- [ ] **`HoloCadeUDPTransport`-compatible emitter** in Python — mirror `[0xAA][type][channel][payload][xor_crc8]` from `HoloCade_Unity` / `HoloCadeUDPTransport.cs`
- [ ] **Channel map** — reserved band (e.g. **100–119**) for per-side **floats** `(u,v)`, confidence, **`uint32` seq** (fits existing per-scalar packets)
- [ ] **Unity `CubeFaceTrackingProviderBase` shim** — reads UDP float cache → approximate **eye / face** world pose for `CubeRigController`

#### Unity integration
- [ ] **Four-stream decoder** — JPEG → `Texture2D` / `RenderTexture` → bind **`CubePassthroughSources`** at runtime
- [ ] **Run book** — `config.example.yaml`, loopback + LAN smoke steps, tag **`v0.1.0`** when checklist is green

#### Milestone tags (same plan)
- [ ] **v0.0.2** — eight feeds + atlas + offline PNG dump
- [ ] **v0.0.3** — one TCP MJPEG quadrant smoke
- [ ] **v0.0.4** — four MJPEG servers + **UDP golden-vector** tests vs C#
- [ ] **v0.0.5** — Unity: one quadrant → one portal
- [ ] **v0.0.6** — Unity: four quadrants + side mapping doc
- [ ] **v0.0.7** — MediaPipe + assignment + UDP driving tracking
- [ ] **v0.1.0** — release polish + version bump in `pyproject.toml`

</blockquote>

</details>

<details>
<summary><strong>v0.2.0+ (Future)</strong></summary>

<blockquote>

### 🎯 Deferred
- [ ] **AV1 / HEVC** transport (replace or augment CPU MJPEG for 4K/8K-class passthrough)
- [ ] **GPU equirect / Vulkan** compositor on AMD vision hardware
- [ ] **Production capture** — v4l2 multi-device, genlock / trigger, real calibration

</blockquote>

</details>

---

## License

Align with the HoloCade / Cube licensing chosen for the wider project (e.g. MIT to match `HoloCade_Unity` where applicable).
