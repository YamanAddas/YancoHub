# NEON DISTRICT — Living City Execution Plan v0.1
Date: 2026-11-21
Status: PLANNING COMPLETE; EXPERIMENTAL IMPLEMENTATION NOT YET STARTED
Owner intent: an enjoyable mobile game whose small world eventually shows observable, persistent, evidence-backed adaptation; use YancoSI / Yaman Society research for experimental discipline, not as a claim that we have built intelligence.

## القرار بالعربي
اللعبة أولاً: قيادة ممتعة قبل أي ذكاء تجريبي. بعدين نعمل حارة صغيرة فيها شخصيات بتتفاعل مع الظروف وبتراجع توقعاتها. ما مننقل أي تعديل للنسخة العامة إلا بعد اختبار فعلي على الهاتف وموافقة اللاعب. ما منخلط بين قصة مكتوبة سلفاً وبين تعلّم حقيقي قابل للقياس.

## 0. Current baseline and constraints

- **Production**: `arcade/neon-district-v2.html` is the last tolerable baseline, not a control-design gold standard.
- **Archived rejected control**: `arcade/archive/neon-district-flow-v3.html` contains the failed compulsory auto-drive and queued-turn experiment. Preserve it as negative evidence; do not re-introduce its behavior by default.
- **Prior seed concept**: `arcade/NEON_LIVING_CITY_SEED_PLAN_2026-11-21.md`.
- The player expressly disliked V3 controls. Computer simulation success is insufficient.
- Mobile-first, one-tap public HTTPS prototype, no install, no paid inference API, no account, offline-capable after first load where practicable.
- The main game stays stable while experiments run at distinct URLs.
- Never copy private YancoSI datasets, code, prompts, or results into this public repository.
- Current YancoSI repository documents reviewed: `research/mind_lab/YAMAN_SOCIETY_IDEA_MAP_2026-11-14.md` and `research/mind_lab/REVIEW_YAMAN_SOCIETY_FEASIBILITY_2026-11-14.md`. The newer locked Windows experiment folder was **not inspected in this planning pass**. Do not claim that the full society exists, that a mind emerged, or that any specific late-stage experimental result has been independently verified.

## 1. Product thesis and player experience

**One-sentence promise:** A small neighborhood where what you do today can change what people do tomorrow, and those changes make sense.

The minimum interesting loop is:
1. Notice a recurring event (an impatient courier crossing a busy junction).
2. Make a meaningful choice (activate a crossing signal, wait to help, obstruct a lane, or do nothing).
3. Watch what happened (crossed safely, waited too long, chose another route).
4. Return to the junction and notice a changed behavior.
5. Inspect an optional readable **City Journal** showing what the resident expects and what evidence changed it.

**Critical distinction**: A journal that merely narrates scripted states is not learning. A genuine experimental learner needs state, local observations, a policy changed by experience, withheld scenarios, and a fair comparison against controls. The game may always use scripted NPCs where that is more enjoyable.

### Play promises, not scientific claims
- Driving and exploration are immediately pleasant even with NPC learning disabled.
- Consequences are discoverable without reading debug panels.
- The player is free to ignore research mechanics.
- No forced quests or police chase during the opening experience.
- No paywall, sign-in, telemetry upload, or cloud dependency for the prototype.
- The first working area is a compact, deliberately authored neighborhood, not a promise of a whole GTA-sized city.

## 2. Architecture boundary

```
Player touch / keyboard
       ↓
Input adapter (one explicit control mode)
       ↓
Deterministic driving physics and collision engine
       ↓
Game world state (time, signals, traffic, resident location, resources)
       ├── renderer + UI + save/load + City Journal
       └── agent interface: observe → choose action → update from outcome
                                 ├── Scripted resident (B0)
                                 ├── Experience learner (B1)
                                 └── Memory-disabled/shuffled control (B2)
```

Design rules:
- Decouple rendered pixels from simulation state; keep agent state visible only via sensors, not omniscient full-world access.
- Render at normal animation speed; agent decisions can occur on a slower fixed simulation cadence.
- No agent computation may block a frame; enforce a hard per-tick budget and degrade to scripted behavior on failure.
- Use seeded PRNG for world schedules, traffic and agent experiments. Capture seed and version with reproducible trace.
- Persist player settings and progress locally; expose an explicit reset.
- Do not introduce a second central knowledge database. Each NPC owns a bounded memory and a transparent state; a game-level save file is not shared omniscience.
- No external model needed initially. Small tabular predictive models are more testable and much cheaper than an LLM for this first question.

## 3. Milestone M0: Play-feel laboratory (first implementation)

