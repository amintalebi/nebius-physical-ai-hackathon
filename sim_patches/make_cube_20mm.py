#!/usr/bin/env python3
"""Generate the 20 mm cube twins the starter does not ship (it has 25/30/40 mm only).

The event cubes are blue in 20/30/40 mm. The starter's assets/cube_blocks/usd/cube_{size}mm_{color}.usda
are one chamfered mesh per size (half-size h, 1 mm chamfer -> inner h-0.001), so the 20 mm twin is the
25 mm file with h 0.0125 -> 0.010, inner 0.0115 -> 0.009, names 25mm -> 20mm, and the mass from the
starter's own estimates (25/30/40 mm = 7.74/12.4/26.3 g) fitted as m = a*s^3 + b*s^2 (shell + infill):
a = 2.78e-4 g/mm^3, b = 5.45e-3 g/mm^2 -> 20 mm = 4.40 g (the fit gives 26.5 g at 40 mm, check).

    python sim_patches/make_cube_20mm.py ~/work/so101_sim_pickplace/assets/cube_blocks/usd
"""

import sys
from pathlib import Path

usd_dir = Path(sys.argv[1])
MASS_20MM_KG = 0.00440
for src in sorted(usd_dir.glob("cube_25mm_*.usda")):
    text = src.read_text()
    out = (text.replace("0.0125", "0.010").replace("0.0115", "0.009").replace("25mm", "20mm"))
    mass_line = next(l for l in text.splitlines() if "physics:mass" in l)
    out = out.replace(mass_line, mass_line.split("=")[0] + f"= {MASS_20MM_KG}")
    dst = src.with_name(src.name.replace("25mm", "20mm"))
    dst.write_text(out)
    print(f"{src.name} -> {dst.name}")
