import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from build_mixes import even_subset, plan  # noqa: E402


def ds(root, rel, n):
    (root / rel / "meta").mkdir(parents=True)
    (root / rel / "meta/info.json").write_text(json.dumps({"total_episodes": n}))


def test_even_subset_keeps_spread():
    kept = list(range(90))  # 9 spots x 10, recorded spot by spot
    sub = even_subset(kept, 45)
    assert len(sub) == 45
    per_spot = [sum(1 for i in sub if i // 10 == s) for s in range(9)]
    assert min(per_spot) >= 4 and max(per_spot) <= 6


def test_twins_share_drops_and_cap(tmp_path):
    ds(tmp_path, "rawB", 20)
    ds(tmp_path, "cosB", 20)
    ds(tmp_path, "real", 10)
    (tmp_path / "cur").mkdir()
    (tmp_path / "cur/d.json").write_text(json.dumps({"datasets": {
        "cos": {"drop": [1, 2]}, "rawB": {"drop": [5]}, "real": {"drop": [0]}}}))
    (tmp_path / "cur/extra.json").write_text(json.dumps({"drop": [19]}))
    cfg = {"curation_file": "cur/d.json", "sources": {
        "real": {"kind": "real", "raw": "real", "path": "x"},
        "rawB": {"kind": "sim", "raw": "rawB", "path": "y"},
        "cos": {"kind": "cosmos", "raw": "cosB", "path": "z", "twin": "rawB", "max_episodes": 10,
                "extra_drops": "cur/extra.json"}}}
    remove, keep = plan(cfg, tmp_path)
    assert keep["cos"] == keep["rawB"]
    assert len(keep["cos"]) == 10
    assert not {1, 2, 5, 19} & set(keep["cos"])
    assert remove["real"] == [0]
