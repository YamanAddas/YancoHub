# YancoHub — Visual Design Reference

## Design Philosophy

YancoHub should feel like a **AAA game main menu**, not a utility app. Every screen should make the user feel like they're entering a premium experience. The aesthetic is dark, cinematic, and slightly futuristic — inspired by sci-fi game UIs (Mass Effect, Cyberpunk), not flat Material Design or generic web apps.

**Key principles:**
- **Depth over flatness** — layers of glass, light, and shadow create dimensionality
- **Glow over borders** — use teal glow/emission instead of hard outlines
- **Motion over static** — subtle animations everywhere (breathing, drifting, twinkling)
- **Restraint over excess** — effects should enhance, not overwhelm

## Color System

```css
:root {
    /* Core palette — NEVER hardcode, always reference variables */
    --bg:           #060b14;    /* Deep navy-black */
    --bg-surface:   #0c1628;    /* Card/panel backgrounds */
    --bg-elevated:  #111e36;    /* Elevated surfaces (modals, dropdowns) */

    --accent:       #00e5c1;    /* YancoHub teal — THE brand color */
    --accent-dim:   #00b89a;    /* Subtler teal for secondary elements */
    --accent-glow:  rgba(0, 229, 193, 0.15);  /* Glow halos */

    --text:         #8a9bb0;    /* Body text — muted blue-gray */
    --text-bright:  #c8d6e5;    /* Headings, important text */
    --text-dim:     #4a5a6e;    /* Tertiary text, placeholders */

    --success:      #00d97e;    /* Connected, installed, ready */
    --danger:       #ff4757;    /* Errors, disconnected */
    --warning:      #ffc107;    /* Caution states */
}
```

### Usage Rules

