# 10 · Ensemble (creativity)

**Points:** Creativity 15 ("Ensemble of models used"), and possibly Accuracy if it is allowed in judged trials.
**Time box:** prepare T+6:00-7:15 (while training); evaluate 9 trials at T+8:00.

## Design: act, verify, retry within the 2-minute cap

A trial allows 120 s; one ACT attempt takes ~15-30 s. Most failures leave the cube on the table, often still
reachable. So the ensemble is:

1. **Actors**: 2-3 ACT checkpoints that fail differently: `act_main`, `act_main_s2` (different seed), and
   `act_main` with temporal ensembling. They are tried in rotation.
2. **Verifier**: Cosmos Reason looks at one camera frame after each attempt: "is the cube released and resting
   on the green pad?"
3. **Policy**: stop on yes; otherwise next actor, until ~115 s are used.

```bash
python scripts/watchdog_rollout.py \
  --ckpts outputs/act_main/checkpoints/040000/pretrained_model outputs/act_main_s2/checkpoints/040000/pretrained_model \
  --reason-url http://<vm-gpu>:8000/v1 --attempt-seconds 40 --spot B2
```

Every attempt and verdict goes to `data/eval/watchdog.jsonl`.

This uses three kinds of models (an imitation policy, a second seed of it, and a vision-language world model as
judge). Each one fixes a weakness of the others: ACT can't tell that it failed, and Reason can't act.
A plainer alternative that also counts as an ensemble is averaging the action chunks of several ACT
checkpoints at every step. It needs a custom inference loop and adds latency, so it is second priority.

## Acceptance check (measured, like everything else)

- 9 blind trials (1 per spot) of the watchdog, logged with `eval_logger.py --ckpt ensemble`, compared with the
  single-checkpoint rate on the same spots. Report both, with intervals.
- **Verifier accuracy:** after each watchdog trial, the human success label vs Reason's last verdict. If Reason
  says "on pad" when it is not, the watchdog stops early. Report the confusion counts.
- Latency: the Reason call over the network must be ≤ 5 s (check in the log timestamps).

## Rules risk

The judges "run the main checkpoint". Whether a retry wrapper is allowed in judged trials is unknown
([open-questions](open-questions.md)). Default: **judged trials use plain `rollout.sh` with the main checkpoint**;
the ensemble is presented as creativity with its own measured results. Use it in judged trials only with
explicit permission.
