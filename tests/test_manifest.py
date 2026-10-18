import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from validate_manifest import check  # noqa: E402

FEATS = {
    "action": {"dtype": "float32", "shape": [6]},
    "observation.state": {"dtype": "float32", "shape": [6]},
    "observation.images.front": {"dtype": "video", "shape": [480, 640, 3]},
}


def ds(root: Path, rel: str, n: int, units=True, feats=FEATS):
    p = root / rel / "meta"
    p.mkdir(parents=True)
    info = {"codebase_version": "v3.0", "fps": 30, "total_episodes": n, "total_frames": n * 300, "features": feats}
    if units:
        info["s2t_units"] = {"mode": "degrees"}
    (p / "info.json").write_text(json.dumps(info))


def cfg():
    return {
        "caps": {"real_max": 50, "total_max": 300},
        "sources": {
            "real": {"kind": "real", "path": "r"},
            "A": {"kind": "sim", "path": "a"},
            "B": {"kind": "sim", "path": "b"},
            "Bc": {"kind": "cosmos", "path": "bc", "twin": "B"},
        },
        "mixes": {"main": ["real", "A", "Bc"], "ablation": ["real", "A", "B"]},
    }


def build(tmp, real=40, a=110, b=150, bc=150):
    ds(tmp, "r", real, units=False)
    ds(tmp, "a", a)
    ds(tmp, "b", b)
    ds(tmp, "bc", bc)


def test_valid_mix(tmp_path):
    build(tmp_path)
    m, errors, _ = check(cfg(), tmp_path)
    assert not errors
    assert m["mixes"]["main"]["per_kind"] == {"real": 40, "sim": 110, "cosmos": 150}


def test_real_cap(tmp_path):
    build(tmp_path, real=51, a=99)
    _, errors, _ = check(cfg(), tmp_path)
    assert any("real episodes 51" in e for e in errors)


def test_total_cap(tmp_path):
    build(tmp_path, a=111)
    _, errors, _ = check(cfg(), tmp_path)
    assert any("total episodes 301" in e for e in errors)


def test_uncontrolled_ablation_warns(tmp_path):
    build(tmp_path, b=140)
    _, _, warnings = check(cfg(), tmp_path)
    assert any("raw twin" in w for w in warnings)


def test_feature_mismatch(tmp_path):
    build(tmp_path)
    info = json.loads((tmp_path / "a/meta/info.json").read_text())
    info["features"]["observation.images.wrist"] = {"dtype": "video", "shape": [480, 640, 3]}
    (tmp_path / "a/meta/info.json").write_text(json.dumps(info))
    _, errors, _ = check(cfg(), tmp_path)
    assert any("features/fps differ" in e for e in errors)
