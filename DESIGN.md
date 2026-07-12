# DESIGN.md — mebuis.com Visual Design System (Professional Services Variant)

Styling reference derived from the live homepage extraction (2026-07-09), revised
2026-07-11 to suit accounting and banking firm audiences. Structure, layout, and
component anatomy are unchanged from the original; the changes are confined to
color temperature, saturation, and effect intensity. Original values noted inline
where they were replaced.

Design intent: same dark, confident identity — but the accents move from
"startup energy" (vivid orange + electric purple) to "quiet authority"
(burnished bronze + steel indigo). Saturation drops roughly 30–40%, glow
intensity drops roughly half.

---

## 1. Color Tokens

### Base surfaces
```css
--bg-base:          #10131A;   /* deep navy-black, page base (was #10101A — shifted from indigo toward navy) */
--bg-elevated:      #141824;   /* subtle lift for sections/cards (was #15131E) */
--bg-tint-cool:     #16203A;   /* right-side ambient gradient, muted navy (was purple #1C1530) */
--bg-tint-warm:     #1E1A15;   /* bottom-left bronze glow bleed (was #22181B) */
--surface-badge:    #1C2438;   /* pill/badge fill, dark navy (was violet #2E1B41) */
```
The background retains the layered treatment: a base of `--bg-base` with large,
soft radial gradients — steel navy (`#16203A` → transparent) upper-right, warm
bronze-umber (`#1E1A15` → transparent) lower-left — plus the faint 1px grid
overlay. The scattered glow dots are reduced (see §5); in a banking context the
grid alone carries the "engineered precision" cue without reading playful.

### Brand accents
```css
--accent-bronze:        #C08A52;   /* headline highlight, primary accent (was orange #EF6A30) */
--accent-bronze-deep:   #96683C;   /* gradient dark stop (was #BE552D) */
--accent-indigo:        #5468A8;   /* active states, carousel, glows (was purple #8134CE) */
--accent-indigo-deep:   #3A4878;   /* wordmark, secondary accent (was #562583) */
--glow-indigo-soft:     #9FB0DC;   /* badge border glow, outer halos (was #C9A7F6) */
```
Bronze reads as ledger-and-brass rather than construction-cone; steel indigo
reads as institutional rather than neon. Both sit in the same hue families as
the originals, so existing imagery and gradients translate without a full
re-shoot.

### Text
```css
--text-primary:     #F5F7FA;   /* headings, button labels */
--text-body:        #7B879C;   /* paragraphs — muted slate, warmed +2% toward neutral (was #6D7C99) */
--text-nav:         #99A0AE;   /* nav links */
--text-caption:     #7B879C;   /* attribution lines, small print */
```
The slate body color is preserved as a deliberate choice — it recedes against
the accents while staying legible. It was nudged slightly lighter and less blue
because the reduced-contrast accents no longer need as much recession from the
body copy, and the extra lightness buys AA contrast headroom on `--bg-base`.

### Gradients
```css
--grad-cta:    linear-gradient(90deg, #C08A52 0%, #96683C 100%);
--grad-hero:   /* headline: white span + solid bronze span, not a text gradient */
```

---

## 2. Typography

Unchanged from the original spec — typography was never the problem, and the
bold grotesque at this scale reads as confidence in both contexts.

| Role | Spec |
|---|---|
| Family | Bold geometric grotesque — candidates: Inter, Manrope, or similar. Verify in bundle. |
| Hero H1 | ~68–76px, weight 700–800, line-height ~1.08, tracking slightly tight (-1% to -2%) |
| Hero two-tone | White (`--text-primary`) lead phrase, bronze (`--accent-bronze`) emphasis phrase — solid color spans, no gradient fill |
| Body / lede | ~18–19px, weight 400, line-height ~1.6, color `--text-body`, max-width ~34ch |
| Nav links | ~14–15px, weight 400–500, muted |
| Buttons | ~15–16px, weight 600–700 |
| Badge label | ~13–14px, weight 500 |
| Caption | ~13px, weight 400, `--text-caption` |

Sentence case throughout — no all-caps labels anywhere in the hero. (This
already aligns with the professional-services register; keep it.)

---

## 3. Components

