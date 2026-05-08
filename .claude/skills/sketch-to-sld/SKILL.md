---
name: sketch-to-sld
description: Convert electrical Single Line Diagram images (hand-drawn sketches, photographs, scans, or screenshots) into a structured sld_spec.json and an IEC 60617 / AutoCAD 2018 (R32) DWG using the image-to-dwg/ pipeline. Use when the user provides an electrical schematic image and asks for a CAD deliverable - including phrases like "convert this SLD", "image to DWG", "단선도 DWG", "손그림 회로도 변환", "전기 단선도 CAD".
---

# sketch-to-sld

Turns an electrical Single Line Diagram **image** into a CAD-ready DWG via
the existing `image-to-dwg/` pipeline.  Claude's vision reads the image and
drafts the structured spec; the pipeline then produces the DWG / DXF / PNG /
SVG.  **Human review of the draft spec is mandatory** before final DWG
delivery — handwriting, blurry photos, and ambiguous symbols routinely
produce wrong digits or misplaced connections.

## When to invoke

Trigger this skill when **all** of the following are true:

1. The user supplies (or points at) an image file: `.png`, `.jpg`, `.jpeg`,
   `.webp`, or `.pdf` (single page).
2. The image content is an electrical schematic — typically a Single Line
   Diagram with generators, busbars, breakers, transformers, motors,
   thrusters, drives, etc.
3. The user wants a CAD output (DWG / DXF) — not just a description.

If the image is unrelated (e.g., a photograph of equipment, a P&ID
mechanical drawing, a network topology) — **do NOT run this skill**.
Tell the user it's out of scope and recommend manual transcription.

## Procedure

Follow these steps in order.  Do not skip ahead.

### 1. Confirm input

Ask the user (using `AskUserQuestion` if appropriate) for:

- The image file path.
- Whether the source is a **hand-drawn sketch**, a **photograph of a printed
  drawing**, or a **digital screenshot/PDF**.
- Vessel / project name and any tag prefix to use (e.g. "DG", "TX", "MTR").

If unspecified, default to the conventions used in
`image-to-dwg/sld_spec.json`.

### 2. Read the image with Claude's vision

Use the `Read` tool on the image path.  Claude is multimodal and will
receive the image content directly.  Spend the first turn just *describing
what you see* in plain English so the user can sanity-check your reading
before any JSON is written.  Specifically enumerate:

- Number of generators and their tags.
- Main busbar voltage, phases, frequency, and bus ties.
- Each feeder: breaker types, transformer ratings, drive type, motor
  ratings, load type (azimuth / tunnel thruster / pump / winch / generic).
- Any annotations or remark numbers.
- **List anything you cannot read clearly.**  Be explicit: "I cannot read
  the kVA on the third transformer — the ink is smudged."

### 3. Draft `sld_spec.json`

Produce a draft spec following the schema in
`image-to-dwg/sld_spec.json` (use that file as the schema template).  Key
rules:

- All coordinates are in **mm on an A3 landscape sheet (420 × 297)**.
- Use the `level_y` strata from the existing template — do **not** invent
  new Y-coordinates unless the diagram demands a new layer.
- For each feeder, the X-coordinate should reflect the relative left-to-right
  position seen in the source image, scaled into the busbar's
  `[x_start, x_end]` range (default `[50, 400]`).
- For ratings you could not read with confidence, use the literal string
  `"???"` or set the value to `null` — never guess.  Flag these in your
  reply so the engineer fills them in.
- Preserve **encircled remark numbers** (①②③④...) from the source and put
  them in `annotations.remark_table`.

Save the draft to `image-to-dwg/sld_spec.json` (replace) **only after** the
user approves it.  Show the JSON inline first.

### 4. Mandatory human review

Before running the builder, present the user with:

1. The drafted `sld_spec.json` (collapsed if long; show the structure).
2. A short list of **uncertainties** and **assumptions** you made:
   - Numbers you guessed.
   - Topology decisions where the image was ambiguous.
   - Symbols you mapped to the closest available IEC 60617 block.
3. Ask explicitly: "Should I commit this spec and build the DWG?"

Do **not** run the build until the user says yes.  This step is what makes
the output enterprise-grade — Claude's vision will never be infallible on
hand-drawn input.

### 5. Build and render

After approval, write the JSON to `image-to-dwg/sld_spec.json` and validate
it before building:

```bash
python .claude/skills/sketch-to-sld/validate.py image-to-dwg/sld_spec.json
```

This catches missing keys, `"???"` placeholders the engineer didn't fill
in, X-coordinates outside the busbar range, and remark-number references
that don't resolve.  Fix all reported problems before continuing.

Then run the builder:

```bash
cd image-to-dwg && python -m src.main
```

This produces:

- `image-to-dwg/output/SHI_18K_BV_SLD.dxf` — R2018 DXF.
- `image-to-dwg/output/preview.png` — raster preview.
- `image-to-dwg/output/preview.svg` — vector preview.

If the user supplied a different drawing number, rename the DXF
accordingly via `--out-dxf`.

### 6. Visual diff and report

Read the new `output/preview.png` and compare against the source image:

- Same number of generators? Same bus tie count?
- Same number and type of feeders?
- All transformer ratings match?
- All motor ratings match?
- All thruster types correct (azimuth vs tunnel)?

Report any mismatches.  If the topology differs, **iterate** — do not
silently move on.

### 7. Hand off

Tell the user:

- Where the DXF lives.
- How to convert to DWG (ODA File Converter or AutoCAD `SAVEAS`).
- That the viewer at `image-to-dwg/index.html` shows the result with
  pan/zoom and direct download links.
- Remaining uncertainties that still need a CAD engineer's review before
  enterprise delivery.

## Symbol mapping reference

Use these IEC 60617 blocks (already defined in
`image-to-dwg/src/blocks.py`):

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
how to handle it (add a new block, substitute closest match, or skip).
Do not silently approximate.

## Pitfalls specific to hand drawings

- **Digit confusion**: `1 / 7`, `0 / O / Q`, `4 / 9`, decimal vs comma.
  When in doubt, mark as `"???"` and ask.
- **Symbol direction**: a rectifier and inverter share the same outer box;
  only the diagonal direction and `~` vs `=` placement differ.  If
  unreadable, note that the VFD might have wrong rectifier/inverter
  ordering.
- **Connection routing**: hand-drawn cables often have kinks that aren't
  meaningful.  Always reduce to straight vertical / horizontal segments in
  the spec.
- **Missing tags**: assign sequential tags (`DG1`, `DG2`, `TX-01`, ...) and
  flag this clearly in the review report.
- **Scale ambiguity**: a tiny sketch and a giant sketch produce the same
  DWG once normalised.  Don't try to preserve absolute scale from the
  image — the level_y strata determine the layout.

## Out of scope

- Mechanical P&ID drawings (different symbol set).
- Schematics with more than ~6 feeders (current pipeline assumes
  single-row feeder layout; ask the user before extending).
- Multi-page drawings (one image per skill invocation).
- Real-time CV with shape detection (this skill is LLM-vision based, not
  classical CV).

## Honest limitations to communicate to the user

State these up-front in your reply:

> "Claude's vision reads the image and drafts a JSON spec. For hand-drawn
> sketches, expect 60–85% accuracy on the first pass — clean, ruler-drawn
> sketches do better than freehand ones. **You must review the draft spec
> before I build the DWG.** Treat the output as a starting point that a CAD
> engineer signs off, not as a finished enterprise drawing."
