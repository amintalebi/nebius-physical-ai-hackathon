"""End-to-end check of scripts/convert_sim_dataset.py on a tiny fake starter (v2.1) dataset."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import yaml

REPO = Path(__file__).resolve().parents[1]
NAMES = [f"{j}.pos" for j in ["shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex", "wrist_roll", "gripper"]]


def fake_dataset(root: Path, n=20):
    (root / "meta").mkdir(parents=True)
    vid = {"dtype": "video", "shape": [480, 640, 3], "names": ["height", "width", "channels"], "info": {}}
    info = {"codebase_version": "v2.1", "fps": 30, "total_episodes": 1, "total_frames": n, "total_videos": 2,
            "features": {"action": {"dtype": "float32", "shape": [6], "names": NAMES},
                         "observation.state": {"dtype": "float32", "shape": [6], "names": NAMES},
                         "observation.images.front": vid, "observation.images.wrist": dict(vid)}}
    (root / "meta/info.json").write_text(json.dumps(info))
    stats = {"episode_index": 0, "stats": {"action": {}, "observation.state": {}, "observation.images.front": {"mean": 1},
                                           "observation.images.wrist": {"mean": 2}}}
    (root / "meta/episodes_stats.jsonl").write_text(json.dumps(stats) + "\n")
    (root / "meta/episodes.jsonl").write_text(json.dumps({"episode_index": 0, "length": n}) + "\n")
    (root / "meta/modality.json").write_text("{}")
    zeros_norm = [[0.0] * 5 + [8.25]] * n  # sim norm 0 = 0 rad for arm joints
    t = pa.table({"action": pa.array(zeros_norm, type=pa.list_(pa.float32())),
                  "observation.state": pa.array(zeros_norm, type=pa.list_(pa.float32())),
                  "episode_index": pa.array(np.zeros(n, dtype=np.int64))})
    (root / "data/chunk-000").mkdir(parents=True)
    pq.write_table(t, root / "data/chunk-000/episode_000000.parquet")
    for cam in ("front", "wrist"):
        d = root / f"videos/chunk-000/observation.images.{cam}"
        d.mkdir(parents=True)
        (d / "episode_000000.mp4").write_bytes(b"fake")


def test_convert(tmp_path):
    src = tmp_path / "sim"
    fake_dataset(src)
    work = tmp_path / "repo"
    shutil.copytree(REPO / "scripts", work / "scripts")
    shutil.copytree(REPO / "s2t", work / "s2t")
    (work / "configs/calibration").mkdir(parents=True)
    st = yaml.safe_load((REPO / "configs/station.yaml").read_text())
    (work / "configs/station.yaml").write_text(yaml.safe_dump(st))
    cal = {j.removesuffix(".pos"): {"id": i + 1, "drive_mode": 0, "homing_offset": 0, "range_min": 1047, "range_max": 3047}
           for i, j in enumerate(NAMES)}
    (work / st["robot"]["calibration_file"]).write_text(json.dumps(cal))
    dst = tmp_path / "out"
    r = subprocess.run([sys.executable, str(work / "scripts/convert_sim_dataset.py"), "--src", str(src), "--dst", str(dst)],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    info = json.loads((dst / "meta/info.json").read_text())
    assert "observation.images.wrist" not in info["features"]
    assert info["s2t_units"]["mode"] == "degrees"
    assert not (dst / "videos/chunk-000/observation.images.wrist").exists()
    assert not (dst / "meta/modality.json").exists()
    act = np.stack(pq.read_table(dst / "data/chunk-000/episode_000000.parquet")["action"].to_numpy(zero_copy_only=False))
    assert np.allclose(act[:, :5], 0.0, atol=1e-2)  # zero rad at a centred calibration = 0 deg
    s = json.loads((dst / "meta/episodes_stats.jsonl").read_text())["stats"]
    assert "observation.images.wrist" not in s and s["action"]["count"] == [20]
    # refuses to convert twice
    r2 = subprocess.run([sys.executable, str(work / "scripts/convert_sim_dataset.py"), "--src", str(dst),
                         "--dst", str(tmp_path / "out2")], capture_output=True, text=True)
    assert r2.returncode != 0 and "twice" in r2.stdout + r2.stderr
