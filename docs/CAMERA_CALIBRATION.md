# Stereo camera calibration (Charuco / checkerboard)

This document describes how to capture data and run **stereo rectification** calibration for a **left/right camera pair** (e.g. GoPro bring-up or the production flank stereo rig). It aligns with HyperCube roadmap **v0.0.4** (undistort + stereo rectify).

---

## What we are solving for

- **Per camera:** intrinsics (focal length, principal point) + **distortion** coefficients.
- **Between cameras:** **relative pose** (rotation **R** and translation **T**) — the **stereo baseline** is the distance between the two **optical centers**, not a subject property.

Rectification uses these to produce **epipolar-aligned** left/right images so stereo matching and downstream geometry are well-behaved.

---

## Printed target (Charuco recommended)

- **Charuco** boards are often easier than a plain checkerboard: partial visibility still works, corners are well-defined.
- **Print at known scale:** measure the **printed** square / marker size (mm). Printer scaling errors flow directly into “metric” outputs.
- Use a board **large enough** to fill a useful fraction of the frame at your working distances, but not so large you can’t see enough markers at your nearest distance.

OpenCV: `cv2.aruco` + `cv2.aruco.CharucoBoard` (or a pre-generated PDF from a known dictionary and grid size — document dictionary ID, squares X×Y, square length, marker size in your calibration artifact).

---

## Syncing left and right captures (GoPro / non-genlocked cameras)

Consumer cameras rarely share **genlock**. Practical approaches:

1. **LED metronome on the beat**  
   Place a metronome with a **visible flash** on each beat so both cameras record the same transient. In post, align clips by matching flash frames, then extract **stereo pairs** at the same (or offset-corrected) frame indices.

2. **Audio**  
   If both cameras record the metronome **click** clearly, waveform alignment can refine sync after the LED gives you a coarse anchor.

3. **Clapper / slate**  
   A single sharp visual+audio event at the start (or periodically) is still useful for **drift checks** over long clips.

The metronome automates **repeated time landmarks** so you can grab many pairs without constant manual slating.

---

## Capture motion: distance vs rotation

### Distance (along the stereo baseline or “down the center line”)

Moving the target **farther/closer** while both cameras see the Charuco gives a good **range of disparities**. That helps depth scale and makes poor poses obvious in validation.

**Avoid** only using one distance.

### Rotation (board relative to cameras)

Calibration solvers need **geometric diversity**: different **views** of the same planar board. If the board stays **parallel** to both image planes at every shot, some parameters are **poorly constrained** and reprojection error can look “okay” while rectification quality is weak.

**Is 0°, 30° left, and 30° right (yaw only) enough?**

- **As a minimum habit:** it is **better than 0° only**, but it is usually **not enough** for a robust stereo cal by itself.
- Add at least:
  - **Pitch variation:** board tilted **up** and **down** (e.g. ±15°–30°) at several distances.
  - **More yaw samples:** e.g. ±15°, ±30°, ±45° where the board still fills enough of both views.
  - **Roll** occasionally (small twists) if your mounting allows — helps break degeneracies.

**Rule of thumb:** aim for **dozens of stereo pairs** (often **30–100+** for noisy consumer footage) with **many combinations** of (distance, yaw, pitch), not a small fixed set of three angles.

### Rolling shutter (GoPro and similar)

Prefer **pause–move–pause** (or **very slow** moves) at each beat so corners are **sharp** in both cameras. Continuous motion during exposure can introduce **skew** that hurts detection and calibration.

Use **bright light** and a **short exposure** when the camera allows it.

---

## Suggested capture ritual (tripod + LED metronome)

1. **Rigid stereo bar:** fix left/right cameras relative to each other for the session (any flex invalidates the cal).
2. **Disable** digital zoom / aggressive stabilization that crops or warps unpredictably; use a **fixed lens / FOV mode** when possible.
3. Mount **Charuco** on a tripod; place **LED metronome** so both cameras see flashes (and optionally hear clicks).
4. Start recording **both** cameras.
5. For each beat (or every other beat):
   - **Hold** the pose briefly (sharp frame).
   - Change **distance** and/or **orientation** before the next beat.
6. Cover the **shared field of view:** corners visible in **left and right** in every kept pair.
7. Export **synchronized still pairs** (same frame index after alignment, or nearest frame after flash detection).

---

## Validation after calibration

- **Reprojection / RMS error** from the solver (report in pixels; thresholds depend on resolution and target size).
- **Epipolar sanity:** after rectification, corresponding features should sit on **approximately the same scanline** (horizontal alignment in the rectified image pair).
- **Holdout:** leave some image pairs **out** of the fit and check error on them.

---

## Artifacts to store (for HyperCube v0.0.4+)

Per **physical stereo pair** / SKU, version together:

- Camera matrices **K_left**, **K_right**
- Distortion coeffs **D_left**, **D_right**
- Stereo **R**, **T** (or rectification **R1**, **R2**, **P1**, **P2**, **Q** and remap maps)
- **Image size** used during calibration
- **Target definition** (Charuco dictionary, grid, printed sizes)
- **Capture notes** (camera model, lens mode, resolution, FPS, sync method)

