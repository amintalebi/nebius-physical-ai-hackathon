# What we built today (in plain language)

**Goal:** teach a small robot arm (SO-101) to pick up a blue cube and put it on a target square, using mostly
*simulated* practice plus a few real demonstrations. Judges score how often it succeeds, and how well we used NVIDIA
Cosmos and Nebius Cloud along the way.

## The idea in one paragraph
Teaching a robot by hand is slow: every example needs a person to steer it. So we let a **simulator** produce hundreds of
perfect examples for free, used **NVIDIA Cosmos** to make those simulated videos look more like the real room, and then
added a few dozen **real examples** recorded with a second "leader" arm. A learning program (**ACT**) watches all these
examples and learns to copy them: camera image in, arm movement out.

## What happened, step by step
1. **Rented one big GPU computer on Nebius** (an RTX PRO 6000). It ran everything: the simulator, Cosmos, and all training.
   Files and results were stored in Nebius Object Storage.
2. **Simulator practice.** In NVIDIA Isaac Sim, a scripted "perfect robot" picked up cubes on a 3×3 grid of spots, in two
   cube sizes (30 and 40 mm). We collected about 180 practice runs. We had to fix two things on the way: a software
   update that broke the simulator, and cube spots that all used the same random settings.
3. **First robot brain, tested in the simulator.** Trained only on simulator practice, it succeeded in about 6 out of 10
   simulated tries, even with a smaller cube it had never seen.
4. **Cosmos Transfer (making sim look real).** Cosmos repainted simulator videos to look like a real lab: white table,
   real lighting. It keeps the robot's motion exactly the same. Its weak spot: it sometimes invents extra objects.
5. **Cosmos Reason (an AI reviewer).** Another Cosmos model watched every practice video and said "good" or "bad". We
   tested how trustworthy it is with videos we deliberately broke: it called most bad videos good, so we used it as a
   second opinion and checked the real recordings ourselves.
6. **Real robot.** We read the arm's existing settings instead of resetting them, fixed the leader arm's settings, and
   recorded **48 real demonstrations** with two cameras (front and side). We threw away 3 bad ones.
7. **Training in rounds.** Each time more real demonstrations came in, we updated the robot brain and saved it as a new
   version (v01 … v07). **Version 6 picked up the cube and placed it correctly on the real robot**, sometimes after a
   second or third try.

## What we learned
- Simulation teaches the motion well, but the **real camera was in a different place** than the simulated one, and the
  real table looks different. That gap is why real demonstrations made the biggest difference.
- Cosmos can change how things *look*, but not *where the camera is*. The next step would be to move the simulated camera
  to match the real one and repaint the simulated table, then practise again.

## Where everything is
- Submission (everything for the judges): Nebius bucket `s2t-group02-a66c17`, folder `submission/`; the overview page is
  `README.md` there.
- Code and notes: GitHub `amintalebi/nebius-physical-ai-hackathon`.
- Real recordings to share: `real_demos_2026-10-18.zip`.
