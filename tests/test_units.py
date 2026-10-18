import math

import numpy as np
import pytest

from s2t.units import (
    JOINTS, MotorCal, SIM_ARM_RANGES_RAD, SIM_GRIPPER_CLOSE_RAD, SIM_GRIPPER_OPEN_RAD, rad_to_real, sim_norm_to_rad,
)


def starter_rad_to_norm(q):
    """Verbatim logic of the starter's so101_units.rad_to_norm, to prove our inverse matches it."""
    lo = np.array([SIM_ARM_RANGES_RAD[j][0] for j in JOINTS[:5]] + [SIM_GRIPPER_CLOSE_RAD])
    hi = np.array([SIM_ARM_RANGES_RAD[j][1] for j in JOINTS[:5]] + [SIM_GRIPPER_OPEN_RAD])
    return (q - lo) / (hi - lo) * np.array([200.0] * 5 + [100.0]) + np.array([-100.0] * 5 + [0.0])


def sym_cal(half=1000):
    return {j: MotorCal(2047 - half, 2047 + half) for j in JOINTS}


def test_inverse_of_starter_mapping():
    rng = np.random.default_rng(0)
    q = rng.uniform(-1.5, 1.5, size=(50, 6))
    assert np.allclose(sim_norm_to_rad(starter_rad_to_norm(q)), q, atol=1e-9)


def test_zero_pose_is_zero_degrees_with_centred_range():
    out = rad_to_real(np.zeros((1, 6)), sym_cal(), "degrees")
    assert np.allclose(out[0, :5], 0.0, atol=1e-3)


def test_quarter_turn_is_about_90_degrees():
    q = np.zeros((1, 6))
    q[0, 1] = math.pi / 2
    out = rad_to_real(q, sym_cal(1500), "degrees")
    assert out[0, 1] == pytest.approx(90.0, abs=0.1)


def test_off_centre_calibration_shifts_degrees():
    # range recorded asymmetrically: mid = 2247 -> 200 ticks -> about -17.6 deg at the homing pose
    cal = sym_cal()
    cal["elbow_flex"] = MotorCal(1247, 3247)
    out = rad_to_real(np.zeros((1, 6)), cal, "degrees")
    assert out[0, 2] == pytest.approx(-200 * 360 / 4095, abs=1e-3)


def test_range_mode_and_gripper_bounds():
    cal = sym_cal()
    out = rad_to_real(np.zeros((1, 6)), cal, "range")
    assert np.allclose(out[0, :5], 0.0, atol=0.2)
    big = np.full((1, 6), 3.0)
    out = rad_to_real(big, cal, "range")
    assert np.all(out[0, :5] <= 100.0) and 0.0 <= out[0, 5] <= 100.0


def test_sign_flip():
    q = np.zeros((1, 6))
    q[0, 0] = 0.5
    a = rad_to_real(q, sym_cal(), "degrees")
    b = rad_to_real(q, sym_cal(), "degrees", signs={"shoulder_pan": -1})
    assert a[0, 0] == pytest.approx(-b[0, 0], abs=1e-3)
