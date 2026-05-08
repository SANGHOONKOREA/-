---
name: sketch-to-sld
description: Convert electrical Single Line Diagram images (hand-drawn sketches, photographs, scans, or screenshots) into a structured sld_spec.json and IEC 60617 / AutoCAD 2018 (R32) DWG using the image-to-dwg/ pipeline. Use when the user provides an electrical schematic image and asks for a CAD deliverable - including phrases like "convert this SLD", "image to DWG", "단선도 DWG", "손그림 회로도 변환", "전기 단선도 CAD".
---

# sketch-to-sld

Turns an electrical Single Line Diagram **image** into a CAD-ready DWG via
the existing `image-to-dwg/` pipeline.

## How accuracy is achieved

A single vision pass on a busy schematic is fragile: tiny digits in
peripheral labels are routinely misread, and a 1500-pixel-tall image gives
the model only ~50 pixels of vertical detail per label.  This skill
deliberately fights that with five layers of redundancy:

1. **Image enhancement + ROI cropping** before reading.  Each label is read
   from a 3x upscaled, contrast-boosted crop, not from the cluttered full
   image.
2. **Multi-pass extraction**.  Topology first (counts and connectivity),
   then per-label numbers, never both at once.
3. **Self-consistency**.  Critical numeric fields are read twice with
   different framings; disagreements are flagged.
4. **Cross-method verification**.  OpenCV symbol counts and Tesseract OCR
   on printed labels run alongside the vision pass and **disagreements
   block the build**.
5. **Render-and-compare iteration**.  After the first build, the source
   image and the generated preview are placed side-by-side and the vision
   model is asked to find differences.  The loop runs up to three times.

Each layer is independent.  A digit must survive every layer to land in
the final spec without a flag.

## When to invoke

Trigger this skill when **all** of the following are true:

1. The user supplies (or points at) an image file: `.png`, `.jpg`,
   `.jpeg`, `.webp`, or single-page `.pdf`.
2. The image is an electrical schematic — typically a Single Line Diagram
   with generators, busbars, breakers, transformers, motors, drives,
   thrusters, etc.
3. The user wants a CAD output (DWG / DXF / SVG), not a description.

If the image is unrelated (mechanical P&ID, network topology, equipment
photo) — **do NOT run this skill**; tell the user it's out of scope.

## Tools provided alongside SKILL.md

| Script               | Purpose                                                 |
|----------------------|---------------------------------------------------------|
| `preprocess.py`      | Sharpen / autocontrast / **crop a ROI at 3x scale**     |
| `cv_count.py`        | OpenCV count of circles, rectangles, long lines         |
| `ocr_check.py`       | Tesseract OCR on a region, with character whitelist     |
| `render_diff.py`     | Side-by-side + 50% overlay panel of source vs preview   |
| `validate.py`        | Schema + geometry + reference + **domain plausibility** |
| `schema.example.json`| Reference structure for `sld_spec.json`                 |

All scripts live in `.claude/skills/sketch-to-sld/`.  They are independent
CLIs; you call them with `Bash`.  None require API keys.

## Procedure (must follow in order)

### Step 1 — Confirm input

Ask the user (use `AskUserQuestion` if appropriate):

- The image file path.
- Whether the source is **hand-drawn**, **photograph of a printed
  drawing**, **scan**, or **digital screenshot/PDF**.  Different sources
  use different techniques in Step 4.