Load path in HyperCube is planned under `calibration/` (see **README → v0.0.4**).

---

## Factory / QC: jig-mounted target array (automated path)

For **final assembly QC**, the goal is to replace ad-hoc tripod captures with a **repeatable mechanical fixture** and a **diagnostic software path** tuned to that fixture’s geometry.

### Concept

1. **Docking jig** mounts to the **cabinet chassis** (or to a reference interface that mates the vision subassembly the same way every time). The jig defines a **known relationship** (within mechanical tolerance) between:
   - the **stereo pair** on that face, and  
   - a **set of Charuco panels** at **fixed positions and orientations** in the jig frame.

2. **Multiple Charucos at various angles**, **evenly lit** (diffuse illumination, avoid hot spots that wash out markers). The array is designed so **both** left and right cameras see **enough corners** in each capture without an operator walking a board through space.

3. **Calibration / verification software** is written **for this specific array**:  
   - Each board’s **pose in jig coordinates** is part of the product definition (CAD + measured sign-off).  
   - The solver uses **detected corners** plus **known 3D object points** → faster convergence and tighter residuals than “free” hand-held capture.  
   - Output is still the same artifact bundle (**K**, **D**, **R|T**, rectification maps); QC records **PASS/FAIL** against thresholds.

With a good station, the expectation is **lock-in or verify calibration in seconds** of compute after a **single triggered multi-frame capture** (not minutes of manual posing).

### Example layout: center + four satellites (“star”) — five Charuco boards

One workable QC pattern is **five planar Charuco boards** in a single rigid frame:

| Role | Placement | Intent |
|------|------------|--------|
| **Center** | On-axis (roughly along the stereo pair’s central viewing direction) | Strong correspondences near the “boresight” of both cameras. |
| **Top / bottom / left / right** | Offset from center, each panel **tilted toward the center** (e.g. **~30°** as a first cut—confirm with **cabinet CAD**, stereo baseline, and ray visibility for both cameras) | In one static arrangement, you get **pitch and yaw diversity** similar to aiming multiple hand-held board angles—without an operator moving the target. |

Together, **center + periphery** also span a modest **range of depths** (near vs slightly farther surfaces), which helps disparity conditioning versus a single flat plane at one distance.

**Scaling up:** some stations add a **sixth** board (e.g. extra corner or farther depth step); the same rules apply—fixed pose in jig coordinates, visibility in **both** cameras, unique identification.

**Engineering checks (before freezing the design):**

- **Stereo overlap:** every panel that enters the solve must have **enough Charuco corners visible in both left and right** at your dock distance and chosen resolution. Use **CAD ray checks** or a prototype photo pair to confirm—wide FOV cameras help; narrow FOV may require larger boards or a closer jig.
- **Tilt angle (e.g. ~30°)** is a **starting point** until validated in CAD / prototype: tune so detection is reliable and **no board is edge-on** to either camera; update this doc when you freeze the jig drawing.
- **Lighting:** tilted panels pick up **specular highlights** differently; prefer **diffuse, even illumination** (soft boxes / integrating sphere–style) over a single forward spotlight.
- **Software:** the calibration artifact must list **each board’s rigid pose in jig coordinates** (or one jig frame with known transforms); detection identifies **which board is which** (dictionary IDs / layout avoids ambiguity).

This layout is **documentation of intent** until mechanical and optical validation say otherwise.

### Four sides of the cube

The cube has **four flank stereo pairs** (N / S / E / W). Each pair has its **own optics, baseline, and mounting tolerances**. For **best results**, run the **QC jig workflow once per side**—i.e. **four runs per fully assembled unit** (or four runs per vision subassembly if you calibrate before final cabinet close-out, depending on your process).

- **Why not one cal for all four?** Intrinsics can sometimes be shared *within a lens batch* if you trust manufacturing, but **extrinsics (stereo geometry relative to the chassis)** are **per pair** unless the mechanical design guarantees interchangeable subassemblies with metrology to prove it.

**Time budget:** if each side’s automated capture + solve + report is on the order of **tens of seconds**, **under one minute per side** is a reasonable QC target; **under ~4 minutes** for all four faces is achievable with scripting, assuming mechanical docking is smooth.

### R&D vs QC

| Phase | Approach |
|--------|-----------|
| **R&D / GoPro** | Hand-held or tripod Charuco, LED/metronome sync, many diverse poses (see sections above). |
| **QC / production** | Jig with **known multi-board geometry**, controlled lighting, **one-button** capture + **pass/fail** against golden tolerances; full re-solve only when engineering changes SKU or station. |

### Optional split: “calibration” vs “verification”

- **Full calibration** when: new camera module, lens lot, mechanical revision, or first article.  
- **Per-unit verification** when: mechanics are stable → load **nominal** or **per-line** priors, use the jig capture to confirm **residuals stay in band**; fail the unit if a camera is swapped, loose, or mis-focused.

---

## References

- HyperCube roadmap: repo root **`README.md`** → **v0.0.4 (Undistort + stereo rectification)**.
- Implementation plan: **`docs/VERSION_0_1_0_PLAN.md`**.
