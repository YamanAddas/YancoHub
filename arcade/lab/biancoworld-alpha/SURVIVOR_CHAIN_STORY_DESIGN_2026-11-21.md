# BiancoWorld — Survivor Chain, Infection & Endings
Date: 2026-11-21
Status: STORY DESIGN — OWNER-APPROVED CORE; OPEN BALANCE QUESTIONS REMAIN
Implementation status: NOT CODED. Do not implement mechanics before the owner finishes planning.

## Canon (explicit user decisions)

**Genre and premise.** A zombie outbreak starts in a laboratory. The player survives, finds separated scientists, rescues survivors, and eventually assembles a cure that restores infected humans. No killing: use stun, knockout, electric pulse tools, stealth and escape. Zombies are people capable of being cured.

**Civilian rescue roster.** Whenever the player finds and rescues a civilian survivor, the survivor joins the player's team/roster. They are not physically drawn walking behind the player during ordinary gameplay. They are treated as accompanying/available in the party, represented as a reserve roster. The team exists to let the story continue through successive playable people.

**Scientist separation (owner decision, 2026-11-21).** Rescued scientists are **mission-critical research specialists**, not playable characters and not extra lives. They remain at the research base and advance the cure narrative / unlock research as missions are completed. Ordinary civilian survivors alone increase the reserve playable roster. The fate and danger mechanics for scientists are still an open design problem, but random scientist loss must never silently make the cure impossible; do not assume scientists are invulnerable without a separate design decision.

**Playable character switching.** A single survivor is controlled at any given time. If infection fully transforms that person into a zombie, the person permanently leaves the playable roster for the remainder of the main story. Control passes to the next survivor in the roster. The transformed former player becomes an ordinary threat in the zombie-populated world; the player might encounter them and need to evade, stun or otherwise avoid them. No playable-character reconversion before the final cure. Reserve members remain unseen during ordinary movement, except when brought into play; this is a performance/UX choice, not a claim that they have literally disappeared in-world.

**Fail condition.** If the final remaining playable survivor transforms and there is nobody left to take over, the **sad/failed ending** occurs: the outbreak wins, humanity/the game world is overwhelmed. Do not spawn a free replacement survivor, silently rewind to checkpoint, or automatically grant a rescue. The risk of permanent roster loss is deliberate. Game-over treatment, retry/new-game mechanics and save rules are still open design questions.

**Win condition.** Reach scientists, finish their missions, develop and deploy a final cure. The **happy ending** restores infected people, including every earlier playable survivor who was lost. The surviving final protagonist meets the restored previous protagonists in a meaningful reunion, with expressions of thanks or gratitude (owner's image: "Thank you, you helped us"). End on a group portrait / photograph featuring the actual encountered playable characters and survivors. The identities and accumulated history are the emotional payoff.

**Non-lethal mechanics established in discussion.** Electrical pulse pistol, shotgun-like spread pulse, and long-range concentrated pulse, all fictional; effectiveness scales from slowdown to stun to knockout based on hit strength and zombie resistance. Knockout is temporary. Escape and stealth viable. Player infection progresses on a spectrum, with access to stabilizers/temporary treatments before full conversion. The player should remain able to run/escape even at severe pre-conversion infection; no unavoidable long stunlocks. All exact thresholds remain unverified proposals, not locked balance.

## Narrative structure

Prologue: a lab incident initiates outbreak; starting survivor escapes.
Act I: survive, discover the threat, rescue first survivors.
Act II: travel between dangerous districts, locate and rescue scientists; uncover pieces of cure research. Each rescue offers meaningful progress or new capabilities.
Act III: unite scientists at a research site; gather key research components, samples and energy sources without killing infected people.
Finale: deploy cure before the last playable survivor is lost; transition from outbreak to recovered society.
Success epilogue: a reunion of all earlier lost player protagonists and the surviving active character, then a personalized group photograph.
Failure epilogue: last survivor becomes infected; no one remains to finish deployment. The city/world succumbs; clear sad ending (not a fake victory or hidden checkpoint retry).

## Design implications / unresolved decisions

1. **Roster scarcity and player agency:** early rescue availability, minimum starting roster size and rescue mission visibility must make success challenging but attainable. Rescue should be the primary way to gain chances.
2. **Fair infection pressure:** each exposure has clear cause and counterplay; protect against repeated unavoidable hits; keep full movement/escape capacity before conversion. Suggested state stages are prototypes only.
3. **Carry-over:** story progress, opened neighborhoods, scientist work and key research should survive a switch. Exactly what personal gear, individual skills, vehicles and upgrades persist is open.
4. **Scientists:** DECIDED — they are separate mission-critical specialists at the research base, **not playable reserves**, and rescuing them does not grant an extra life. Still open: story-consistent ways they can be in danger without creating an unannounced unwinnable softlock.
5. **Missing-character presence:** decide whether transformed former protagonists should be trackable/persistent specific zombies (as opposed to a visual lookalike random encounter). Protect their identity data for the reunion.
6. **Save integrity:** choose between ironman/autosave, generous retry-on-new-run, difficulty modes, and accessibility without undermining the meaningful roster fail state. No decision yet.
7. **World-scale cure:** a story end sequence can show a global recovery, but delivery mechanism and final gameplay challenge remain to be designed.
8. **Group photo:** cinematic composition must reflect the roster/persona identities from the actual run, not generic unrelated characters. What happens with survivors found but never played is TBD.
9. **Failing without cheapness:** ensure late-game rescue routes remain possible and surviving scientist capacity is well understood; use warnings/risks rather than unpredictable instant conversion.

## Acceptance questions for future design review

- Do rescued survivors join an ordered queue automatically, or can the player select the next character after a conversion?
- DECIDED: scientists are mission specialists outside the playable roster. Determine how scientific work progresses and what happens if their base is threatened.
- How do item inventory and upgrades transfer to a new playable survivor?
- What is the save/retry model after the bad ending?
- Is the final group portrait only previously playable lost people plus the last hero, or all rescued survivors?

## Status and boundaries

This document captures the owner's choices and explicitly separates approved canon from new proposals. It is *planning only* and must not be confused with gameplay implementation, measured balance, or experiments in YancoSI. Bianco's real-life appearance and habits must not be invented or published via private photographs.
