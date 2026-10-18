"""Make a real dataset's info.json metadata match the sim mix so lerobot-edit-dataset merge accepts it.
Same robot and features; only labels differ: robot_type (so_follower vs so101_follower), per-feature fps keys,
and the video encoder metadata (real AV1 vs sim H.264). Videos are decoded from the files themselves, and the
merge keeps one video file per source (concatenate_videos=false), so the codecs never share a file."""
import json, sys
ref, tgt = sys.argv[1], sys.argv[2]
r = json.load(open(f"{ref}/meta/info.json")); p = f"{tgt}/meta/info.json"; t = json.load(open(p))
assert set(r["features"]) == set(t["features"]), set(r["features"]) ^ set(t["features"])
t["features"] = r["features"]; t["robot_type"] = r["robot_type"]
json.dump(t, open(p, "w"), indent=4); print("aligned", tgt, "to", ref)
