# Pipeline test images (local)

Drop **two** flank captures of the same subject here (filenames are configurable; suggested defaults):

- `face_left.png` — subject as seen from the **left** flank camera  
- `face_right.png` — subject as seen from the **right** flank camera  

The **v0.0.3** harness loads these as **BGR** at **native orientation** (see root **`README.md`** → **v0.0.3** → **Cell geometry**): **portrait** (e.g. `720×1280`) and **landscape** (e.g. `1280×720`) are both supported via **config** — images are **not** reformatted into landscape when portrait mode is selected. Optional scaling only when the file resolution does not match the configured cell (same aspect / center-crop policy TBD in code).

Eight logical cameras: repeat the stereo pair **four times**, e.g. **`L,R,L,R,L,R,L,R`**, so each notional quadrant gets the same stereo test pair for **Unity loopback** layout checks.

Raster files in this folder are **gitignored**; only this `README.md` is meant to be committed.

See the root **`README.md`** roadmap → **v0.0.3**.
