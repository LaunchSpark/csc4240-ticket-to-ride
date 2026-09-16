# Shell vs. Dashboard — Visual Comparison

**Date:** 2026-09-16
**Bundle:** rebuilt from `widget-src` immediately before comparison (esbuild, `__RG_BUILD__` stamped at build time)
**Verdict:** **PASS — proceed to deletion**

## How this was assessed

Two sources, agreeing.

**The author's assessment, which is the one that counts.** Everything on the
dashboard's replay surface has already been replicated in the notebook harness.
The only thing left in the viewer without a harness counterpart is the
navigation bar, which is stale and is meant to disappear — and it disappears
with the viewer itself, so it needs no replacement.

**A headless corroboration.** Both UIs were started against the same stored
match (`random_1-random_2`, `dv8vl97r8ckr4qv`, map `classic`, seed
`1745730632`) with a freshly rebuilt widget bundle, and driven in headless
Chrome via `playwright-core`.

## What the harness renders

| Surface | Present in the marimo shell |
|---|---|
| Board / routes | Yes — full graph, claimed and unclaimed routes, per-colour styling |
| Playback controls | Yes — first / play / next |
| Jump to round / turn | Yes |
| Round + turn indicator | Yes — "ROUND 1 · TURN 1" |
| Leaderboard | Yes — ordered player cards with score |
| Per-player stats | Yes — trains left, tickets, routes, hidden cards |
| Hand composition | Yes — per-colour counts |
| Unclaimed-route opacity | Yes — a control the React dashboard does not have |
| Stored-match picker | Yes |

## Known shared limitation — not a parity failure

The market panel shows less for stored matches in **both** UIs.
`StoredMatchSeries.market_at` returns `deck_count=None`, `pie=[]`, and the
label "Unavailable for stored matches"; `replay-model.jsx:119` reads only
`gameObjects.decks.marketCards` and renders no deck or discard counts either.
Stored turns carry snapshots rather than a replayable action log, so the data
does not exist on either side. Nothing is lost by retiring the React surface.

## Consequence

Tasks 7 and 8 of `docs/superpowers/plans/2026-09-16-viewer-retirement.md` are
unblocked.
