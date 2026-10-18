# Roadmap

Read in this order. Every stage file has the same six parts: **Points**, **Inputs**, **Commands**,
**Time box**, **Acceptance check** (confirmed by the arm, a metric, a script or the organizers, not
by our own impression), and **If it fails**.

| # | File | One-line purpose |
|---|---|---|
| 00 | [scoring-map](00-scoring-map.md) | Every rubric point → the file that proves it |
| 01 | [critical-path](01-critical-path.md) | Hour-by-hour plan; end-to-end smoke test in the first 2 h |
| 02 | [station-sim-alignment](02-station-sim-alignment.md) | Units, camera, grid: make sim describe *our* table |
| 03 | [sim-data](03-sim-data.md) | Scripted demos spread evenly over the 9 spots |
| 04 | [cosmos-transfer](04-cosmos-transfer.md) | Edge-controlled re-render toward our station, measured |
| 05 | [cosmos-reason-curation](05-cosmos-reason-curation.md) | Score every episode, one stated rule, validated against hand labels |
| 06 | [teleop-protocol](06-teleop-protocol.md) | ≤50 real demos that cover the spots and match the judged start |
| 07 | [dataset-manifest](07-dataset-manifest.md) | Mix sizes, controlled ablation, the order of operations |
| 08 | [training-nebius](08-training-nebius.md) | Main + ablation on Nebius, identical except data |
| 09 | [eval-protocol](09-eval-protocol.md) | Blind 9-spot trials, failure labels, checkpoint choice |
| 10 | [ensemble](10-ensemble.md) | Checkpoint rotation + Cosmos Reason verifier inside the 2-min cap |
| 11 | [submission](11-submission.md) | Object Storage layout and the cutoff checklist |
| — | [open-questions](open-questions.md) | Rules to confirm with organizers, first thing |

Background: [`../sources.md`](../sources.md) lists every upstream repo we read and the eight findings
that changed this plan. The most important one is **finding 1**: sim and real joint units differ.
