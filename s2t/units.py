"""Sim joint units -> real SO-101 LeRobot units.

Why this exists: the starter repo (ddiddi/so101-sim-pickplace-gr00t @ 52b23a9,
so101_pickplace/so101_units.py) writes sim joints mapped from the *USD joint limits* to [-100, 100].
The real arm, recorded with current LeRobot (@146d847), reports joints from *its own calibration file*:
`use_degrees=True` by default (robots/so_follower/config_so_follower.py), i.e.
    deg = (raw - (range_min + range_max) / 2) * 360 / 4095        (motors/motors_bus.py::_normalize)
and the gripper always in RANGE_0_100 over the calibrated [range_min, range_max].
The two are different numbers for the same physical pose, so raw sim actions would drive the real arm
to the wrong place. This module converts sim values into the real arm's units.

Assumption (verify with the open-loop replay test, docs/roadmap/02-station-sim-alignment.md):
the `so101_new_calib` USD zero pose equals the pose the arm was in when LeRobot calibration set the
half-turn homing (raw tick 2047). Per-joint `sign` and `offset_deg` in configs/station.yaml absorb
whatever the replay test shows is off.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np

JOINTS = ["shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex", "wrist_roll", "gripper"]
ARM_JOINTS = JOINTS[:5]

# Copied from the starter's so101_units.py so the inverse mapping cannot drift from what wrote the data.
SIM_GRIPPER_OPEN_RAD = 1.745
SIM_GRIPPER_CLOSE_RAD = -0.1745
SIM_ARM_RANGES_RAD = {
    "shoulder_pan": (-1.91986, 1.91986),
    "shoulder_lift": (-1.74533, 1.74533),
    "elbow_flex": (-1.69000, 1.69000),
    "wrist_flex": (-1.65806, 1.65806),
    "wrist_roll": (-2.74385, 2.74385),
}
_SIM_LO = np.array([SIM_ARM_RANGES_RAD[j][0] for j in ARM_JOINTS] + [SIM_GRIPPER_CLOSE_RAD])
_SIM_HI = np.array([SIM_ARM_RANGES_RAD[j][1] for j in ARM_JOINTS] + [SIM_GRIPPER_OPEN_RAD])
_SIM_SCALE = np.array([200.0] * 5 + [100.0])
_SIM_OFFSET = np.array([-100.0] * 5 + [0.0])

HOMING_TICK = 2047  # set_half_turn_homings(): present position becomes half the 12-bit encoder
TICKS_PER_REV = 4096
DEG_RES = 4095  # LeRobot uses (resolution - 1) in the DEGREES mapping


def sim_norm_to_rad(q_norm: np.ndarray) -> np.ndarray:
    """Inverse of the starter's rad_to_norm (no clipping: we want the exact value that was written)."""
    q = np.asarray(q_norm, dtype=np.float64)
    return (q - _SIM_OFFSET) / _SIM_SCALE * (_SIM_HI - _SIM_LO) + _SIM_LO


@dataclass
class MotorCal:
    range_min: int
    range_max: int
    drive_mode: int = 0


def load_calibration(path: str | Path) -> dict[str, MotorCal]:
    """Read a LeRobot calibration JSON (~/.cache/huggingface/lerobot/calibration/robots/<robot>/<id>.json)."""
    raw = json.loads(Path(path).read_text())
    cal = {}
    for j in JOINTS:
        if j not in raw:
            raise KeyError(f"calibration file {path} has no motor '{j}'")
        m = raw[j]
        cal[j] = MotorCal(int(m["range_min"]), int(m["range_max"]), int(m.get("drive_mode", 0)))
        if cal[j].range_min == cal[j].range_max:
            raise ValueError(f"motor {j}: range_min == range_max in {path}")
    return cal


def rad_to_real(
    q_rad: np.ndarray,
    cal: dict[str, MotorCal],
    mode: str = "degrees",
    signs: dict[str, int] | None = None,
    offsets_deg: dict[str, float] | None = None,
) -> np.ndarray:
    """Sim joint radians (N, 6) in JOINTS order -> real LeRobot units for this arm's calibration.

    mode="degrees": arm joints in LeRobot DEGREES (use_degrees=True, the current default).
    mode="range":   arm joints in RANGE_M100_100 (use_degrees=False).
    The gripper is RANGE_0_100 in both modes.
    """
    if mode not in ("degrees", "range"):
        raise ValueError(mode)
    signs = signs or {}
    offsets_deg = offsets_deg or {}
    q = np.atleast_2d(np.asarray(q_rad, dtype=np.float64))
    out = np.empty_like(q)
    for i, j in enumerate(JOINTS):
        c = cal[j]
        s = signs.get(j, 1)
        raw = HOMING_TICK + s * q[:, i] * TICKS_PER_REV / (2 * math.pi)
        raw = raw + offsets_deg.get(j, 0.0) * DEG_RES / 360.0
        if j == "gripper":
            b = np.clip(raw, c.range_min, c.range_max)
            v = (b - c.range_min) / (c.range_max - c.range_min) * 100.0
            out[:, i] = 100.0 - v if c.drive_mode else v
        elif mode == "degrees":
            mid = (c.range_min + c.range_max) / 2.0
            out[:, i] = (raw - mid) * 360.0 / DEG_RES
        else:
            b = np.clip(raw, c.range_min, c.range_max)
            v = (b - c.range_min) / (c.range_max - c.range_min) * 200.0 - 100.0
            out[:, i] = -v if c.drive_mode else v
    return out.astype(np.float32)


def sim_norm_to_real(q_norm, cal, mode="degrees", signs=None, offsets_deg=None) -> np.ndarray:
    return rad_to_real(sim_norm_to_rad(q_norm), cal, mode, signs, offsets_deg)
