# SHI 18K BV — Electric Single Line Diagram (image → DWG)

Programmatic conversion of the *SHI 18K Bunkering Vessel - Electric Single
Line Diagram* PowerPoint screenshot into an enterprise-grade AutoCAD 2018
(R32) DWG.

The conversion follows the IEC 60617 symbol standard and produces a real CAD
deliverable (proper layers, text styles, blocks with attributes, A3 title
block) — not a raster trace.

## Layout

```
image-to-dwg/
├── README.md              ← this file
├── requirements.txt
├── sld_spec.json          ← single source of truth (Step 1: image read-out)
├── src/
│   ├── template.py        ← Step 2: layers / styles / title block
│   ├── blocks.py          ← Step 3: IEC 60617 symbol library
│   ├── builder.py         ← Step 4: assembles entities from sld_spec.json
│   └── main.py            ← CLI entry point
└── output/
    ├── SHI_18K_BV_SLD.dxf ← generated drawing (R2018 DXF)
    └── preview.png        ← matplotlib render for visual QA
```

## Build

```bash
pip install -r requirements.txt
python -m src.main \
  --spec sld_spec.json \
  --out  output/SHI_18K_BV_SLD.dxf
```

Output: a R2018 DXF.  Convert to DWG using either of:

### Option A — ODA File Converter (free)

1. Install <https://www.opendesign.org/guestfiles/oda_file_converter>
2. Run with: input format **DXF**, output format **DWG**, version **ACAD2018**.

### Option B — AutoCAD

Open the DXF and `SAVEAS` → DWG (AutoCAD 2018 Drawing).

## Drawing structure

| Layer            | Color | Usage                          |
|------------------|-------|--------------------------------|
| `0-FRAME`        | 7     | Sheet border, title block      |
| `1-BUSBAR_440V`  | 1     | Main 440 V busbar              |
| `2-CABLE_440V`   | 2     | 440 V feeder cables            |
| `2-CABLE_690V`   | 3     | 690 V VFD output cables        |
| `3-SYMBOL`       | 7     | All IEC 60617 symbol geometry  |
| `4-TEXT`         | 7     | Tags, ratings, headings        |
| `5-DIM`          | 8     | Dimension lines                |
| `6-ANNO`         | 5     | Encircled remark numbers       |
| `7-HIDDEN`       | 8     | Drawout breaker frame (dashed) |

## IEC 60617 symbol library

All blocks insert at (0, 0) on the symbol's geometric centre.

| Block name           | IEC ref     | Used for                        |
|----------------------|-------------|---------------------------------|
| `IEC_GEN`            | S00210      | Generator (G)                   |
| `IEC_MOTOR`          | S00210      | Motor (M)                       |
| `IEC_ACB_DRAWOUT`    | S00286+drawout | Air circuit breaker, withdrawable |
| `IEC_DISC`           | S00284      | Disconnector / isolator          |
| `IEC_BUSTIE`         | —           | Bus tie breaker (horizontal)     |
| `IEC_TX_3WND`        | S00604      | 3-winding transformer            |
| `IEC_RECTIFIER`      | S00866      | AC → DC rectifier                |
| `IEC_INVERTER`       | S00867      | DC → AC inverter                 |
| `IEC_VFD`            | combined    | Variable frequency drive (rect+inv) |
| `IEC_AZIMUTH_THR`    | —           | Azimuth thruster                 |
| `IEC_TUNNEL_THR`     | —           | Tunnel thruster                  |

## What was captured from the source image

The `sld_spec.json` file encodes the entire drawing as structured data:

- **4 diesel generators** on a single AC 440 V / 3PH / 60 Hz busbar with bus tie.
- **3 feeders** below the busbar:
  - F1: TX 2000/1000/1000 kVA (440/690/690 V) → VFD → 1500 kW Azimuth Thruster
  - F2: TX 2000/1000/1000 kVA (440/690/690 V) → VFD → 1500 kW Azimuth Thruster
  - F3: TX 1200/600/600  kVA (440/690/690 V) → VFD → 800 kW Tunnel Thruster
- All ACBs are drawout type; each feeder has a downstream disconnector.
- 4 remark numbers (①②③④) cross-reference the table at lower-left.

## Verification checklist

Before delivery, verify against the source image:

- [ ] Generator count = 4
- [ ] Bus tie present (1)
- [ ] Feeder count = 3 (2 azimuth, 1 tunnel)
- [ ] Transformer ratings: 2000/1000/1000 × 2 and 1200/600/600 × 1
- [ ] Motor ratings: 1500 kW × 2 and 800 kW × 1
- [ ] Voltages: 440 V primary, 690 V secondary
- [ ] All ACBs drawn as drawout (dashed frame)
- [ ] Title block fields populated
- [ ] DWG opens cleanly in AutoCAD with no AUDIT errors

## Editing the drawing

To add or move a component, edit `sld_spec.json` (positions, ratings, tags),
then re-run the build.  The Y-coordinate of every horizontal stratum
(busbar, ACB, transformer, VFD, motor, thruster) is centralised in
`sld_spec.json::level_y` so the whole diagram can be re-balanced by
adjusting one field.