- **Background layers:** `--bg` → `--bg-surface` → `--bg-elevated` (each layer lighter)
- **Text hierarchy:** `--text-bright` for titles, `--text` for body, `--text-dim` for labels
- **Accent:** Use `--accent` sparingly — active states, focused elements, important CTAs
- **Glow:** `--accent-glow` for box-shadow halos, never solid accent backgrounds
- **Never** use pure white (#fff) or pure black (#000) — they break the atmospheric feel

## Typography

```css
font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
```

| Element | Size | Weight | Color |
|---------|------|--------|-------|
| App title / Logo | 24-28px | 700 | --text-bright |
| Section heading | 16-18px | 600 | --text-bright |
| Game title (carousel) | 18-20px | 600 | --text-bright |
| Body text | 13-14px | 400 | --text |
| Labels / captions | 11-12px | 400 | --text-dim |
| Badges | 10-11px | 500 | varies |

- Use `letter-spacing: 0.5px` on uppercase labels
- Use `letter-spacing: -0.02em` on large headings for tightness

## Effects Library

### Glassmorphism
```css
.glass-panel {
    background: rgba(12, 22, 40, 0.85);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    border: 1px solid rgba(0, 229, 193, 0.08);
    border-radius: 12px;
}
```

### Glow / Emission
```css
.glow-accent {
    box-shadow:
        0 0 15px rgba(0, 229, 193, 0.15),
        0 0 30px rgba(0, 229, 193, 0.05);
}

.glow-accent-strong {
    box-shadow:
        0 0 20px rgba(0, 229, 193, 0.25),
        0 0 40px rgba(0, 229, 193, 0.10),
        inset 0 0 20px rgba(0, 229, 193, 0.05);
}
```

### Breathing Animation
```css
@keyframes breathe {
    0%, 100% { opacity: 0.6; }
    50% { opacity: 1; }
}

.breathing {
    animation: breathe 3s ease-in-out infinite;
}
```

### Hex Card Clip Path
```css
.hex-card {
    clip-path: polygon(
        50% 0%,
        100% var(--hex-point),
        100% calc(100% - var(--hex-point)),
        50% 100%,
        0% calc(100% - var(--hex-point)),
        0% var(--hex-point)
    );
}
```

## Component Patterns

### Buttons
- **Primary:** Teal border, transparent fill, teal text. On hover: subtle glow + fill at 10% opacity.
- **Secondary:** No border, dim text. On hover: text brightens.
- **Danger:** Red border/text variant of primary.
- **Never** use solid-fill buttons — they look cheap against the dark aesthetic.

```css
.btn-primary {
    background: transparent;
    border: 1px solid var(--accent);
    color: var(--accent);
    padding: 8px 16px;
    border-radius: 6px;
    transition: all 0.2s ease;
}
.btn-primary:hover {
    background: var(--accent-glow);
    box-shadow: 0 0 12px rgba(0, 229, 193, 0.2);
}
```

### Inputs
- Dark fill (`--bg-surface`), subtle border (`rgba(255,255,255,0.06)`)
- On focus: teal border, subtle glow
- Placeholder text uses `--text-dim`

### Badges / Tags
- Small, rounded, semi-transparent background
- Source badges use per-source colors from `SYS_COLORS`
- Status dots: 8px circles, solid color (green/red/gray)

### Overlays / Modals
- Full-screen dark backdrop (`rgba(0, 0, 0, 0.7)`)
- Content panel uses glassmorphism
- Animate in with scale(0.95) → scale(1) + opacity

### Scrollbars
```css
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb {
    background: rgba(0, 229, 193, 0.2);
    border-radius: 3px;
}
::-webkit-scrollbar-thumb:hover {
    background: rgba(0, 229, 193, 0.4);
}
```

## 3D Carousel Specifications

The hexagonal crystal carousel is the centerpiece. These values are tuned and should not be changed without explicit request:

```
Container:      perspective: 900px
Center card:    translateX(0) translateZ(60px) rotateY(0) scale(1)
Side cards:     rotateY(±35deg), progressive translateX/translateZ/scale
Visible range:  4 cards per side (VISIBLE_HALF = 4)
Card size:      180px × 320px (--card-width, --card-height)
Transition:     transform 0.5s cubic-bezier(0.25, 0.1, 0.25, 1), opacity 0.5s
```

### Card Anatomy (inside to outside)
1. **Inner art area** — rectangular, clipped by hex parent
2. **Hex body** — crystal glass fill with slight gradient
3. **Hex border** — thin, semi-transparent edge (bevel effect)
4. **Glass highlight** — top gradient simulating light refraction
5. **Depth shadow** — inner shadow for recessed feel
6. **Surface reflection** — animated sweep across the surface
7. **Outer glow** — teal emission halo on center card

## Per-System Colors

Retro game cards use system-specific color gradients when no artwork is available:

```javascript
const SYS_COLORS = {
    snes:         ['#3b1f7e', '#1a0d3d'],   // Purple
    nes:          ['#8b1a1a', '#3d0d0d'],   // Deep red
    megadrive:    ['#1a3a6b', '#0a1a35'],   // Blue
    gba:          ['#2d1b5e', '#140d2e'],   // Indigo
    psx:          ['#2a2a3a', '#0d0d1a'],   // Cool gray
    n64:          ['#1a4a1a', '#0a250a'],   // Forest green
    // ... etc
    steam:        ['#1a2a3a', '#0a1520'],   // Steam blue-gray
    epic:         ['#2d1b69', '#1a1a2e'],   // Epic purple
    gog:          ['#4a1942', '#1a1a2e'],   // GOG magenta
    xbox:         ['#107c10', '#0e3d0e'],   // Xbox green
};
```

## Animation Timing

- **Navigation:** 0.5s cubic-bezier(0.25, 0.1, 0.25, 1) — smooth with slight ease-out
- **Overlays:** 0.3s ease-out — snappy open, gentle close
- **Hover states:** 0.2s ease — quick response
- **Background effects:** 3-8s — slow, ambient, non-distracting
- **Boot sequence:** 0.4-0.6s per phase — deliberate, cinematic pacing
- **Never** use linear timing for UI transitions — always ease

## Responsive Considerations

YancoHub runs in pywebview, not a browser, so responsive breakpoints aren't critical. However:
- Minimum comfortable resolution: 1280×720
- Optimal: 1920×1080
- Card sizes and carousel math assume 1080p+
- Settings overlay should scroll gracefully on smaller viewports

## Visual Anti-Patterns (What NOT To Do)

- ❌ Solid-color backgrounds on interactive elements
- ❌ Hard 1px borders without glow/gradient
- ❌ White text on dark backgrounds (use the grayed palette)
- ❌ Rounded corners > 16px (feels bubbly, not cinematic)
- ❌ Drop shadows pointing downward (we use glow, not shadows)
- ❌ System font fallback without attempting Inter first
- ❌ Flat iconography — prefer emoji or custom glyphs that fit the theme
- ❌ Dense data tables — use cards, badges, and spatial layout
- ❌ Sudden transitions (anything < 0.15s feels jarring)