**Build**: `arcade/lab/drive-feel.html` — a separate 30–60-second course with two bends, a left and right turn, and a recovery section. No police, missions, damage, NPC experiments, or procedural distractions.

Test **one axis at a time**. Lock road, zoom, camera, acceleration, collision and target speed across the input comparison.

Modes:
- A — unchanged V2 thumbstick + held GAS/BRAKE (reference).
- B — large LEFT / RIGHT touch zones + GAS/BRAKE (no auto cruise; steering response smoothed).
- C — analog drag-to-steer / thumb wheel + GAS/BRAKE (no auto-turn at intersections).

Follow-up physics experiments are independent from A/B/C:
- softer low-speed steering, speed-limited steering sensitivity, stable camera damping, gentler curb bounce, predictable reverse.
- **Never** silently enable auto-driving or automatically execute a queued intersection turn.

Local test record (download/export only, with a visible player opt-in):
- mode, trial seed, completion time, turn misses, collisions, stuck duration, reset count, device viewport, one-tap comfortable/frustrating verdict.
- No network telemetry and no location collection.

Acceptance gate M0:
1. Same reproducible course, all controls render and respond on real Safari/iPhone (not only desktop emulation).
2. Player prefers a candidate to V2, or explicitly asks to keep V2. A numerical speed improvement alone **never** overrides player rejection.
3. Restart and mode switch available within one tap. Manual throttle/brake always possible.
4. No unhandled errors; tested portrait and landscape.
5. Only after these gates, promote the selected control into production.

**Decision owner**: the player, not a synthetic benchmark.

## 4. Milestone M1: One living intersection (independent prototype)

**Build**: `arcade/lab/living-block.html` plus pure simulation modules (e.g., `arcade/lab/engine/*.js`). First iteration uses a fixed rendered junction, two residents, one crossing signal, traffic, a shop, and one alternate path.

Opening scene:
- A courier repeats a route past a junction.
- A second resident occasionally changes traffic timing by requesting a crossing.
- The player can activate the signal, block a lane, help carry an item, or observe.
- The courier remembers outcomes and may change its decision to wait, cross, or detour.
- The player can come back after a few simulated days, then choose a different intervention.

Give each resident:
- **Senses**: signal state, distance band of nearest vehicle, current destination, local route condition, previous result.
- **Actions**: wait, cross, use alternate route, request assistance.
- **World law**: transit time, collision risk, and effort costs are consistent and learnable.
- **Memory**: bounded counts of (observed state, attempted action, outcome), not omniscient rules.
- **Prediction**: expected safe crossing and delay for each candidate action.
- **Update**: only after observing the actual consequence; record counterexamples and confidence.
- **Policy**: pick actions by an explicit utility (safety/effort/time) plus bounded exploration. A sensible scripted safety policy is the baseline.

The first learner can be a small empirical state-action outcome table; no model weights or self-aware narrative. Behaviors must change by observed outcomes, not hidden if/else flags keyed to the player's actions.

**Player-facing visualization**: optional 3-row City Journal:
- "I expected waiting to be safer when cars were near."
- "Last time I tried to cross and had to stop."
- "Now I'm choosing the side street more often."
Every journal sentence must be derived from a real agent record; no fabricated introspection.

Acceptance gate M1:
1. Player can observe cause/event/changed behavior in a 2–4 minute demo.
2. At least one resident's future action depends on memory; swapping/removing its memory removes that dependence in a matched replay.
3. Behavior is not merely a scripted cutscene.
4. A crash or bad agent output never breaks player controls or rendering.
5. No major lag on target phone; log FPS and simulation tick budget.

## 5. Milestone M2: Evidence before intelligence claims

**Scientific question:** Does a bounded resident adapt to changing local rules and generalize beyond the exact events it encountered?

Test arms in the same seeded worlds:
- B0 scripted resident; safety-competent and given the same sensor interface.
- B1 resident with event memory and update mechanism.
- B2 same learner with shuffled or disabled memory (and matched compute and observation budget).

World variants: traffic arrival distribution, signal delay, alternate route closures, different interventions. Separate developmental/training episodes from a frozen set of withheld evaluation episodes. Reserve multiple seeds *before* evaluation; choose count and decision threshold from a pilot and pre-register them, not after inspecting results.

Primary outcomes: safe arrival rate and median travel time over matched evaluation worlds. Secondary: wrong decisions, collisions, action changes, time stuck, compute/tick, memory size, and whether a falsified belief is revised.

