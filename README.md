# HoloCade HyperCube (Linux vision service)

Companion repository for **HoloCade Cube** deployments that split **camera capture + MediaPipe + passthrough compositing** onto a **Linux Mini-ITX**, while **Unity on Windows** runs the game and display rig.

Canonical hardware and topology narrative: **`../CubeModule_README.md`** (dual PC, Ethernet, per-display flank stereo cameras).

**Roadmap:** **`docs/VERSION_0_1_0_PLAN.md`** — v0.0.1 → v0.1.0 (eight test feeds → four quadrant streams → Unity + UDP pose).

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
| `uv run pytest` | Run tests once you add them. |

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

## License

Align with the HoloCade / Cube licensing chosen for the wider project (e.g. MIT to match `HoloCade_Unity` where applicable).
