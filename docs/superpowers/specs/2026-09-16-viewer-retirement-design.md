# Viewer Retirement — Design

**Date:** 2026-09-16
**Status:** Approved

## Problem

The repo maintains two independent implementations of the same spectate UI.

`applications/viewer/` is 2,711 lines of JSX across 33 files. Its replay surface —
map/routes, market strip, destination tickets, current player, player stats, match
sidebar, playback — is reproduced by `applications/notebook_harness/spectate_shell_widget.py`
and its bundled JS. Both read the same match payloads from the same backend. Any change
to how a match is displayed must be made twice, in two languages.

This duplication was always meant to be temporary. The spectate-UI-consolidation design
(2026-07-06) stated the trajectory directly: *"the website becomes a navigation plane
between notebooks, and the notebook harness grows into the main display for competitive
matches."* The spectate-shell-parity plan (2026-07-18) named the endpoint: *"so the
dashboard can be retired."*

That parity work is complete in code. What remains is to finish the sentence: retire the
viewer, and let a directory-rooted marimo server be the navigation plane.

A second gap motivates the same change. PocketBase currently has no analytical surface.
Match data is reachable only through hand-written REST calls or PocketBase's own admin
UI. Making PocketBase a first-class marimo data source turns 1,013 stored turns from an
opaque blob into something queryable in a SQL cell.

## Evidence

Each claim below was verified against the running code, not inferred.

| Claim | Method | Result |
|---|---|---|
| Replay panels are duplicated | Introspected both series classes against the 2026-07-18 plan's protocol | `HarnessSeries` and `StoredMatchSeries` each implement 11/11 methods |
| Retiring the React market panel loses no data | Compared `StoredMatchSeries.market_at` against `replay-model.jsx:119` | Both read `gameObjects.decks.marketCards`; React renders no deck/discard/pie either |
| The viewer has no human-play surface | Searched for turn-submission handlers | None; the viewer is purely observational |
| `/notebooks/{id}/launch` is viewer-only | Traced consumers | Only `BotsDashboard.jsx`, `bot-registry.jsx`, and their own tests |
| `/managed-matches/*` must stay | Traced consumers | No frontend consumer, but `cli.py:618-626` uses it for bootstrap |
| PocketBase is queryable as SQLite | Opened `data.db` read-only | 1 match, 10 rounds, 1,013 turns |
| SQL stack is absent | Imported each | `sqlalchemy`, `polars`, `duckdb`, `pandas` all missing |

The viewer's four nav items map onto replacements as follows:

| Viewer nav | Lines | Replacement |
|---|---|---|
| Match Replay | 1,282 (panels + replay app) | `replay.py` (exists, protocol-complete) |
| Bots | 522 (`BotsDashboard.jsx`) | `bots.py` (new) |
| Matches | in `Sidebar.jsx` | `matches.py` (new, SQL cells) |
| PocketBase | link-out | marimo's data-sources panel |

The remaining ~907 lines are shared shell — `app.jsx`, `atoms/`, `layout/`, `services/`,
`model/`, `constants.jsx` — which exist only to host the four nav items and go with them.

## Design

### Navigation: one directory-rooted server

`marimo edit` started against a directory serves a file browser at `/` and opens a
specific notebook at `?file=<path>`. Both relative-to-root and absolute paths work; the
served page reports `mode: "home"` versus `mode: "edit"` accordingly.

This replaces the React app shell, the sidebar, and the launch endpoint together. Opening
a bot is a link, not an API call that spawns a process.

### `notebook_harness/pocketbase_source.py` (new)

One module owns both halves of the hybrid integration, so no notebook needs to know there
are two mechanisms.

- `engine()` — a read-only SQLAlchemy engine over `operations/data/pocketbase/data.db`,
  opened with a `file:...?mode=ro` URI. Feeds `mo.sql(..., engine=...)` and marimo's
  data-sources panel. Read paths only.
- `api()` — a thin httpx wrapper over the FastAPI backend for every write and action.
  Writes never touch PocketBase's internal schema.

The split is by direction, not by convenience: reads go to SQL because SQL cells and the
data panel are the point; writes go to REST because PocketBase's table layout is a
private implementation detail that will change under upgrades.

