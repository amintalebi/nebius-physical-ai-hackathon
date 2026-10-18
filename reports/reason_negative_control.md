# Cosmos Reason curator: negative control

Model `dedicated/nvidia/Cosmos3-Super-Reasoner-4KvIHP`, request identical to `scripts/cosmos_reason_score.py` (inline mp4, fps 4, temperature 0.6, top_p 0.95, max_tokens 2048).
Curation rule under test: `keep iff task_success and not visual_defect and motion_quality >= 3`. Expected labels are known by construction (see table).

## Prompt v1 (16 clips, 6 positive, 10 negative)

| | predicted keep | predicted drop |
|---|---|---|
| expected keep | 6 | 0 |
| expected drop | 7 | 3 |

- accuracy 0.56, Cohen's kappa 0.24, false keeps 7, false drops 0, unparsed 0
- per-field agreement with construction labels: `task_success` 12/16, `visual_defect` 13/16
- latency per call (s): mean 5.8, median 5.6, min 3.9, max 9.7

| clip | expected | pred keep | task_success | visual_defect | motion | failure_mode | notes |
|---|---|---|---|---|---|---|---|
| `pos_sim_A_000000` | keep | True | True | False | 5 | none | The robot successfully picked up the red cube and placed it on the green pad without errors. |
| `pos_sim_A_000005` | keep | True | True | False | 5 | none | The robot arm successfully picked up the red cube, moved it over the green pad, and released it without any errors. |
| `pos_sim_A_000010` | keep | True | True | False | 5 | none | The robot arm successfully grasped the red cube, moved it to the green pad, and released it without errors. |
| `pos_sim_A_000015` | keep | True | True | False | 5 | none | The robot successfully picked up the cube, moved it to the green pad, and released it as instructed. |
| `pos_sim_A_000020` | keep | True | True | False | 5 | none | The robot arm successfully grasped the red cube, moved it over the green pad, and released it, completing the task as intended. |
| `pos_sim_A_000025` | keep | True | True | False | 5 | none | The robot arm successfully grasped the red cube, moved it to the green pad, and released it without any issues. |
| `neg_rollout_act_smoke_300_B2_0` | drop | True **WRONG** | True | False | 5 | none | The robot successfully grasped the red cube, moved it to the green pad, and released it. |
| `neg_trunc_000003` | drop | False | False | False | 3 | incomplete | The robot arm successfully grasped the red cube but did not move or place it on the green pad, leaving the task incomplete. |
| `neg_trunc2_000007` | drop | True **WRONG** | True | False | 5 | none | The robot arm successfully grasped the red cube, moved it to the green pad, and released it without any issues. |
| `neg_rev_000012` | drop | True **WRONG** | True | False | 5 | none | The robot successfully grasped the red cube, moved it to the green pad, and released it as instructed. |
| `neg_rev2_000017` | drop | True **WRONG** | True | False | 4 | none | The robot successfully grasped the red cube, moved it off the green pad, and returned it to the pad, releasing it as instructed. |
| `neg_freeze_000022` | drop | False | False | False | 1 | incomplete | The robot arm remains stationary throughout the video and does not perform any grasping or placement actions. |
| `neg_freeze2_000027` | drop | False | False | False | 1 | incomplete | The robot arm remains stationary throughout the video and does not interact with the red cube. |
| `neg_redbox_000030` | drop | True **WRONG** | True | False | 5 | none | The robot arm successfully picked up the red cube and placed it on the green pad, releasing it as intended. |
| `neg_splice_000013_000018` | drop | True **WRONG** | True | False | 5 | none | The robot arm successfully grasped the red cube, moved it over the green pad, and released it without any errors or visual anomalies. |
| `neg_dup_000033` | drop | True **WRONG** | True | False | 4 | none | The robot arm successfully grasped the red cube, moved it to the green pad, and released it without issues. |

## Prompt v2 (13 clips, 3 positive, 10 negative)

| | predicted keep | predicted drop |
|---|---|---|
| expected keep | 3 | 0 |
| expected drop | 7 | 3 |

- accuracy 0.46, Cohen's kappa 0.17, false keeps 7, false drops 0, unparsed 0
- per-field agreement with construction labels: `task_success` 9/13, `visual_defect` 10/13
- latency per call (s): mean 4.4, median 4.4, min 3.3, max 5.2