- Project / vessel name and tag prefix (default to `image-to-dwg/sld_spec.json`'s).

### Step 2 — Image enhancement

Always run enhancement before any vision pass:

```bash
python .claude/skills/sketch-to-sld/preprocess.py \
    <input> --enhance image-to-dwg/output/enhanced.png
```

Use the enhanced version for all subsequent reads.  Keep the original on
disk so `render_diff.py` can compare against it later.

### Step 3 — Topology pass (no numbers)

`Read` the enhanced image.  Describe in plain English **only the
topology**:

- Generator count and approximate left-to-right positions (no kVA / V yet).
- Main busbar(s); is there a bus tie? where?
- Feeder count and what each feeder appears to drive (azimuth thruster /
  tunnel thruster / pump / winch / generic motor / unknown).
- Presence of breakers (drawout?), disconnectors, transformers (number of
  windings — 2 or 3?), VFDs.
- Encircled remark numbers (just the digits, locations).

**Do not write the JSON yet.**  Ask the user to confirm topology.  If they
say "you missed feeder 4" or "there is no bus tie", correct your reading
and try again before proceeding.

### Step 4 — Cross-method symbol count (sanity)

```bash
python .claude/skills/sketch-to-sld/cv_count.py \
    image-to-dwg/output/enhanced.png
```

Compare CV counts to your topology pass:

- `circles` ≈ generators + motors + 3 × number of 3-winding TXs.
- `rectangles` ≈ VFD enclosures + breaker drawout frames + title block.

If your topology says 4 generators + 3 motors + 3 TXs (× 3 windings) =
`16` circles but CV finds only `9`, **stop and re-examine the image**.
Mismatch usually means you missed a feeder or the image has poor contrast.

For hand-drawn input, CV counts can be unreliable — treat them as a
weak signal, not a hard veto.

### Step 5 — Per-label ROI extraction

For **each** entity that has numeric labels (every generator, every
transformer, every motor, the busbar label), do:

1. Estimate the pixel ROI of that label.  If unsure, generate a grid:

   ```bash
   python .claude/skills/sketch-to-sld/preprocess.py \
       <input> --grid output/grid.png --grid-step 100
   ```
   `Read` `output/grid.png` to get pixel-coordinate references.

2. Crop and upscale that ROI:

   ```bash
   python .claude/skills/sketch-to-sld/preprocess.py \
       <input> --crop X,Y,W,H --out output/label_<name>.png \
       --scale 3
   ```

3. `Read` the crop and extract digits.

4. For printed sources (not hand-drawn), also run OCR:

   ```bash
   python .claude/skills/sketch-to-sld/ocr_check.py \
       output/label_<name>.png --psm 7 --whitelist 0123456789kVAVHzKWRPMxX/.,
   ```

   If the vision read and the OCR read **agree** → high confidence.
   If they **disagree** → store the value as `"???"` and put both
   readings in your follow-up question to the user.

5. For ambiguous digits in **hand-drawn** inputs, do a **self-consistency
   pass**: re-read the same crop with a different question framing
   ("read just the kVA number on the primary winding") and compare.
   Disagreements become `"???"`.

### Step 6 — Draft sld_spec.json

Assemble everything from Steps 3–5 into a draft following
`.claude/skills/sketch-to-sld/schema.example.json`.

Rules:

- Keep `level_y` exactly as in the example unless the source has a
  visibly different layer stack.
- For each feeder, X is the **relative position** in the source mapped
  into `[main_busbar.x_start, main_busbar.x_end]` (default `[50, 400]`).
- For each generator, X is similarly mapped.
- Any value you could not read with high confidence → literal string
  `"???"` or `null`.  **Never guess a digit.**
- Preserve encircled remark numbers; put text in
  `annotations.remark_table`.

### Step 7 — Domain validation (mandatory gate)

```bash
python .claude/skills/sketch-to-sld/validate.py \
    image-to-dwg/sld_spec.json
```

The validator runs four passes:

- **STRUCT** — required keys present.
- **GEO** — coordinates inside the busbar range.
- **REF** — remark-number references resolve.
- **DOMAIN** — voltages in known IEC classes; motor V matches a TX
  secondary; motor kW within 40–95% of TX secondary capacity; RPM in
  100–5000; primary kVA ≥ 80% of secondary sum.

A **DOMAIN** failure usually means a digit was misread (e.g., motor
voltage `680` should have been `690`, primary kVA `200` should have been
`2000`).  Do **not** override domain rules silently — show the failures
to the user, ask which value to correct, fix the spec, and re-validate.

The build cannot proceed while the validator returns non-zero.

### Step 8 — Human review (mandatory)

Even after validation passes, present the user with:

1. The full `sld_spec.json` (collapsed table view).
2. The list of fields that came from low-confidence readings (anywhere a
   self-consistency or vision↔OCR disagreement occurred).
3. The list of assumptions: defaults applied for missing tags, mapped
   thruster type when uncertain, etc.

Ask explicitly: **"Should I commit this spec and build the DWG?"**

Do not run the builder until the user says yes.

### Step 9 — Build

```bash
cd image-to-dwg && python -m src.main
```

This produces `output/SHI_18K_BV_SLD.dxf` (R2018), `preview.png`, and
`preview.svg`.

### Step 10 — Render diff and iterate

```bash
python .claude/skills/sketch-to-sld/render_diff.py \
    --original <user-supplied original> \
    --preview image-to-dwg/output/preview.png \
    --out image-to-dwg/output/diff.png
```

`Read` `output/diff.png`.  It contains three panels: SOURCE, BUILT, and
50% OVERLAY.  Compare and report:

- Element counts (generators, feeders, breakers, ...).
- Topology (correct bus tie position, correct azimuth-vs-tunnel mapping).
- Numeric labels (kVA, kW, V, RPM all present and correct).
- Layout (each feeder under the right generator, no missing remarks).

If you find any discrepancy:

- **Topology / count error** → fix the spec, re-run `validate.py`,
  re-build, re-diff.  Up to 3 iterations.
- **Numeric error** → fix the spec, re-validate, re-build, re-diff.
- **Stylistic difference only** (line spacing, font, layer colour) →
  ignore.  These are template choices, not errors.

If after 3 iterations the diff still shows substantive differences, stop
and hand the spec to the user with a clear list of remaining issues.

### Step 11 — Hand off

Tell the user:

- The DXF path and how to convert to DWG (ODA File Converter or AutoCAD
  `SAVEAS`).
- The viewer at `image-to-dwg/index.html` for pan/zoom + downloads.
- The list of fields that still carry uncertainty flags and need a CAD
  engineer's sign-off.
- The diff image path so they can do their own visual check.

## Symbol mapping reference

Use only these blocks (defined in `image-to-dwg/src/blocks.py`):

| Source drawing element                  | Block name           |
|-----------------------------------------|----------------------|
| Circle with G                           | `IEC_GEN`            |
| Circle with M                           | `IEC_MOTOR`          |
| Drawout breaker (square in dashed box)  | `IEC_ACB_DRAWOUT`    |
| Disconnector (open switch with dots)    | `IEC_DISC`           |
| Bus tie (gap with switch on busbar)     | `IEC_BUSTIE`         |
| 3 overlapping circles (transformer)     | `IEC_TX_3WND`        |
| Box with `~` and `=` (rectifier+inv.)   | `IEC_VFD`            |
| Two ovals + rotation arrow              | `IEC_AZIMUTH_THR`    |
| Two ovals in horizontal tunnel          | `IEC_TUNNEL_THR`     |

If the source uses a symbol not in this table, **stop** and ask the user
how to handle it.

## Hand-drawing pitfalls

- **Digit confusion**: `1 / 7`, `0 / O / Q / D`, `4 / 9`, `3 / 8`, `5 / 6`.
  Self-consistency + OCR catches most of these.  Decimals vs commas in
  Asian/European writing.
- **Voltage class snap**: if you read `680` and `690` is the standard
  class, the validator will catch it.  Trust the validator.
- **Symbol direction**: rectifier and inverter share the same outer box;
  only diagonal direction and `~/=` placement differ.  Read at 3x crop.
- **Connection routing**: hand-drawn cables often have meaningless kinks.
  Always reduce to straight vertical / horizontal.
- **Missing tags**: assign sequential (`DG1`, `TX-01`, ...).  Flag this.
- **Scale ambiguity**: the level_y stack determines the layout — do not
  try to preserve absolute pixel coordinates from the image.

## Out of scope

- Mechanical P&ID drawings.
- Schematics with more than ~6 feeders (current pipeline assumes
  single-row feeder layout; ask the user before extending).
- Multi-page drawings (one image per skill invocation).

## Honest limitations to communicate up-front

State this in your first reply:

> "I read the image with vision, cross-check digits against OCR (for
> printed sources), sanity-check counts against OpenCV blob detection,
> validate every value against electrical-engineering domain rules, then
> render the result and compare to the source up to three times.  This
> typically gets clean printed sources to ~95%+ first-pass accuracy and
> hand-drawn sketches to ~80–90%.  **A CAD engineer must still sign off
> before delivery** — fundamental ambiguity in the source cannot be
> resolved by any number of cross-checks."