### `bots.py` (new) — replaces BotsDashboard

Lists **local** bots through `BotLoader` in-process, requiring no backend for the common
case. This is a deliberate improvement on BotsDashboard, which needed the backend for
everything including local discovery.

- Local bots: `BotLoader().load_bots()` → `mo.ui.table` showing `BOT_META` (name,
  version, tags), each row linking to that bot's notebook via `?file=`.
- Remote bots and connections: `api()` against `GET /bots`, `POST /bot-connections`,
  `DELETE /bot-connections/{id}`.
- New bot: `POST /bots/new`, preserving the chooser flow added in `7a0efce`.

### `matches.py` (new) — replaces Matches and PocketBase nav

SQL cells over `engine()` against the `matches`, `rounds`, `turns`, and `managed_matches`
tables. Selecting a match links to `replay.py?file=...` for playback. marimo's
data-sources panel covers what the PocketBase nav item linked out to.

### Deletions

- `applications/viewer/` in full — 2,711 JSX lines plus its vendored `node_modules`,
  which is also the bulk of the repo's persistent git-status noise.
- `backend/notebook_launcher.py`, its `POST /notebooks/{bot_id}/launch` endpoint, its
  service method, and `test_notebook_launcher.py` / `test_notebook_launch_api.py`.

Deleting `NotebookLauncher` also resolves a standing defect: it tracked spawned servers
in a dict that was never reaped, so dead `marimo edit` processes accumulated for the
backend's lifetime. One shared server has nothing to leak.

### Dependencies

`sqlalchemy` and `polars` join the `notebooks` extra in `pyproject.toml`. `mo.sql`
returns polars frames by default; the engine needs SQLAlchemy. DuckDB is not required.

## What stays

- `/matches/*` — consumed by `stored_match.py` for replay.
- `/managed-matches/*` — consumed by `cli.py` for bootstrap. Untouched by this work.
- `/bots`, `/bots/new`, `/bot-connections` — consumed by `bots.py` for remote bots.
- Every widget under `notebook_harness/` — the shell is the surviving implementation.

## Testing

- `bots.py` and `matches.py` gain `marimo check` coverage automatically:
  `test_marimo_notebooks_check.py` discovers notebooks by `app = marimo.App(` at column
  zero and requires no edit when notebooks are added.
- New unit tests for `pocketbase_source`: `engine()` rejects writes, `api()` surfaces
  backend errors rather than swallowing them.
- Existing suite (367 tests) must stay green across each step, minus the two launcher
  test modules removed with the endpoint.

## Gates and risks

**Visual parity gate — blocking.** Data parity is verified; visual parity is not. Before
any deletion commit, open the marimo shell and the React dashboard on the same stored
match and compare them directly. Check `window.__routeGraphDebug.build` against a
freshly built bundle first — stale kernel bundles have produced phantom widget bug
reports in this repo before. If the shell falls short, that is a parity task to complete,
not grounds to abandon retirement; but the delete commit waits.

**Concurrent SQLite access.** `engine()` reads `data.db` while `pocketbase serve` may
hold it. `data.db` is already in `journal_mode=wal` (verified), so readers do not block
on a writer; combined with the read-only URI this should be safe. "Should be" is not
"is" — the tests must cover a read taken while the server is actively writing.

**Recently built code.** BotsDashboard's chooser-modal flow landed in `7a0efce`, three
commits before this design. `bots.py` must demonstrably cover that flow before the
viewer is removed.

**Ordering.** The deletion commit comes last, after `bots.py` and `matches.py` are
working and the visual gate has passed. Until then the viewer stays runnable, so the
comparison is always available.

## Out of scope

- Making bot notebooks "more notebooky" — tunable sliders sourced from
  `bot_lab.tunables()`, and extracting class helpers into `@app.function` cells. Designed
  separately; deferred by explicit sequencing decision.
- Pruning `/managed-matches/*`. It has no frontend consumer but the CLI depends on it;
  any change there is its own decision.
- PEP 723 headers, `[tool.marimo]` configuration, and the research-dashboard `importlib`
  loading hacks. Separate audit findings, unrelated to retirement.
