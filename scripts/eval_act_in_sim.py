#!/usr/bin/env python3
"""Closed-loop evaluation of an ACT checkpoint in the Isaac Lab scene, spot by spot.

The sim counterpart of roadmap 09: same 9 grid spots, same success test the expert's data was
filtered with (starter mdp.cube_placed: cube at rest on the pad, jaw open, gripper clear, held for
--success_steps frames), same per-trial cap. Start scripts/act_server.py first (LeRobot venv), then
run this with the Isaac Lab python, from anywhere:

    $ISAACLAB_PY scripts/eval_act_in_sim.py --starter ~/work/so101_sim_pickplace --per-spot 2 \
        --ckpt-name act_sim_A_20k --out reports/sim_eval_act_sim_A_20k.jsonl [--record_dir logs/eval]

Observations are built exactly like collect_demos.py writes the dataset (front/wrist 640x480 RGB,
state = so101_units.rad_to_norm of the joint positions); actions come back in the same units and are
executed with norm_to_rad on the joint-space env (starter eval_in_sim.py, @52b23a9). The pad and the
front camera are pinned from configs/station.yaml like scripts/collect_grid.py does, and each spot
is set by rewriting the cube reset event's pose_range, so one Isaac launch covers all spots.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
pre = argparse.ArgumentParser(add_help=False)
pre.add_argument("--starter", type=Path, default=Path.home() / "work/so101_sim_pickplace")
known, _ = pre.parse_known_args()
sys.path.insert(0, str(known.starter / "scripts"))  # starter's _common (launch helpers) and package root

from _common import build_env_cfg, launch_simulation, make_parser, parse_args  # noqa: E402

parser = make_parser(__doc__)
parser.add_argument("--starter", type=Path, default=known.starter)
parser.add_argument("--station", type=Path, default=REPO / "configs/station.yaml")
parser.add_argument("--spots", nargs="*", help="subset of grid spot names, default all 9")
parser.add_argument("--per-spot", type=int, default=2)
parser.add_argument("--jitter", type=float, default=0.012, help="+- m around each spot, as in collection")
parser.add_argument("--policy_port", type=int, default=5556)
parser.add_argument("--ckpt-name", required=True, help="label written to every result row")
parser.add_argument("--max_steps", type=int, default=900, help="30 s at 30 Hz; the judged cap is 120 s")
parser.add_argument("--success_steps", type=int, default=15)
parser.add_argument("--out", type=Path, required=True, help="jsonl, one row per trial (appended)")
parser.add_argument("--record_dir", type=str, default="", help="front-camera mp4 per trial")
args = parse_args(parser)

st = yaml.safe_load(args.station.read_text())
g = st["geometry"]
os.environ.update(  # read by the patched pickplace_env_cfg at import time (sim_patches/s2t_station.patch)
    S2T_PAD_XY="{},{}".format(*g["pad_center_xy"]),
    S2T_CAM_POS=",".join(map(str, g["front_cam_pos"])),
    S2T_CAM_LOOK_AT=",".join(map(str, g["front_cam_look_at"])),
    CUBE_SIZE_MM=str(round(g["cube_size_m"] * 1000)),
    CUBE_COLOR=g["cube_color"],
)
from so101_pickplace.pickplace_env_cfg import CUBE_SIZE, IMAGE_HEIGHT, IMAGE_WIDTH, SO101PickPlaceJointEnvCfg  # noqa: E402

env_cfg = build_env_cfg(SO101PickPlaceJointEnvCfg, args)
assert env_cfg.scene.num_envs == 1
spots = {k: v for k, v in g["grid_spots_xy"].items() if not args.spots or k in args.spots}

with launch_simulation(env_cfg, args):
    import subprocess

    import gymnasium as gym
    import msgpack
    import msgpack_numpy
    import numpy as np
    import torch
    import zmq

    import so101_pickplace  # noqa: F401
    from so101_pickplace import TASK_JOINT, mdp
    from so101_pickplace.so101_units import JOINTS, norm_to_rad, rad_to_norm

    sock = zmq.Context().socket(zmq.REQ)
    sock.setsockopt(zmq.RCVTIMEO, 60_000)
    sock.connect(f"tcp://127.0.0.1:{args.policy_port}")

    def call(**req):
        sock.send(msgpack.packb(req, default=msgpack_numpy.encode))
        rep = msgpack.unpackb(sock.recv(), object_hook=msgpack_numpy.decode)
        if not rep.get("ok"):
            raise SystemExit(f"act_server error: {rep.get('error')}")
        return rep

    info = call(cmd="ping")
    image_keys = info["image_keys"]
    print(f"[eval] policy wants images {image_keys}, state {info['state_dim']}", flush=True)

    env = gym.make(TASK_JOINT, cfg=env_cfg).unwrapped
    robot = env.scene["robot"]
    jidx = torch.as_tensor(robot.find_joints(JOINTS, preserve_order=True)[0], device=env.device)
    cams = {k: env.scene[f"{k}_cam"] for k in ("front", "wrist")}
    missing = set(image_keys) - set(cams)
    if missing:
        raise SystemExit(f"policy needs cameras {missing} that the scene does not have")

    def frame(k):
        return np.ascontiguousarray(cams[k].data.output["rgb"].torch[0, :, :, :3].cpu().numpy().astype(np.uint8))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for spot, (x, y) in spots.items():
        term = env.event_manager.get_term_cfg("randomize_cube_pose")
        term.params["pose_range"] = {
            "x": (x - args.jitter, x + args.jitter), "y": (y - args.jitter, y + args.jitter),
            "z": (CUBE_SIZE / 2, CUBE_SIZE / 2), "yaw": (-0.8, 0.8),
        }
        env.event_manager.set_term_cfg("randomize_cube_pose", term)
        for k in range(args.per_spot):
            env.reset()
            call(cmd="reset")
            rec = None
            if args.record_dir:
                os.makedirs(args.record_dir, exist_ok=True)
                path = os.path.join(args.record_dir, f"{args.ckpt_name}_{spot}_{k}.mp4")
                rec = subprocess.Popen(
                    ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s",
                     f"{IMAGE_WIDTH}x{IMAGE_HEIGHT}", "-r", "30", "-i", "-", "-an", "-c:v", "libx264",
                     "-pix_fmt", "yuv420p", "-crf", "23", path], stdin=subprocess.PIPE)
            outcome, held, t, t0 = "timeout", 0, 0, time.perf_counter()
            while t < args.max_steps:
                state = rad_to_norm(robot.data.joint_pos.torch[0, jidx].cpu().numpy()).astype(np.float32)
                imgs = {c: frame(c) for c in image_keys}
                action = call(cmd="act", state=state, images=imgs, task=st["task"])["action"]
                env.step(torch.as_tensor(norm_to_rad(action), device=env.device, dtype=torch.float32).unsqueeze(0))
                t += 1
                if rec is not None:
                    rec.stdin.write(frame("front").tobytes())
                if bool(mdp.cube_dropped(env)[0]):
                    outcome = "dropped"
                    break
                held = held + 1 if bool(mdp.cube_placed(env)[0]) else 0
                if held >= args.success_steps:
                    outcome = "success"
                    break
            if rec is not None:
                rec.stdin.close()
                rec.wait()
            row = {"ckpt": args.ckpt_name, "spot": spot, "trial": k, "outcome": outcome, "steps": t,
                   "sim_seconds": round(t / 30, 1), "wall_seconds": round(time.perf_counter() - t0, 1)}
            rows.append(row)
            with args.out.open("a") as f:
                f.write(json.dumps(row) + "\n")
            print(f"[eval] {spot} #{k}: {outcome} after {t} steps", flush=True)

    ok = sum(r["outcome"] == "success" for r in rows)
    print(f"[eval] {args.ckpt_name}: {ok}/{len(rows)} = {ok / max(len(rows), 1):.2f}")
    for spot in spots:
        rs = [r for r in rows if r["spot"] == spot]
        print(f"[eval]   {spot}: {sum(r['outcome'] == 'success' for r in rs)}/{len(rs)}  "
              f"{ {o: sum(r['outcome'] == o for r in rs) for o in {r['outcome'] for r in rs}} }")
    env.close()
