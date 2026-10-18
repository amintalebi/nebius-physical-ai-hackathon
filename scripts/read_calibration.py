#!/usr/bin/env python3
"""Recover an SO-101's LeRobot calibration JSON from the motors themselves (read-only).

LeRobot's calibration writes homing offsets and position limits into each Feetech motor and also
saves them as JSON on the calibrating machine. On a new laptop the JSON is missing, and connecting
then starts an interactive *re*-calibration, which would replace the organizers' calibration. This
reads the registers back (lerobot @146d847 motors_bus.py read_calibration) and writes the JSON
LeRobot expects, so robot.connect() finds a matching calibration and does not prompt. Nothing is
written to the motors and torque is left as it is.

    python scripts/read_calibration.py --port /dev/tty.usbmodemXXXX --type so101_follower --id station_follower
    python scripts/read_calibration.py --port /dev/tty.usbmodemYYYY --type so101_leader --id station_leader
    python scripts/read_calibration.py --port … --type … --id … --watch 5   # print positions: which arm is this?
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import asdict

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("--port", required=True)
ap.add_argument("--type", required=True, choices=["so101_follower", "so101_leader"])
ap.add_argument("--id", required=True, help="robot.id / teleop.id used on the command line later")
ap.add_argument("--watch", type=float, default=0, help="seconds to print raw positions instead (move the arm by hand)")
ap.add_argument("--dry-run", action="store_true", help="print the calibration, do not write the JSON")
args = ap.parse_args()

if args.type == "so101_follower":
    from lerobot.robots.so_follower import SOFollower as Device, SOFollowerRobotConfig as Cfg
else:
    from lerobot.teleoperators.so_leader import SOLeader as Device, SOLeaderTeleopConfig as Cfg

dev = Device(Cfg(port=args.port, id=args.id))
dev.bus.connect()
try:
    if args.watch:
        t_end = time.time() + args.watch
        while time.time() < t_end:
            pos = dev.bus.sync_read("Present_Position", normalize=False)
            print("  ".join(f"{k}={v:4d}" for k, v in pos.items()), flush=True)
            time.sleep(0.5)
    else:
        cal = dev.bus.read_calibration()
        print(json.dumps({k: asdict(v) for k, v in cal.items()}, indent=1))
        if not args.dry_run:
            dev.calibration = cal
            dev._save_calibration()
            print(f"saved {dev.calibration_fpath}")
finally:
    dev.bus.disconnect(disable_torque=False)
