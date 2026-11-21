# NEON DISTRICT — The Living City Seed
Date: 2026-11-21
Status: DESIGN / NOT AN IMPLEMENTED AI SYSTEM
Owner feedback: V2 had promising presentation but difficult steering; V3 Flow Drive made control worse. Do not push untested control rewrites to the live URL.

## What changed today

- Restored manual-control V2 at \`arcade/neon-district-v2.html\`.
- Archived the Flow Drive V3 at \`arcade/archive/neon-district-flow-v3.html\`.
- Next experiments must run under distinct URLs. Do not overwrite the game based solely on automated browser checks.
- Treat a real player's discomfort with controls as an acceptance-test failure even if input simulation passes.

## Core game idea

Make a small **living city that reacts and adapts**, not a miniature GTA imitation.

The player should be able to drive or walk, help or ignore inhabitants, discover city routines, change them by acting, and return later to see consequences. A living city is a gameplay goal, not a claim of consciousness, AGI, or scientific emergence.

The fun loop is:
**Notice something unusual → choose an intervention → observe a consequence → revisit → discover a changed relationship.**

Prototype scenario: One street intersection contains two residents, vehicles, a signal, an intermittent repair truck, and a delivery shop. A resident's route crosses the intersection. Traffic and timing change. The player can act (block traffic, press a crossing button, provide a bicycle, distract someone). Over repeated encounters, the resident may change its route strategy and remember what worked. That change must be observable, reproducible, and optionally reversible.

The rest of the city can be conventional game simulation until this single block is convincingly fun.

## What can be borrowed from YancoSI / Yaman Society

Relevant *research principles*, not a transfer of an already-proven general intelligence:

1. **Experiential loop:** observe state → propose a small predictive rule → choose an informative action → compare the outcome → revise → reuse. One rule must demonstrably affect future behavior.
2. **Readable knowledge:** each resident has few inspectable beliefs with confidence and explicit falsifying events. Show player's observations in plain words in a "City Journal" but keep the underlying simulation private from the agent.
3. **Causality:** predictive association alone does not prove that an action caused an outcome. Introduce interventions and matched controls before claiming learning.
4. **Learning progress, not random surprise:** curiosity should attend to things that can be learned, avoiding endless fascination with noise.
5. **Agents with boundaries:** individual positions, needs/resources, sensors, actions, and memories; no shared omniscient state. Later test cooperation and culture with multiple inhabitants.
6. **Reproducible evidence:** fixed seeds, deterministic replay, identical initial conditions, baseline agents, matched sensor history, withheld evaluation episodes, and visible limitations.
7. **Honesty:** Stage-1 counted PASS reported in the lab is limited evidence on particular mechanisms; it is not proof that Yaman Society, minds, social intelligence, autonomous language, or general reasoning exist.

The game's stable NPC layer must not depend on experimental YancoSI code. Experimental learner runs as an opt-in "research brain" behind a swappable interface. If it fails, the town should remain playable.

## Player experience (mobile first)

- **Control first.** No compelled auto-cruise or automatic right-angle turning. Restore the V2 control until real users choose otherwise.
- **Separate control playground.** A 30–60 second flat test course, never in the main world. Offer three candidate controls to compare against the V2 baseline:
  A: V2 thumbstick + held throttle/brake;
  B: large left/right steering zone + held throttle/brake, with speed-dependent steering attenuation;
  C: on-screen wheel/drag-to-steer + held throttle/brake.
  Do not silently change acceleration, camera, damage, and steering together: isolate variables.
- **Comfort guardrails.** Fixed minimum readable zoom; visible road orientation; predictable camera; no extra screen shake while measuring control; wide crossings; clean collisions; reasonable reverse recovery; accessible restart.
- **Player choice beats algorithm.** The selected control mode is remembered locally; reset is always possible. Subjective fun, comprehension, and fatigue are acceptance gates.
- **Natural mission difficulty.** Early goal is near and clearly visible; no police during the tutorial. Later, the world changes through events rather than escalating punishment.
- **No account, cloud model or metered API required.** Prefer offline-capable static client code with local persistent saves.

## Phase 0 — Stop making steering worse

Implementation: independent \`arcade/lab/drive-feel.html\`, no deployment replacing the public main game.

Measure for each input mode:
- time to finish a short identical route,
- collisions and successful turns,
- time spent stuck (velocity ~0 when throttle held),
- resets or switches,
- visible control state,
- 1-tap player vote: comfortable / frustrating.

Two fair trial layouts, same road geometry and target speeds. Keep a log only in localStorage, exportable by the player. Do not quietly upload telemetry or location.

**Gate:** do not promote any control mode that players consider worse than V2, even if computer-simulated lap time is shorter. Only change one variable per A/B run.

## Phase 1 — One living intersection

Start with **two NPCs**, not eight. Each NPC has a tiny state:
- sensed signal, near-traffic, location, and remembered outcomes;
- action: wait, cross, route around, signal, interact;
- predicted result under chosen action;
- per-action costs and resource constraints;
- explicit memory of successes, misses, and reversals.

Three comparators:
- B0: fixed scripted NPC;
- B1: trial-and-error NPC with compact per-state action-values;
- B2: B1 but history shuffled or memory disabled, same action budget and initialization.

Randomize multiple worlds (signal schedule, traffic probabilities, road closures), reserve unseen scenarios. Claim *local adaptation* only if B1 improves on withheld evaluations over B0/B2 and visibly alters its policy. If results fail or are ambiguous, leave NPC scripted and record the failure.

**Gate:** the player can notice, trigger, and understand a change in one NPC's behavior, and the simulation remains performant on a midrange mobile phone.

## Phase 2 — Social routines

Add two more NPCs (total four), one resource and one shared space. Permit communication or observation as a test, not as an assumed intelligence. Compare with signal-disabled and memory-shuffled controls. Require observable transfer before using the term "culture."

Only if this is both fun and measurable, try the eight-founder society. Do not copy locked YancoSI counted runs into a game project, alter lab evidence, or claim general intelligence from the game.

## Engineering boundaries

- Game simulation and experimental learning modules are separate; a model crash cannot break rendering or controls.
- Main loop should not block on model inference. Enforce a per-frame compute budget and allow slower background tick cadence inside the page (not an external autonomous service).
- Use pre-registered diagnostic seeds, immutable result snapshots, and opt-in debug overlays.
- Public build exposes no private lab files, credentials, agent prompts, or sensitive data.
- Do not conflate player enjoyment testing with scientific validation. They answer different questions.

## Order of work

1. Keep V2 stable and playable.
2. Build and test the isolated control playground; let the player choose a mode.
3. Add the tiny living intersection in a separate playable prototype.
4. Evaluate the NPC with controls, then make it a world feature only if it adds play value.
5. Expand the city incrementally; use YancoSI as research inspiration and test discipline, not a magic AI label.

## Known limitations

Yaman Society's newest Windows-only experiment folder was not reachable in this work session. This design uses previously reviewed research notes from the private YancoSI GitHub repository and known recent Stage-1 reports. Reinspect the locked Windows evidence before making any claims about a specific new mechanism or integrating research code.
