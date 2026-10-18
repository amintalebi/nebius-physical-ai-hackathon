# 09 · Real-arm evaluation

**Points:** predicts Accuracy (30), proves Technical (15), turns the ablation into a Cosmos claim (Transfer 10).
**Time box:** T+7:15-8:30, plus a 9-trial check on any earlier checkpoint if the station is free.

## Why more than 3 trials

The judges run 3. Three trials cannot tell a 50 % policy from an 80 % one: the 95 % interval for 2/3 is
roughly 0.21-0.94 (`s2t.stats.wilson_interval`). To choose between checkpoints we need ≥ 18 trials
on the main candidate (2 per spot) and ≥ 9 on alternatives (1 per spot).

## Protocol (same as the judges, plus blindness)

1. A teammate **who does not run the policy** generates the order:
   `python scripts/eval_logger.py sequence --per-spot 2 --seed <any>` and places the cube; the operator
   doesn't see the list. Judges' order is hidden from us too; a policy tuned for a known order won't help.
2. Arm in the agreed start pose (02 §2.4). Cube on the spot, yaw varied by hand (0-45°).
3. `CKPT=… ./scripts/rollout.sh`. Stopwatch: 2 min cap.
4. **Success** = cube released and at rest on the green pad (brief). Anything else is a failure with one label:
   `missed_grasp · dropped · off_pad · not_released · timeout · collision · froze · other`.
5. Log immediately: `python scripts/eval_logger.py log --ckpt main_40k --spot B2 --result fail --failure off_pad --seconds 47`
6. Phone video of every trial (Technical evidence; failure analysis).

`python scripts/eval_logger.py summary` → `reports/eval_summary.md`: per-spot matrix, success rate with
95 % Wilson interval, P(≥2/3) per checkpoint, failure-mode counts.

## Order of evals

| Run | Trials | Why |
|---|---|---|
| `main` best checkpoint (by a quick 9-trial check between 30k and 40k) | 18 | the submission estimate |
| `ablation` same step | 9 | Cosmos effect (report both with intervals; 9 vs 18 trials can only show a large effect) |
| `main` + temporal ensembling | 9 | inference-only option |
| ensemble watchdog (10) | 9 | creativity claim, measured |

## Checkpoint choice rule (write it down before evaluating)

Submit the candidate with the most successes; on a tie, the one with fewer `collision`/`froze` failures
(those can end a trial early and look worse to a judge); on a further tie, the later checkpoint.
The main checkpoint must contain sim-derived data (the validator already guarantees it).

## Using failure modes

| Dominant failure | Likely cause | Action if time remains |
|---|---|---|
| `missed_grasp` on specific spots | thin data there / grasp height off | spend reserve real episodes on those spots; check spot coordinates |
| `off_pad` | placement imprecision | temporal ensembling; more real demos ending precisely on the pad |
| `not_released` | gripper action never opens | gripper unit offset (02) or the real demos release too late |
| `froze` / oscillation | policy uncertain at start | start pose mismatch with training data (02 §2.4) |

## Acceptance check

`reports/eval_summary.md` exists with ≥ 18 blind trials on the submitted checkpoint, every trial labelled,
and the checkpoint's sha256 noted. It is the honest prediction of the judged score.
