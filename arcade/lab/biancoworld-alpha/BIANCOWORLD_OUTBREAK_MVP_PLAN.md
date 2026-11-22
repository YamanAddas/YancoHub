# BiancoWorld: Outbreak — Small Shippable Game Plan
Date: 2026-11-21
Status: DRAFT EXECUTION PLAN / FOR OWNER REVIEW — NO NEW GAMEPLAY IMPLEMENTED BY THIS DOCUMENT
Decision: Scope reset. This file takes priority over the older NEON DISTRICT living-city/YancoSI experimental plan for the **current BiancoWorld game**.

## 1. Reflection / why this scope reset

Earlier planning drifted into open-world simulation, learning agents, skills, complex branching, social systems, and extensive research benchmarks. The owner explicitly rejects that scope: this is a lightweight mobile game we can actually finish with ChatGPT and modest coding tools. The story has a mostly linear timeline. Different playable survivors should have at most small flavor/stat differences; no branching storyline or progression-gating character skills.

Existing tangible artifact:
- \`arcade/lab/biancoworld-alpha/index.html\`: standalone HTML5 Canvas, camera and top-down city, car-driving analog stick with up/throttle, down/brake, max-up boost, horizontal steering, reverse action, pedestrian walking and enter/exit. 3 generic exploration tasks. This is **not yet a zombie game**.
- \`arcade/lab/biancoworld-alpha/FLOATING_CONTROLS_SPEC_2026-11-21.md\`: planned dynamically appearing left and right thumb controls, portrait/landscape. Not yet implemented.
- \`arcade/lab/biancoworld-alpha/SURVIVOR_CHAIN_STORY_DESIGN_2026-11-21.md\`: owner-approved survivor loss, scientists separate, and emotional ending.

No independent \`YamanAddas/BiancoWorld\` GitHub repository confirmed available at planning time. Work in an isolated YancoHub path until one actually exists. Never modify the stable alpha during experiments.

## 2. Game pitch

**A compact, 2D, top-down zombie survival adventure for mobile, with a definite ending.** The outbreak begins in a lab. A succession of survivors rescues scientists and ordinary people to complete a cure. No kills; only electric stun, knockout, evasion and stealth. Rescued civilians add reserve playable lives. A transformed protagonist permanently leaves the playable roster and becomes one of the zombies. If the final survivor converts, the world is lost (sad ending). If cure deployment succeeds, infected people return and lost protagonists reunite with the last hero; final group picture reflects the actual run.

This is a **fixed story with lightweight simulated encounters**, not an open-ended AI society. The city need not stay alive while the app is closed. Do not add neural agents, actual language learning, independent NPC economies, complex skills or giant procedural worlds.

## 3. Minimal content budget — target, not a locked contract

- **One connected small city map** built from reusable existing Canvas art; 3 visually distinct zones + the lab start location. No giant 3D map or multiplatform VR.
- **Six short sequential story beats** as an initial content target, grouped into a linear timeline. Suggested:
  1. Outbreak at lab, learn move/drive/escape (low pressure).
  2. Rescue first civilian (explain reserve roster and rescue).
  3. Rescue researcher from clinic (introduce infection stabilizer).
  4. Rescue engineer at power station (restore power/upgrade pulse tool).
  5. Rescue final research scientist + recover missing sample (the base is assembled).
  6. Get cure running and deploy it; reunion or failure.
- **Three scientists** are story specialists at the lab/base, not extra playable lives. They do not need autonomous AI.
- **A small set of civilian survivors**: start with one playable hero; rescue civilians through missions and one or two optional clearly marked encounters, providing additional chances. Exact roster size to balance in playtests.
- **One basic electric pulse tool** in the first slice. A spread-pulse unlock only after play loop is fun. Long-range pulse is optional stretch scope; don't hold shipping hostage.
- **Two or three enemy behavior types** maximum: wandering, alert/chasing, stunned/knocked out. These can be states of the same zombie rather than separately animated species.
- **Two endings**, one linear story. Optional side rescue does not rewrite the timeline.
- No voice acting, complex cutscenes, inventories with dozens of resources, crafting tree, hunger/thirst, day/night ecology, police, or detailed character skills in MVP.

## 4. Core mechanics and fairness

### Controls
- Keep successful analog car physics from alpha. Implement separate floating touch anchors only after an isolated mobile test.
- Left touch: car throttle/steering/brake or pedestrian 2D movement; stick spawns where thumb lands.
- Right touch: simple context action / aiming or camera adjustment, without accidental triggering. Keep reverse reachable while driving; no extra simultaneous Boost button.
- iPhone Safari portrait + landscape, safe areas, pointerId isolation, pointercancel/blur release, optional fixed-control fallback. Test with two fingers simultaneously.
- Out of car, one stick moves; one obvious contextual button for enter/exit/rescue/use. Don't design a full console controller system.

### Zombies
- Zombies have detection radius / simple line of sight, chase timeout, and an escape condition that players understand. Faster to escape while sprinting than a permanently attached pursuit. No unavoidable spawn-hits.
- Electric pulse adds a fictional suppression meter: move slower → stun → temporary knockout. Stronger zombies require more hits. No killing mechanics.
- Stun recovers with time; a cleared map is never permanently "killed clean".
- Stealth and running should work without needing to fire; health feedback explains contact.

### Infection
- Each bite/contact increments infection with a clear UI meter and brief immunity/grace period so one encounter cannot deliver several unavoidable hits.
- Mild/late stages increase tension via **readable audio/visual warnings**, not by making the survivor unable to run or control their character. Before full transformation, escape must remain possible.
- Rare stabilizers can reduce or pause infection before 100%, but they do not convert a transformed zombie back to playable status.
- At 100%, former hero is lost until the final cure, switches to next reserve civilian; inventory/story continuity handled simply at base/checkpoint.
- Last playable survivor becoming infected: **bad ending**, no free replacement. How to restart from bad ending is a user-facing menu choice but does not undo this run's ending.

### Survivor chain and scientists
- Rescuing an ordinary civilian adds one visible roster portrait/life. No extra follower sprite for each reserve.
- On conversion, choose the next survivor using a predetermined queue by rescue order for the first MVP; no complex character selection.
- Scientists are protected at research base *after* rescue, and advance plot only. Scientists are never playable reserves. Risk during their initial rescue can still exist, but no hidden scientist death softlock.
- Cosmetic differences and optionally **one small passive stat difference** between civilians, but not enough to alter mission availability or create branching stories.
- Keep the player's lost-character identity (name/color/portrait) to build the final reunion. No need for live memory-learning agent.

### Progress and saves
- The canonical story progresses on a **small explicit finite-state mission machine**, not dynamic agent goals or a choice tree.
- Auto-save at mission transitions (localStorage) is a proposed engineering default; avoid interruptions erasing long progress. The consequences of intentional reload during an infection event must be specified before balancing; don't silently negate roster loss. Keep "New Run" explicit.
- The bad ending and good ending both display deliberately designed closure. Avoid fake "complete" from simply reaching a marker.

## 5. What the first real prototype must prove

**Vertical Slice V1** (single isolated \`/arcade/lab/biancoworld-outbreak-v1/\` URL) includes:
1. Floating left movement stick, minimal right contextual/aim control, with fixed-controls toggle as backup.
2. Car driving and enter/exit on foot from existing alpha (no regressions).
3. One compact lab/street scene, 3–5 zombies, a clear route to one trapped civilian.
4. Zombie perception, pursuing, lost sight, escape; non-lethal pulse and slowdown→stun→knockout.
5. Player infection HUD; an avoidable contact event and one stabilizer.
6. Rescue civilian, add a reserve life; optionally test conversion/switch and sad-ending state with a debug test button.
7. One mission with a beginning, objective and finish — not a generic "explore map" task.

**Acceptance / GO**:
- Player understands objective and completes a 3–7 minute slice without manual explanation.
- Walking, driving, two-thumb floating controls actually function on Safari portrait and landscape (on real device, not just Chromium emulation).
- No accidental attack or unresponsive/stuck input when fingers lift or screen rotates.
- One zombie can be escaped without using a weapon; one can be knocked out temporarily by pulse; no zombie is killed.
- A rescue genuinely increases reserve lives, and transforming switches to next; scientist rescue does *not* increase lives.
- No source code commits to older alpha or locked YancoSI evidence during slice.
- Keep CPU/frame time within comfortable mobile performance; measure on a real phone before release claims.
- If controls are not fun, fix that before expanding story content.

## 6. Implementation order, small independent steps

| Phase | Concrete output | Don't add yet |
|---|---|---|
| A — Control + on-foot loop | Floating sticks, camera/aim interaction, reliable enter/exit; playable on phone | zombie AI, NPC learning, story cutscenes |
| B — One zombie encounter | detection/chase/escape, one electric pulse, suppression meter, one bite/infection/cure item | multi-weapon arsenal, wave survival |
| C — One rescue & one switch | a civilian, reserve count, conversion to alternate hero, small event script | full cinematic ending |
| D — Fixed story content | 3 scientist rescues, 6 total beats, final cure, bad ending, personalized reunion portrait | more maps, branching plot |
| E — Polish | art/readability, audio cues, balance, simple save, portrait/landscape tests | research agents, economy, giant expansion |

**Stop rule:** no new feature if the last playable slice is confusing or broken on the owner's phone. In each step, ship an HTTPS playable URL and describe exactly what changed.

## 7. Main risks / scope controls

1. **Control complexity**: floating right thumb responsibilities are not yet player-tested; begin with move + context and add camera/aim only when needed.
2. **Character loss frustration**: permanent loss must result from visible, fair events; not from hidden exponential infection or unstoppable chain-hits. Give early civilians before hard encounters.
3. **No-weapon play viability**: electric weapon cannot become mandatory for every movement; maintain evade and distract paths.
4. **Mobile performance**: reuse simple top-down Canvas render, finite enemies, no live LLM at runtime.
5. **Narrative workload**: six beats with short dialogue balloons, no cinematic animation pipeline until the final scene is fun.
6. **Save exploits vs fairness**: define run semantics before the first full story test; avoid inconsistent last-survivor resets.
7. **Identity fidelity**: ending group shows actual playable people rescued/lost; Bianco the real cat's appearance/habits should be grounded only in owner's source, not invented or copied from private files.

## 8. Explicitly deferred, not forgotten

- YancoSI-inspired living NPC learning, Yaman Society social evolution, 8-founder society, agent communication, complex branching choices.
- Big city with procedural daily lives, skill trees, detailed crafting/loot, network multiplayer, 3D VR, advanced zombie combat classes.
- Realistic scientific modeling of a zombie virus. The game is fictional.
- Any change to the existing live alpha before an independent experiment proves better.

## Decision ledger

**Locked by user:** zombie outbreak in lab; cure all at story end; non-lethal electricity, stun/stealth/escape; infection stages without impossible pre-conversion running; civilians are reserve lives, unseen followers; transformed previous protagonist remains zombie and unplayable until finale; last survivor lost is a genuine sad ending; scientists separate from reserve; positive reunion and personalized group photo; small linear timeline, light survivor differences; finishable with modest code/time.

**Suggested, not locked:** three scientists, six missions, three-zone map, 3–7 minute slice, fixed roster queue, save rules, exact weapon stats/thresholds, number of civilians, ending animation style.

## Next action

Owner reviews this MVP scope. Then use Chat On Steroids Core or another coder to implement **Phase A in a separate branch/path**, and only after the user tests it on the iPhone proceed to Phase B. Do not start an expensive rewrite or attempt to build all six missions at once.
