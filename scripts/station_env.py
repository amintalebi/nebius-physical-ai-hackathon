#!/usr/bin/env python3
"""Print configs/station.yaml as shell exports so the .sh wrappers have one source of truth.

    eval "$(python3 scripts/station_env.py)"
"""

import shlex
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
st = yaml.safe_load((REPO / "configs/station.yaml").read_text())
r, t, c = st["robot"], st["teleop"], st["camera"]
cams = "{%s: {type: opencv, index_or_path: %s, width: %d, height: %d, fps: %d}}" % (
    c["key"], c["index_or_path"], c["width"], c["height"], c["fps"])
calib_dir = (REPO / r["calibration_file"]).parent
env = {
    "ROBOT_TYPE": r["type"], "ROBOT_PORT": r["port"], "ROBOT_ID": r["id"],
    "ROBOT_USE_DEGREES": str(r["use_degrees"]).lower(), "ROBOT_CALIB_DIR": str(calib_dir),
    "TELEOP_TYPE": t["type"], "TELEOP_PORT": t["port"], "TELEOP_ID": t["id"],
    "CAMERAS": cams, "TASK": st["task"],
}
for k, v in env.items():
    print(f"export {k}={shlex.quote(str(v))}")
