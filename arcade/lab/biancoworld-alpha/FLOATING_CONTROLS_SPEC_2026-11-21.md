# BiancoWorld — Floating Two-Thumb Controls v0.1
Date: 2026-11-21
Status: ACCEPTED CONCEPT, IMPLEMENTATION NOT YET STARTED
Authoritative user feedback: mobile thumb comfort matters more than fixed on-screen buttons; the control must appear under the finger where the user chooses to touch. Support portrait and landscape.

## Scope

Replace fixed-position pads with a **dual-zone floating touch control** that spawns at the contact origin. Preserve the successful BiancoWorld analog driving physics. Do not add yet more permanent buttons.

Current prototype: \`arcade/lab/biancoworld-alpha/index.html\`.
New isolated experiment: \`arcade/lab/biancoworld-floating-controls/index.html\` (do not overwrite the alpha or production game while building).

## Touch behavior

### Left side — movement / steering
- A touch that begins inside the left control zone creates a joystick **centered at the touch-down position**, never a remote fixed bottom-left location.
- Drag displacement from that fixed touch origin controls X/Y continuously. Keep the origin fixed during that touch; only the knob moves.
- Car:
  - X: steering, smooth analog.
  - Y raised: progressively stronger throttle; maximum upward range activates Boost only if nitro is ready.
  - Y lowered: increasingly strong brake; center and deadzone should settle cleanly.
  - If reverse is armed using a separate context action, the same analog Y controls low-speed reverse.
- Pedestrian:
  - X/Y: walk freely in 2D; deflection magnitude smoothly controls walk→run, independent of heading.
  - On release: come to a stop quickly, and keep last facing direction.
- Joystick disappears gracefully on pointerup/pointercancel. No jumps when a second finger joins.

### Right side — context controls
- A touch that begins in the right control zone owns a **separate pointerId** and displays a contextual right-hand control anchored at the user's chosen touch location.
- Initial hypothesis: right thumb drag turns the camera / view, and tap triggers the single nearby contextual action; use minimal discoverable affordances for "Enter/Exit", "Talk", "Pick up", or "Use". These are a UX prototype, **not yet player-approved**.
- Avoid making an ordinary camera drag accidentally interact with people/objects. Suggested tap vs drag threshold and visual feedback; do not guess from same gesture without a threshold.
- An alternate implementation may use a thumb-anchored radial option for actions, tested separately against tap/drag. Do not force simultaneous camera rotation and interaction through one unseparated gesture.
- Driving reverse must be available without releasing the left thumb, e.g. via the right contextual control, and **only at safe low speed**.
- During initial development, provide a compact accessible help/settings affordance and preserve the ability to use the previous stable layout.

### Zone recognition and gestures
- Distinguish sides from the location where each touch *begins*, not where it drifts after activation.
- Reserve a small neutral strip near screen center (example: 4–8% width), configurable for comfort; safe areas from screen notches/edges must be honored.
- The first left-side touch controls movement; the first right-side touch controls contextual action/camera. Additional touches must not steal an existing pointer.
- UI overlays, explicit interaction targets, Pause and menus have precedence over the world control zones.
- \`pointerdown\` should immediately create a visible control, with low jitter; set pointer capture, \`touch-action: none\` inside the active game surface, and prevent browser scrolling/zoom only on active gameplay surface.
- Clear both pointers and input state on cancellation, orientation change, app blur, and visibility loss; never leave "stuck acceleration" or reverse engaged.
- Stable control origin and independent finger capture are required on both axes, not finger-following base that recenters during a stroke.

## Portrait and landscape
- Compute zones from actual viewport at runtime; recompute on \`resize\` and device orientation changes.
- On rotation, release/reset active controls and recreate on next touches (do not teleport the steering input).
- Honor CSS safe-area insets, avoid overlays over the fingers, and keep important world HUD away from the bottom thumb zones.
- Test small portrait (e.g., ~320px width), standard portrait (~390px), large landscape (~844px width), and a real Safari iPhone.
- If one side cannot physically fit a full joystick, shrink radius/reach smoothly rather than clipping the control.

## Accessibility and onboarding
- First touch should show an unobtrusive label: "MOVE / STEER" on left, "LOOK / ACT" on right.
- Finger-relative UI must have enough contrast and a clear center/deadzone ring. Retain an optional fixed-controls setting for users who prefer it.
- Do not require pressing two action buttons with the same thumb or holding Boost separately from analog accelerator.
- Display BOOST charging / active feedback, low-speed REVERSE lockout reason, and visible ride / exit action when nearby.

## Test gates (separate from gameplay simulation)
1. Pressing two fingers simultaneously creates two independent controls; neither pointer steals/moves the other.
2. Car acceleration + steering work together continuously from one analog vector; max up activates boost with remaining charge.
3. Pedestrian walks/runs in all directions and stops on release.
4. Right-hand camera drag never triggers an unintended interaction, and tap on a visible action is discoverable.
5. Reverse remains accessible without losing left thumb steering; disallowed reverse is understandable.
6. Orientation changes, Safari interruptions and pointercancel leave zero active inputs.
7. Portrait and landscape playable without thumb overstretch; controls are placed under contact point with appropriate edge clamping.
8. Performance remains comparable to alpha; no unexpected scrolling or default touch gestures during gameplay.
9. A real owner phone test must accept the feel **before** replacing the alpha controls.

## Project tooling
- Design and code handoff live in GitHub under YancoHub until a separate \`YamanAddas/BiancoWorld\` repository is created and available. The new repository **has not been created** as of this spec.
- Use Chat On Steroids Core to implement, test and commit changes in a *separate* experimental path. Do not claim the work is complete merely because the spec exists.
- Keep YancoSI / Yaman Society simulation experiments separate from control UX. No need for AI models to implement touch mechanics.

## Exact next implementation task
Create the floating-controls experiment as a self-contained touch input module with pointer state, visible overlays and a minimal car/person playground. Preserve existing driving dynamics. Publish direct GitHub Pages link. Run automated pointer tests, then get the owner's real-device verdict before merging.
