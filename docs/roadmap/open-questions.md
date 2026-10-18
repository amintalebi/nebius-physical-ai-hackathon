# Open questions for the organizers

Ask in the first 30 minutes, write the answer and who gave it next to each question, and commit.
Each one changes a decision in the plan; the "default" column is what we do without an answer.

| # | Question | Why it matters | Default if unanswered |
|---|---|---|---|
| 1 | Does each Cosmos variant of the same sim episode count as a separate episode toward the 300 cap? | Decides `--variants` (04) | Yes, it counts; 1 variant |
| 2 | Does the 50-episode real cap count episodes we recorded and deleted, or only episodes in the final dataset? | Re-recording bad takes (06) | Only the final dataset; keep the raw count ≤ 50 anyway to be safe |
| 3 | What is the exact submission cutoff time, bucket, region, and folder name? Are datasets expected in the bucket, or only checkpoints + manifest? | 11 | Upload everything in 11's layout |
| 4 | Who launches the policy in judged trials, with what command, on which machine? Can we use our laptop and `rollout.sh`? | Deployment path, device (CPU/MPS) | We launch `rollout.sh` with the main checkpoint |
| 5 | Is a retry wrapper (Cosmos Reason verifier + second attempt within the 2-min cap) allowed in judged trials? | 10 | Not used in judged trials |
| 6 | Start pose for judged trials: arm folded at rest, or any pose we choose? | 02 §2.4, 06 | Rest pose; teleop demos start there too |
| 7 | Is the cube orientation fixed at each spot or varied by judges? | Yaw range in sim and teleop | Varied, 0-45° |
| 8 | Are we allowed to add a wrist camera, or is the single mounted camera fixed? | Camera features (02) | Single mounted camera |
| 9 | Is the cube colour/size the one in the kit (30 mm, colour?) and the pad 90 mm? | `configs/station.yaml` | Measure |
| 10 | Is GROOT allowed as an ensemble member alongside ACT for the main checkpoint ("ACT or GROOT")? | 10 | ACT only for main |
| 11 | Which Nebius GPU quota do we have (H100 count, RTX PRO 6000 / L40S availability)? Do the organizers host a Cosmos reasoner endpoint? (Token Factory retired its Cosmos3 reasoner on 2026-08-31, see 05) | 01 machine plan, 04 budget, 05 | 1 RTX PRO 6000 + 2 H100; reasoner self-hosted on vLLM |
| 12 | Calibration: may we use the organizers' calibration file as-is (and copy it), and will it stay unchanged until judging? | Unit conversion depends on it | Yes; never recalibrate |