| clip | expected | pred keep | task_success | visual_defect | motion | failure_mode | notes |
|---|---|---|---|---|---|---|---|
| `pos_sim_A_000000` | keep | True | True | False | 5 | none | The robot arm successfully grasped the red cube, moved it to the green pad, and released it without any errors or visual anomalies. |
| `pos_sim_A_000010` | keep | True | True | False | 5 | none | The robot arm successfully grasped the red cube, moved it to the green pad, and released it without any errors or visual anomalies. |
| `pos_sim_A_000020` | keep | True | True | False | 5 | none | The robot arm successfully grasped the red cube, moved it to the green pad, and released it, with no visual anomalies or failures observed. |
| `neg_rollout_act_smoke_300_B2_0` | drop | True **WRONG** | True | False | 5 | none | The robot arm successfully grasped the red cube, moved it over the green pad, and released it onto the pad as intended. |
| `neg_trunc_000003` | drop | True **WRONG** | True | False | 5 | none | The robot arm successfully picked up the cube, moved it to the green pad, and released it, with no visual anomalies or failures observed. |
| `neg_trunc2_000007` | drop | False | False | False | 3 | incomplete | The robot arm has closed its grippers around the red cube but has not lifted or moved it to the green pad yet. |
| `neg_rev_000012` | drop | True **WRONG** | True | False | 4 | none | The robot arm successfully grasped the red cube from the green pad, moved it to the right, and released it onto the table surface. |
| `neg_rev2_000017` | drop | True **WRONG** | True | False | 5 | none | The robot arm successfully grasps the red cube, moves it to the right, and releases it onto the green pad as instructed. |
| `neg_freeze_000022` | drop | False | False | False | 1 | incomplete | The robot arm remains stationary throughout the video, showing no movement toward or interaction with either the red or green block. |
| `neg_freeze2_000027` | drop | False | False | False | 1 | incomplete | The robot arm remains stationary with open grippers; no grasping, movement, or placement occurs. |
| `neg_redbox_000030` | drop | True **WRONG** | True | False | 5 | none | The robot arm successfully grasped the red cube, moved it to the green pad, and released it, completing the task without any visible errors. |
| `neg_splice_000013_000018` | drop | True **WRONG** | True | False | 5 | none | The robot arm successfully grasped the red cube, moved it over the green pad, and released it, with the cube resting on the pad in the final frame. |
| `neg_dup_000033` | drop | True **WRONG** | True | False | 5 | none | The robot arm successfully picked up the red cube, moved it to the green pad, and released it, completing the task without errors. |

## How each clip was made

- `pos_sim_A_000000`: untouched expert success episode
- `pos_sim_A_000005`: untouched expert success episode
- `pos_sim_A_000010`: untouched expert success episode
- `pos_sim_A_000015`: untouched expert success episode
- `pos_sim_A_000020`: untouched expert success episode
- `pos_sim_A_000025`: untouched expert success episode
- `neg_rollout_act_smoke_300_B2_0`: real failed ACT policy rollout (arm moves, never completes the task)
- `neg_trunc_000003`: first 40% (3.9s) of episode 3: cube never reaches the pad
- `neg_trunc2_000007`: first 40% (3.8s) of episode 7: cube never reaches the pad
- `neg_rev_000012`: episode 12 played backwards: cube ends at its start, off the pad
- `neg_rev2_000017`: episode 17 played backwards: cube ends at its start, off the pad
- `neg_freeze_000022`: frame 0 of episode 22 held for 8 s: nothing happens
- `neg_freeze2_000027`: frame 0 of episode 27 held for 8 s: nothing happens
- `neg_redbox_000030`: episode 30 with a 90px solid red square over the cube's start position for the first half (giant cube)
- `neg_splice_000013_000018`: first half of episode 13 + second half of episode 18: cube/arm teleport at the cut
- `neg_dup_000033`: episode 33 with a static copy of the cube pasted +70px beside it for the whole clip (duplicate cube)

## Findings

- **Positives: 9/9 kept** (v1 6/6, v2 3/3), all `task_success=true`, motion 5. No false drops.
- **Negatives: only 3/10 dropped with either prompt.** The only reliable catch is a completely static video
  (freeze, 2/2 in both versions). Short truncated clips are a coin flip (v1 caught trunc_3 and missed trunc2_7; v2 did the opposite),
  so the model is sampling "success" rather than reading the end state.
- **Fooled every time:** the real failed ACT rollout (cube never moves; Reason: "successfully grasped the red cube, moved it to
  the green pad, and released it"), both reversed episodes (cube ends off the pad; v2 even wrote "released it onto the
  table surface" and still set `task_success=true`), and all 3 visual defects (`visual_defect` 0/3 in both versions: a 90 px
  solid red square, a duplicated cube, a mid-clip splice/teleport).
- **Prompt v2** (explicit last-frame check + list of physically impossible events) did not help: false keeps 7 to 7, kappa 0.24 to 0.17.
- **Conclusion:** as a filter, `keep iff task_success and not visual_defect and motion_quality >= 3` passes almost anything that
  shows an arm moving near a cube. It is not trustworthy for removing failed or hallucinated episodes. Use the sim success flag
  (cube pose on pad) as ground truth for sim and Cosmos-B (inherits the source episode label), and keep Reason output as
  an annotation and a "static/no-motion" detector only.
