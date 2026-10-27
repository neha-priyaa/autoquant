# Themes (Dark + Light) — Design Spec

Date: 2026-10-22. Scope: theme switcher for the landing; chart/table plans noted.

## Palettes (all contrast ratios computed, WCAG)

| Token | Dark (default) | Light "paper" |
|---|---|---|
| bg | #0B0C0D | #F4F2EA |
| surface | #131516 | #FCFBF7 |
| ink | #F3F1EA (15.4:1) | #16181A (15.9:1) |
| dim | #969A97 | #5A5F5C (5.8:1) |
| accent | #C5F467 (15.4:1) | #3F6212 (6.3:1) |
| fail | #E5785C | #B3401F |
| line | rgba(243,241,234,.13) | rgba(22,24,26,.15) |

Raw lime on paper is 1.13:1 — unusable; the light accent steps down the same
hue family so the brand reads identically. Both themes pass AA everywhere the
tokens are used (accent is used for text/CTAs: 6.3:1 ≥ 4.5:1).

## Architecture

- Tokens stay CSS custom properties; `[data-theme="light"]` redeclares them on
  `html` after the Tailwind import (later in cascade, `html[data-theme]`
  specificity). Zero component changes — everything already reads tokens.
- `useTheme()` hook (`web/src/lib/theme.ts`): state from
  `documentElement.dataset.theme` (pre-set by an inline `index.html` snippet —
  no flash), persists to `localStorage("aq-theme")`, `toggle()` flips it.
- First visit follows `prefers-color-scheme`; choice persists. Default dark.
- Switcher: sun/moon button in the nav (desktop bar + mobile overlay),
  `aria-label="Toggle theme"`.

## Planned ahead (not in this change)

- Sortable tables: TanStack Table (headless), workspace slice.
- Chart framework: Recharts now; lightweight-charts if dense time series land.
  Charts must use theme tokens and validated palettes per theme.

## Tests

- `normalizeBasename`-style unit tests: hook sets `data-theme`, persists,
  toggles; default resolves to dark when unset.
- Gates: vitest, tsc + vite build, existing suites green.
