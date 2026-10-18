Put the organizers' calibration file for our follower arm here, named `<robot.id>.json`
(`robot.id` from `configs/station.yaml`).

On the station laptop it is at `~/.cache/huggingface/lerobot/calibration/robots/<robot_name>/<id>.json`
(LeRobot `HF_LEROBOT_CALIBRATION`, `robots/robot.py`). Do **not** recalibrate the arm: every unit
conversion and every recorded real episode depends on this exact file. If it ever changes,
re-run `scripts/convert_sim_dataset.py` for all sim/Cosmos data and treat older real episodes as suspect.