### Primary button ("Get Started", "Read the Article")
- Pill shape, full radius (`border-radius: 9999px`)
- Fill: `--grad-cta` (bronze, left-light to right-dark)
- Label: white, weight 600, with leading icon (lucide-style stroke icons) and optional trailing arrow
- Outer glow: reduced to roughly `box-shadow: 0 0 16px 2px rgba(192,138,82,0.18)` (was 24px 4px at 0.35 — halve both spread and opacity)
- Padding approx `14px 28px`

### Secondary button ("Schedule a Call")
- Pill, transparent/near-bg fill (`#141822`)
- 1px border in muted indigo (~`rgba(84,104,168,0.45)`)
- White label, weight 600, trailing stroke icon

### Badge / eyebrow pill ("Latest Insight")
- Pill, fill `--surface-badge`
- 1px border with soft indigo glow — border color near `--glow-indigo-soft` at reduced opacity, outer halo `0 0 10px rgba(159,176,220,0.12)` (was 16px at 0.25)
- Pale steel-blue label + small icon
- Sits above H1 with ~24px gap

### Media card (hero image)
- Border radius ~24px
- 1px border, very low-contrast (`rgba(255,255,255,0.06)` range)
- Image fully bleeds to the rounded edge
- Ambient glow behind card: optional, and if used, match the muted palette — no saturated halos

### Carousel indicators
- Horizontal dash bars (~44px × 3px), gap ~12px
- Inactive: `#2C3140`; active: `--accent-indigo` (`#5468A8`)

### Scroll cue
- Outlined mouse glyph, 1px indigo stroke, centered below the fold line, small animated wheel dot

### Nav bar
- Transparent over the dark bg, no border or blur panel visible
- Logo left (icon mark + white wordmark), center link group, right phone number (muted, with phone icon) + primary pill CTA
- Link hover: assume brighten to `--text-primary` (verify)

---

## 4. Layout & Spacing

Unchanged — the generous whitespace and 45/55 hero split already communicate
restraint, which is the right instinct for this audience.

- Content container: ~1200–1280px max-width, generous side gutters
- Hero: two-column split, roughly 45/55 (text left, media right), vertically centered, full-viewport height with scroll cue at bottom
- Hero text stack rhythm: badge → H1 (~24px gap) → lede (~28px gap) → button row (~40px gap) → logo lockup + attribution caption
- Button row: two buttons, ~16px gap, left-aligned
- Whitespace is a feature: large top padding (~200px+) before hero content

---

## 5. Effects Summary

1. **Ambient radial glows** — steel navy and bronze-umber, very low opacity, oversized (600–900px radii), positioned off-canvas edges. Opacity ceiling ~60% of original values.
2. **Faint grid** — 1px lines at ~3% white opacity, large cells (~90px), fading toward center. Keep — it reads as precision.
3. **Glow dots** — reduce count by roughly half and cap opacity at ~10–15% (was 20–40%). Consider removing entirely on interior pages; retain sparingly in the hero if any.
4. **Component halos** — bronze glow on primary CTA, indigo glow on badge, both at half the original spread and opacity. The CTA should still be unambiguously the brightest element on the page.
5. **No glassmorphism, no heavy blur panels** — unchanged. Solid dark fills with hairline borders.

---

## 6. Contrast Notes (added for this variant)

1. `--text-body` #7B879C on `--bg-base` #10131A ≈ 5.6:1 — passes AA for body text.
2. White label on `--grad-cta` — check against the light stop `#C08A52` (≈ 2.9:1 for large/bold text only). If the label ever drops below button-scale bold weight, darken the light stop toward `#A87741`.
3. `--accent-bronze` as an H1 span on `--bg-base` ≈ 5.9:1 — fine at display sizes.
4. `--glow-indigo-soft` badge label on `--surface-badge` — verify; may need to lift toward `#B4C2E6`.

---

## 7. Verification Checklist (before treating as final)

1. Confirm typeface from the built CSS or font network requests.
2. Confirm hover/focus states (not capturable from a static screenshot).
3. Confirm responsive breakpoints — hero likely stacks to single column under ~1024px.
4. Gradient stop values on the CTA were derived, not sampled — validate visually against the original at 100% zoom side by side.
5. Validate the bronze/indigo pairing against actual brand photography — bronze can clash with cool-toned stock imagery common in financial marketing.
