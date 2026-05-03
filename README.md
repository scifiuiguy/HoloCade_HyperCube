# HoloCade HyperCube (Linux vision service)

Companion repository for **HoloCade Cube** deployments that split **camera capture + MediaPipe + passthrough compositing** onto a **Linux Mini-ITX**, while **Unity on Windows** runs the game and display rig.

Canonical hardware and topology narrative: **`../CubeModule_README.md`** (dual PC, Ethernet, per-display flank stereo cameras).

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
| **Compositing** (N×camera → equirect or tiled atlas) | Prefer **GPU** once CPU proves too slow. Practical order: **OpenCV with CUDA** (remap/warp, stitching prototypes) → **PyTorch** (differentiable warps, rapid iteration) → **custom CUDA** / **Vulkan compute** if you need minimum latency and full control. |
| **Video encode to Windows** | Depends on wire format: **NDI**, **SRT**, **custom UDP + NVENC** (if Linux box has NVIDIA), or **raw / lightly compressed tiles** on a 10 GbE link. Document bandwidth and latency budgets alongside the protocol. |
| **Pose / metadata** | Small JSON or protobuf over **TCP/WebSocket** or a side channel multiplexed with video; include **monotonic timestamps** for Unity to align with frames. |

**CUDA vs “something else”:** CUDA is excellent when you already target **NVIDIA on Linux** and want hand-written kernels or **OpenCV CUDA** / **TensorRT**-adjacent pipelines. If you need **vendor-neutral GPU**, consider **Vulkan compute** or **OpenCL** (declining ecosystem) for compositing only, while MediaPipe stays on its supported backends. For a first milestone, **Python + MediaPipe + OpenCV (CUDA optional)** keeps iteration speed high; profile before rewriting in raw CUDA.

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