Guard against illusions:
- Inspect an event trace: observation → prediction → action → outcome → revision → future action.
- Compare with shuffled memory.
- Test a law reversal to verify relearning, not just memorization.
- Compare against a competent rule-based baseline; outperforming a deliberately stupid NPC proves little.
- Repeat with withheld worlds and matched compute; never claim emergence from one compelling anecdote.

**M2 GO** only if the learner produces interpretable, reproducible behavioral adaptation under controlled conditions **and** remains fun as a game mechanic. A null result is not a bug to conceal.

## 6. Milestone M3: Social texture before a society

Only after M1/M2:
- Add two more residents (total four), distinct routines, one shared resource, optional observation/signaling.
- Test the same setup with communication switched off, and with another resident's observation history shuffled.
- A signal is not "language" until shown to carry grounded information and have a causal role.
- "Culture" requires demonstrated persistence/transfer, not synchronized animations.
- Eight founders, fusion, open-ended evolution, and generational growth are **deferred research hypotheses**, not a required game feature.

## 7. Distinct acceptance gates

| Track | Primary question | Evidence | Release rule |
|---|---|---|---|
| Controls | Is it fun and manageable? | actual player vote + mobile input check | Player accepts, no regression |
| Gameplay | Does the living block create interesting choices? | repeated short playtests + observed consequences | Choices feel meaningful |
| Learning | Did behavior genuinely change from experience? | held-out worlds, memory-shuffle ablation, traces | Measurable and reproducible |
| Performance | Is the phone smooth? | frame pacing + slow-device test | No major jank / stalled controls |
| Integrity | Did we preserve scientific boundaries? | tests, versioned seeds, provenance | No misleading mind claims |

## 8. Task backlog, in dependency order

| ID | Priority | Deliverable | Status |
|---|---|---|---|
| D00 | P0 | Preserve playable V2 and rejected V3, keep production URL stable | DONE |
| D01 | P0 | Implement isolated drive-feel course with baseline A and two experimental modes | TODO |
| D02 | P0 | Measure controls in local-only replay, show one-tap preference and mode switching | TODO |
| D03 | P0 | Real iPhone/Safari acceptance; promote only player-approved controls | BLOCKED ON REAL TEST |
| W01 | P1 | Build deterministic single-intersection simulation with seeded replay | TODO |
| W02 | P1 | Add scripted courier and second resident with visible routines | TODO |
| W03 | P1 | Implement agent interface + bounded resident memory + predictions + revision | TODO |
| W04 | P1 | Make City Journal evidence-backed; no made-up reasoning | TODO |
| E01 | P1 | Build B0/B1/B2 paired-seed test harness and held-out evaluation | TODO |
| E02 | P1 | Pre-register pass/fail and examine reversal/counterexample traces | TODO |
| P01 | P2 | Real phone performance and local save/load/error recovery | TODO |
| S01 | P3 | Expand to 4 agents only after validated enjoyable M1/M2 | DEFERRED |

## 9. Release discipline

- Development URLs live under `/arcade/lab/`; production remains unchanged until explicitly approved.
- Commit experiments individually. Preserve a rollback to the prior accepted version.
- Each candidate requires: source commit, direct HTTPS test link, exact changelog, synthetic-test results, and a clear "needs real phone test" label where applicable.
- Public GitHub Pages can serve standalone HTML + JS; no server or API required.
- No user-visible assertion of "tested on iPhone" unless a real iPhone test was observed.
- Never interpret the YancoSI PASS label as validation for the gameplay agent.
- If something makes driving less fun, revert immediately regardless of how elegant the architecture looks.

## 10. Immediate next build (not yet implemented)

Deliver **D01** only: a standalone mobile control playground with three modes, simple geometric track, repeat/reset, local observations and optional votes; publish a separate direct link for the player's real-device comparison.

Do **not** start NPC learning, change physics in the public game, or expand the city before D01 is accepted. This avoids repeating the V3 mistake.

## Basis and limitations

Read directly in this planning pass:
- YancoHub / `arcade/NEON_LIVING_CITY_SEED_PLAN_2026-11-21.md`
- YancoHub / `arcade/neon-district-v2.html` (confirmed V2, not Flow Drive V3)
- Private YancoSI / `research/mind_lab/YAMAN_SOCIETY_IDEA_MAP_2026-11-14.md`
- Private YancoSI / `research/mind_lab/REVIEW_YAMAN_SOCIETY_FEASIBILITY_2026-11-14.md`

This is a proposed build plan, **not** a result of new experiments or an assertion that resident learning already exists. The private YancoSI review warned explicitly against claiming open-ended intelligence on small-world results and recommended cheap decisive experiments with comparisons; this project applies that caution.
