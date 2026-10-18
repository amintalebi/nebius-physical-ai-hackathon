"""lerobot-edit-dataset delete_episodes drops "fps" from the non-video features that convert_dataset_v21_to_v30
keeps; merge then refuses ("Same features is expected"). Put it back so both paths match."""
import json, sys
for root in sys.argv[1:]:
    p = f"{root}/meta/info.json"; info = json.load(open(p))
    for k, f in info["features"].items():
        if f.get("dtype") != "video" and "fps" not in f:
            f["fps"] = info["fps"]
    json.dump(info, open(p, "w"), indent=4)
    print("fps restored:", root)
