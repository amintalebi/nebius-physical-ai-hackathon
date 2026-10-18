#!/usr/bin/env python3
"""Serve a LeRobot ACT checkpoint over ZeroMQ for closed-loop evaluation in Isaac Sim.

Isaac Lab (torch 2.11+cu130) and LeRobot live in separate venvs on the VM (roadmap 01), so the policy
runs here and scripts/eval_act_in_sim.py talks to it, the same split as the starter's GR00T server.
Inference is LeRobot's own path (lerobot @146d847: policies/utils.py prepare_observation_for_inference,
policies/factory.py make_pre_post_processors, ACTPolicy.select_action with its action queue), so
the sim eval exercises the same normalisation the real-arm rollout will use.

    ~/work/env_lerobot/bin/python scripts/act_server.py \
        --ckpt outputs/act_sim_A/checkpoints/020000/pretrained_model --port 5556

Protocol (REQ/REP, msgpack + msgpack_numpy):
    {"cmd": "ping"}                                   -> {"ok": True, "image_keys": [...], "state_dim": 6}
    {"cmd": "reset"}                                  -> {"ok": True}       (clears ACT's action queue)
    {"cmd": "act", "state": (6,) f32, "images": {"front": HxWx3 u8, ...}, "task": str}
                                                      -> {"ok": True, "action": (6,) f32}
"""

from __future__ import annotations

import argparse
import time

import msgpack
import msgpack_numpy
import numpy as np
import torch
import zmq

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("--ckpt", required=True, help="…/checkpoints/<step>/pretrained_model")
ap.add_argument("--port", type=int, default=5556)
ap.add_argument("--device", default="cuda")
args = ap.parse_args()

from lerobot.configs.policies import PreTrainedConfig  # noqa: E402
from lerobot.policies.act.modeling_act import ACTPolicy  # noqa: E402
from lerobot.policies.factory import make_pre_post_processors  # noqa: E402
from lerobot.policies.utils import prepare_observation_for_inference  # noqa: E402

cfg = PreTrainedConfig.from_pretrained(args.ckpt)
cfg.device = args.device
policy = ACTPolicy.from_pretrained(args.ckpt, config=cfg).to(args.device).eval()
pre, post = make_pre_post_processors(
    policy_cfg=cfg, pretrained_path=args.ckpt, preprocessor_overrides={"device_processor": {"device": args.device}}
)
image_keys = [k.removeprefix("observation.images.") for k in cfg.input_features if k.startswith("observation.images.")]
state_dim = cfg.input_features["observation.state"].shape[0]
print(f"[act_server] {args.ckpt}: images {image_keys}, state {state_dim}, chunk {cfg.chunk_size}, "
      f"n_action_steps {cfg.n_action_steps}, port {args.port}", flush=True)

sock = zmq.Context().socket(zmq.REP)
sock.bind(f"tcp://127.0.0.1:{args.port}")
n, t_sum = 0, 0.0
while True:
    req = msgpack.unpackb(sock.recv(), object_hook=msgpack_numpy.decode)
    cmd = req.get("cmd")
    try:
        if cmd == "ping":
            rep = {"ok": True, "image_keys": image_keys, "state_dim": state_dim}
        elif cmd == "reset":
            policy.reset()
            pre.reset()
            post.reset()
            rep = {"ok": True}
        elif cmd == "act":
            t0 = time.perf_counter()
            obs = {"observation.state": np.asarray(req["state"], dtype=np.float32)}
            for k in image_keys:
                obs[f"observation.images.{k}"] = np.ascontiguousarray(req["images"][k], dtype=np.uint8)
            batch = pre(prepare_observation_for_inference(obs, torch.device(args.device), req.get("task", "")))
            with torch.inference_mode():
                action = post(policy.select_action(batch))
            rep = {"ok": True, "action": action.squeeze(0).float().cpu().numpy()}
            n, t_sum = n + 1, t_sum + time.perf_counter() - t0
            if n % 1000 == 0:
                print(f"[act_server] {n} steps, mean {1e3 * t_sum / n:.1f} ms/step", flush=True)
        else:
            rep = {"ok": False, "error": f"unknown cmd {cmd!r}"}
    except Exception as e:  # report to the client instead of leaving it blocked on recv()
        rep = {"ok": False, "error": f"{type(e).__name__}: {e}"}
    sock.send(msgpack.packb(rep, default=msgpack_numpy.encode))
