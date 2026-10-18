#!/usr/bin/env python3
"""Read leader and follower joint positions side by side, in the units teleop uses (read-only).

Put both arms in the same physical pose (e.g. both folded at rest). If the calibrations agree, the per-joint
difference is a few units; a large, steady difference on one joint means that arm's calibration is off for
that joint (recalibrate the LEADER, never the follower). Nothing is written to the motors.

    ../lerobot/.venv/bin/python scripts/compare_arms.py --seconds 20
"""

import argparse
import time

import yaml
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("--seconds", type=float, default=20)
args = ap.parse_args()

st = yaml.safe_load((REPO / "configs/station.yaml").read_text())
from lerobot.robots.so_follower import SOFollower, SOFollowerRobotConfig  # noqa: E402
from lerobot.teleoperators.so_leader import SOLeader, SOLeaderTeleopConfig  # noqa: E402

cal_dir = (REPO / st["robot"]["calibration_file"]).parent
fol = SOFollower(SOFollowerRobotConfig(port=st["robot"]["port"], id=st["robot"]["id"], calibration_dir=cal_dir,
                                       use_degrees=st["robot"]["use_degrees"]))
lead = SOLeader(SOLeaderTeleopConfig(port=st["teleop"]["port"], id=st["teleop"]["id"], calibration_dir=cal_dir,
                                     use_degrees=st["teleop"].get("use_degrees", False)))
for d in (fol, lead):
    d.bus.connect()
try:
    t_end = time.time() + args.seconds
    while time.time() < t_end:
        f = fol.bus.sync_read("Present_Position")
        l = lead.bus.sync_read("Present_Position")
        short = {"shoulder_pan": "pan", "shoulder_lift": "lift", "elbow_flex": "elbow", "wrist_flex": "wflex",
                 "wrist_roll": "wroll", "gripper": "grip"}
        print("  ".join(f"{short.get(k, k)}: L{l[k]:6.1f} F{f[k]:6.1f} d{l[k] - f[k]:+6.1f}" for k in f), flush=True)
        time.sleep(1.0)
finally:
    for d in (fol, lead):
        d.bus.disconnect(disable_torque=False)
