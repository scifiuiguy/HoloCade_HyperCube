# Pipeline test images (local)

Drop **two** flank captures of the same subject here (filenames are configurable; suggested defaults):

- `face_left.png` — subject as seen from the **left** flank camera  
- `face_right.png` — subject as seen from the **right** flank camera  

The **v0.0.3** harness loads these as **BGR**, fits them to **1280×720** (or the active cell size), and assigns **eight logical cameras** by repeating the pair **four times**, e.g. **`L,R,L,R,L,R,L,R`**, so each notional quadrant gets the same stereo test pair for **Unity loopback** layout checks.

Raster files in this folder are **gitignored**; only this `README.md` is meant to be committed.

See the root **`README.md`** roadmap → **v0.0.3**.
