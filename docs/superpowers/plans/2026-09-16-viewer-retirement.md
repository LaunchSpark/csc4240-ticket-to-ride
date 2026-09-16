# Viewer Retirement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Retire `applications/viewer/` entirely, replacing it with a directory-rooted marimo server plus two new notebooks, and make PocketBase a first-class marimo data source.

**Architecture:** Navigation becomes `marimo edit <dir>` — a file browser at `/` with `?file=` deep links — which removes the need for `NotebookLauncher` and its per-bot subprocess. Two new notebooks (`bots.py`, `matches.py`) cover the two viewer nav items with no marimo counterpart. PocketBase is reached two ways by direction: a read-only SQLAlchemy engine for SQL cells and the data-sources panel, and the existing REST backend for every write.

**Tech Stack:** Python 3.12+, marimo 0.23.13, SQLAlchemy (new), polars (new), httpx, FastAPI, PocketBase (SQLite), unittest.

**Spec:** `docs/superpowers/specs/2026-09-16-viewer-retirement-design.md`

## Global Constraints

- Tests run with `uv run test` (unittest discovery over `quality/tests`); a single module runs as `.venv/bin/python -m unittest quality.tests.<module> -v` from the repo root.
- marimo is pinned `marimo>=0.23.13,<0.24` in the `notebooks` extra. Do not widen it.
- Every new notebook must pass `marimo check`. `quality/tests/test_marimo_notebooks_check.py` discovers notebooks by `app = marimo.App(` **at column zero** and needs no edit when notebooks are added.
- Notebook cells use `hide_code=True` only where the code is plumbing the reader should not have to see. `matches.py` and `bots.py` are analysis surfaces: leave their SQL and query cells **visible**.
- Underscore-prefixed cell-local variables: at most one or two per notebook. Prefer a new name over prefixing a whole cell.
- Widget CSS must be theme-aware via `light-dark()` with light fallbacks.
- PocketBase DB path is `operations/data/pocketbase/data.db`; it is gitignored and disposable. `data.db` is in `journal_mode=wal`.
- Commit after every green test cycle. Commit messages end with `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`.
- The deletion tasks (7, 8) are gated on Task 6 passing. Do not delete the viewer before the visual comparison is done.

---

### Task 1: PocketBase data source module

**Files:**
- Modify: `pyproject.toml` (the `notebooks` extra)
- Create: `applications/notebook_harness/pocketbase_source.py`
- Test: `quality/tests/test_pocketbase_source.py` (create)

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces:
  - `engine() -> sqlalchemy.Engine` — read-only engine over `data.db`.
  - `db_path() -> pathlib.Path` — absolute path to `data.db`.
  - `api(method: str, path: str, payload: dict | None = None, base: str | None = None) -> Any` — JSON REST call against the backend; raises `PocketBaseSourceError` on transport or HTTP failure.
  - `PocketBaseSourceError(RuntimeError)`
  - `DEFAULT_API_BASE: str` — `"http://127.0.0.1:8000"`

- [ ] **Step 1: Add the dependencies**

In `pyproject.toml`, the `notebooks` extra becomes:

```toml
notebooks = [
  # Floor is load-bearing, not cosmetic: every notebook in this repo uses
  # `with app.setup`, `@app.class_definition`, and `@app.function`, none of
  # which parse on older marimo. A lower floor lets a clean resolve install a
  # marimo that fails to open every bot and dashboard. Upper bound keeps the
  # generated-file format (`__generated_with`) in step with what CI checks.
  "marimo>=0.23.13,<0.24",
  "anywidget>=0.9",
  "wigglystuff>=0.1",
  # PocketBase as a marimo data source: SQLAlchemy supplies the read-only
  # engine for `mo.sql`, polars is the frame type `mo.sql` returns.
  "sqlalchemy>=2.0,<3",
  "polars>=1.0,<2",
]
```

Then install them:

```bash
uv pip install -e ".[notebooks]"
```

- [ ] **Step 2: Write the failing tests**

Create `quality/tests/test_pocketbase_source.py`:

```python
from __future__ import annotations

import json
import sqlite3
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from notebook_harness import pocketbase_source


class EngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = TemporaryDirectory()
        self.db = Path(self._tmp.name) / "data.db"
        con = sqlite3.connect(self.db)
        con.execute("create table matches (id text primary key, name text)")
        con.execute("insert into matches values ('m1', 'alpha')")
        con.commit()
        con.close()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_engine_reads_rows(self) -> None:
        import sqlalchemy

        engine = pocketbase_source.engine(self.db)
        with engine.connect() as conn:
            rows = conn.execute(sqlalchemy.text("select name from matches")).fetchall()

        self.assertEqual([row[0] for row in rows], ["alpha"])

    def test_engine_refuses_writes(self) -> None:
        import sqlalchemy

        engine = pocketbase_source.engine(self.db)
        with self.assertRaises(sqlalchemy.exc.OperationalError) as caught:
            with engine.connect() as conn:
                conn.execute(sqlalchemy.text("insert into matches values ('m2', 'beta')"))

        self.assertIn("readonly", str(caught.exception).lower())

    def test_engine_reads_while_another_connection_writes(self) -> None:
        # WAL means a reader must not block on a live writer. This is the
        # concurrency risk named in the spec, pinned as a test.
        import sqlalchemy

        writer = sqlite3.connect(self.db)
        writer.execute("pragma journal_mode=wal")
        writer.execute("begin")
        writer.execute("insert into matches values ('m3', 'gamma')")

        engine = pocketbase_source.engine(self.db)
        with engine.connect() as conn:
            rows = conn.execute(sqlalchemy.text("select count(*) from matches")).fetchall()

        writer.rollback()
        writer.close()
        self.assertEqual(rows[0][0], 1)

    def test_db_path_points_at_the_repo_database(self) -> None:
        self.assertEqual(pocketbase_source.db_path().name, "data.db")
        self.assertIn("pocketbase", str(pocketbase_source.db_path()))


class ApiTests(unittest.TestCase):
    def test_api_returns_decoded_json(self) -> None:
        calls = []

        def fake_request(method, url, json=None, timeout=None):
            calls.append((method, url, json))

            class Response:
                status_code = 200

                @staticmethod
                def json():
                    return {"bots": []}

                @staticmethod
                def raise_for_status():
                    return None

            return Response()

        result = pocketbase_source.api("GET", "/bots", transport=fake_request)

        self.assertEqual(result, {"bots": []})
        self.assertEqual(calls[0][0], "GET")
        self.assertTrue(calls[0][1].endswith("/bots"))

    def test_api_wraps_transport_failures(self) -> None:
        def broken(method, url, json=None, timeout=None):
            raise OSError("connection refused")

        with self.assertRaises(pocketbase_source.PocketBaseSourceError) as caught:
            pocketbase_source.api("GET", "/bots", transport=broken)

        self.assertIn("connection refused", str(caught.exception))

    def test_api_wraps_http_errors(self) -> None:
        def failing(method, url, json=None, timeout=None):
            class Response:
                status_code = 500

                @staticmethod
                def raise_for_status():
                    raise RuntimeError("500 Server Error")

            return Response()

        with self.assertRaises(pocketbase_source.PocketBaseSourceError):
            pocketbase_source.api("GET", "/bots", transport=failing)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `.venv/bin/python -m unittest quality.tests.test_pocketbase_source -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'notebook_harness.pocketbase_source'`

- [ ] **Step 4: Write the implementation**

Create `applications/notebook_harness/pocketbase_source.py`:

```python
"""PocketBase access for notebooks, split by direction.

Reads go through a read-only SQLAlchemy engine so `mo.sql` cells and marimo's
data-sources panel work against the real tables. Writes go through the FastAPI
backend, so nothing in a notebook depends on PocketBase's private table layout
— that schema is PocketBase's to change, and it does change across upgrades.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, Optional

DEFAULT_API_BASE = "http://127.0.0.1:8000"
_REQUEST_TIMEOUT_SECONDS = 10.0


class PocketBaseSourceError(RuntimeError):
    """Raised when the backend is unreachable or answers with an error."""


def db_path() -> Path:
    """Absolute path to the PocketBase SQLite database."""
    repo_root = Path(__file__).resolve().parents[2]
    return repo_root / "operations" / "data" / "pocketbase" / "data.db"


def engine(path: "Path | None" = None):
    """A read-only SQLAlchemy engine over the PocketBase database.

    The `mode=ro&uri=true` query is what makes this genuinely read-only: SQLite
    itself refuses writes, so a stray INSERT in a notebook cell fails loudly
    instead of mutating match history. `data.db` is in WAL mode, so this reader
    does not block while PocketBase is writing.
    """
    import sqlalchemy

    target = Path(path) if path is not None else db_path()
    return sqlalchemy.create_engine(f"sqlite:///file:{target}?mode=ro&uri=true")


def api(
    method: str,
    path: str,
    payload: "Optional[Dict[str, Any]]" = None,
    base: "Optional[str]" = None,
    transport: "Optional[Callable[..., Any]]" = None,
) -> Any:
    """Call the backend and return decoded JSON.

    `transport` exists so tests can drive this without a live server; it
    defaults to httpx, which is already a first-party dependency.
    """
    url = f"{(base or DEFAULT_API_BASE).rstrip('/')}{path}"

    if transport is None:
        import httpx

        transport = httpx.request

    try:
        response = transport(method, url, json=payload, timeout=_REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status()
    except PocketBaseSourceError:
        raise
    except Exception as exc:
        raise PocketBaseSourceError(f"{method} {url} failed: {exc}") from exc

    if getattr(response, "status_code", None) == 204:
        return None
    return response.json()
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `.venv/bin/python -m unittest quality.tests.test_pocketbase_source -v`
Expected: PASS, 7 tests

If `test_engine_refuses_writes` fails because the error text differs, print the exception and match the substring SQLite actually produces — do not weaken the assertion to "any exception", since that would also pass if the engine silently accepted writes.

- [ ] **Step 6: Run the full suite, then commit**

```bash
.venv/bin/python -m unittest discover -s quality/tests 2>&1 | tail -5
git add pyproject.toml applications/notebook_harness/pocketbase_source.py quality/tests/test_pocketbase_source.py
git commit -m "feat: PocketBase data source for notebooks, split read/write by direction

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 2: `matches.py` notebook

**Files:**
- Create: `applications/notebook_harness/matches.py`
- Test: covered by `quality/tests/test_marimo_notebooks_check.py` (auto-discovers)

**Interfaces:**
- Consumes: `pocketbase_source.engine()`, `pocketbase_source.db_path()` from Task 1.
- Produces: a notebook at `applications/notebook_harness/matches.py`. No importable API.

Replaces the viewer's **Matches** and **PocketBase** nav items. The `matches` table carries `id`, `name`, `mapName`, `seed`, `player_count`, `player_names`, `players`, `status`, `averageScores`; `rounds` carries `id`, `match_id`, `round_number`, `turn_count`; `turns` carries `id`, `match_id`, `round_id`, `turn_index`, `active_player_id`, `active_player_score`, `active_player_hand`, `active_player_remaining_trains`, `active_player_claimed_routes`, `active_player_destination_tickets`, `market_cards`, `opponents`, `turn_state`.

- [ ] **Step 1: Write the notebook**

Create `applications/notebook_harness/matches.py`:

```python
import marimo

__generated_with = "0.23.13"
app = marimo.App(width="medium")

with app.setup:
    import marimo as mo

    from notebook_harness.pocketbase_source import db_path, engine

    pocketbase = engine()


@app.cell(hide_code=True)
def _():
    mo.md(
        f"""
    # Matches — PocketBase
    Every stored match, queried straight from PocketBase's SQLite database at
    `{db_path()}`. The connection is read-only, so a stray `INSERT` here fails
    instead of rewriting match history. Open the **data sources** panel in the
    sidebar to browse the tables directly.
    """
    ).left()
    return


@app.cell
def _():
    matches = mo.sql(
        """
        SELECT id, name, mapName, seed, player_count, status, player_names
        FROM matches
        ORDER BY name
        """,
        engine=pocketbase,
    )
    return (matches,)


@app.cell
def _():
    per_round = mo.sql(
        """
        SELECT m.name AS match, r.round_number, r.turn_count
        FROM rounds r
        JOIN matches m ON m.id = r.match_id
        ORDER BY m.name, r.round_number
        """,
        engine=pocketbase,
    )
    return (per_round,)


@app.cell
def _():
    scoring = mo.sql(
        """
        SELECT m.name        AS match,
               t.active_player_id AS player,
               MAX(t.active_player_score) AS final_score,
               COUNT(*)      AS turns_taken
        FROM turns t
        JOIN matches m ON m.id = t.match_id
        GROUP BY m.name, t.active_player_id
        ORDER BY m.name, final_score DESC
        """,
        engine=pocketbase,
    )
    return (scoring,)


@app.cell(hide_code=True)
def _(matches):
    mo.md(
        "### Replay a match\n"
        "Open `replay.py` and pick the match there — it loads through the same "
        "series protocol the bot notebooks use."
    ) if len(matches) else mo.md(
        "*No stored matches yet. Run `uv run run` and play one.*"
    )
    return


if __name__ == "__main__":
    app.run()
```

Note the cells are **not** `hide_code=True` except the two prose cells: the SQL is the content of this notebook, and hiding it would defeat the purpose.

- [ ] **Step 2: Verify marimo accepts it**

Run: `.venv/bin/marimo check applications/notebook_harness/matches.py`
Expected: exit 0, no output

- [ ] **Step 3: Verify the discovery test picks it up**

Run: `.venv/bin/python -m unittest quality.tests.test_marimo_notebooks_check -v`
Expected: PASS. The notebook count rises from 12 to 13 with no edit to the test.

- [ ] **Step 4: Verify it runs against real data**

Run: `.venv/bin/python -c "
import sys; sys.path.insert(0, 'applications')
from notebook_harness.pocketbase_source import engine
import sqlalchemy
with engine().connect() as c:
    print(c.execute(sqlalchemy.text('select name, mapName, seed from matches')).fetchall())
"`
Expected: at least one row, e.g. `[('random_1-random_2', 'classic', 1745730632)]`

If this returns zero rows, the local PocketBase database is empty rather than broken — run `uv run run` once to seed a bootstrap match, then re-run.

- [ ] **Step 5: Commit**

```bash
git add applications/notebook_harness/matches.py
git commit -m "feat: matches.py — PocketBase match browser as SQL cells

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 3: `bots.py` notebook

**Files:**
- Create: `applications/notebook_harness/bots.py`
- Test: `quality/tests/test_bots_notebook.py` (create)

**Ordering:** this task's create-bot cell reads `created["notebook"]`, which only exists after **Task 4** reshapes `BotCreateResponse`. If you are executing tasks out of order, run Task 4 before this one. Task 3's own tests do not touch the API and pass either way, so the suite will not catch the mistake — the create-bot button will simply `KeyError` at runtime.

**Interfaces:**
- Consumes: `pocketbase_source.api`, `pocketbase_source.PocketBaseSourceError` from Task 1; `external.clients.bot_api.loader.BotLoader`; `BotCreateResponse.notebook` from Task 4.
- Produces:
  - `local_bot_rows() -> list[dict]` — one row per locally discovered bot, keys `bot_id`, `name`, `version`, `author`, `tags`, `notebook`.
  - `remote_bot_rows(payload: dict) -> list[dict]` — rows for `source == "remote"` entries of a `GET /bots` response, keys `bot_id`, `name`, `version`, `connection`, `base_url`.
  - `notebook_link(notebook: str) -> str` — `?file=` deep link, relative, for the running marimo server. Takes a **filename**, not a bot id.

**A trap worth naming:** `bot_id` comes from `BOT_META["id"]`, while the notebook's filename is the module stem. `BotLoader` does not require them to match, so `f"{bot_id}.py"` is wrong the moment someone names them differently. `BotDescriptor.module_path` carries the real path — use it.

Replaces `BotsDashboard.jsx` (522 lines). Local bots come from `BotLoader` in-process, so the common case needs no backend at all — an improvement on the dashboard, which required the backend even to list local bots. Remote bots and all writes go through `api()`.

`BotEntry` fields from the backend are: `botId`, `name`, `version`, `description`, `author`, `tags`, `source` (`"local"`/`"remote"`), `connectionId`, `baseUrl`. `ConnectionSummary` fields are: `connectionId`, `url`, `status`, `error`, `botCount`, `createdAt`.

- [ ] **Step 1: Write the failing tests**

Create `quality/tests/test_bots_notebook.py`:

```python
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


NOTEBOOK = (
    Path(__file__).resolve().parents[2]
    / "applications"
    / "notebook_harness"
    / "bots.py"
)


def load_notebook():
    spec = importlib.util.spec_from_file_location("bots_notebook", NOTEBOOK)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class BotsNotebookTests(unittest.TestCase):
    def test_local_rows_describe_every_discovered_bot(self) -> None:
        module = load_notebook()
        rows = module.local_bot_rows()

        self.assertTrue(rows, "expected at least one local bot")
        ids = {row["bot_id"] for row in rows}
        self.assertIn("random_bot", ids)

        row = next(r for r in rows if r["bot_id"] == "random_bot")
        self.assertEqual(row["name"], "Random Bot")
        self.assertEqual(row["notebook"], "random_bot.py")

    def test_notebook_name_comes_from_the_module_path_not_the_bot_id(self) -> None:
        # BOT_META["id"] and the filename are independent; deriving one from the
        # other breaks as soon as they diverge.
        module = load_notebook()
        for row in module.local_bot_rows():
            self.assertTrue(row["notebook"].endswith(".py"))
            self.assertNotIn("/", row["notebook"])

    def test_remote_rows_ignore_local_entries(self) -> None:
        module = load_notebook()
        payload = {
            "bots": [
                {"botId": "a", "name": "A", "version": "1", "source": "local",
                 "connectionId": None, "baseUrl": None},
                {"botId": "b", "name": "B", "version": "2", "source": "remote",
                 "connectionId": "c1", "baseUrl": "http://host:9000"},
            ],
            "connections": [],
        }

        rows = module.remote_bot_rows(payload)

        self.assertEqual([row["bot_id"] for row in rows], ["b"])
        self.assertEqual(rows[0]["base_url"], "http://host:9000")

    def test_remote_rows_tolerate_an_empty_payload(self) -> None:
        module = load_notebook()

        self.assertEqual(module.remote_bot_rows({}), [])

    def test_notebook_link_is_a_relative_file_query(self) -> None:
        module = load_notebook()

        self.assertEqual(module.notebook_link("random_bot.py"), "?file=random_bot.py")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m unittest quality.tests.test_bots_notebook -v`
Expected: FAIL — the notebook file does not exist yet.

- [ ] **Step 3: Write the notebook**

Create `applications/notebook_harness/bots.py`:

```python
import marimo

__generated_with = "0.23.13"
app = marimo.App(width="medium")

with app.setup:
    import marimo as mo

    from notebook_harness.pocketbase_source import PocketBaseSourceError, api


@app.function
def local_bot_rows():
    """Every bot discovered on disk, via the same loader the backend uses.

    Deliberately in-process: listing local bots must not require a running
    backend, which is the common case when someone opens this notebook.
    """
    from pathlib import Path

    from external.clients.bot_api.loader import BotLoader

    rows = []
    for bot_id, descriptor in sorted(BotLoader().load_bots().items()):
        meta = descriptor.metadata
        rows.append({
            "bot_id": bot_id,
            "name": meta.name,
            "version": meta.version,
            "author": meta.author,
            "tags": ", ".join(meta.tags),
            # From module_path, never f"{bot_id}.py": BOT_META["id"] and the
            # filename are independent and may differ.
            "notebook": Path(descriptor.module_path).name,
        })
    return rows


@app.function
def remote_bot_rows(payload):
    """Rows for the remote half of a `GET /bots` response."""
    return [
        {
            "bot_id": entry["botId"],
            "name": entry["name"],
            "version": entry["version"],
            "connection": entry.get("connectionId") or "",
            "base_url": entry.get("baseUrl") or "",
        }
        for entry in (payload or {}).get("bots", [])
        if entry.get("source") == "remote"
    ]


@app.function
def notebook_link(notebook):
    """Deep link opening a notebook in this same marimo server.

    Takes the filename — see local_bot_rows on why the bot id will not do.
    """
    return f"?file={notebook}"


@app.cell(hide_code=True)
def _():
    mo.md(
        """
    # Bots
    Local bots are discovered on disk and need no backend. Remote bots and
    connections come from the running backend — start it with `uv run run`.
    """
    ).left()
    return


@app.cell
def _():
    local_rows = local_bot_rows()
    mo.vstack([
        mo.md(f"### Local bots ({len(local_rows)})"),
        mo.ui.table(local_rows, selection=None),
    ])
    return (local_rows,)


@app.cell(hide_code=True)
def _(local_rows):
    mo.md("### Open a bot notebook")
    mo.vstack([
        mo.md(f"[{row['name']}]({notebook_link(row['notebook'])})")
        for row in local_rows
    ])
    return


@app.cell
def _():
    refresh_button = mo.ui.run_button(label="Load remote bots")
    refresh_button
    return (refresh_button,)


@app.cell
def _(refresh_button):
    mo.stop(
        not refresh_button.value,
        mo.md("*Press **Load remote bots** to query the backend.*"),
    )
    try:
        directory = api("GET", "/bots")
        directory_error = None
    except PocketBaseSourceError as exc:
        directory, directory_error = {}, str(exc)
    return directory, directory_error


@app.cell
def _(directory, directory_error):
    remote_rows = remote_bot_rows(directory)
    connections = (directory or {}).get("connections", [])
    mo.vstack([
        mo.md(f"### Remote bots ({len(remote_rows)})"),
        mo.md(f"*Backend unreachable: {directory_error}*")
        if directory_error
        else mo.ui.table(remote_rows, selection=None),
        mo.md(f"### Connections ({len(connections)})"),
        mo.ui.table(connections, selection=None),
    ])
    return


@app.cell
def _():
    new_bot_name = mo.ui.text(label="New bot name", placeholder="My Bot")
    create_button = mo.ui.run_button(label="Create bot")
    mo.hstack([new_bot_name, create_button], align="end", justify="start")
    return create_button, new_bot_name


@app.cell
def _(create_button, new_bot_name):
    mo.stop(not create_button.value, mo.md(""))
    mo.stop(not new_bot_name.value.strip(), mo.md("*Give the bot a name first.*"))
    try:
        created = api("POST", "/bots/new", {"name": new_bot_name.value.strip()})
        result = mo.md(
            f"Created **{created['botId']}** — "
            f"[open its notebook]({notebook_link(created['notebook'])})"
        )
    except PocketBaseSourceError as exc:
        result = mo.md(f"*Could not create the bot: {exc}*")
    result
    return


@app.cell
def _():
    connection_url = mo.ui.text(
        label="Bot API URL", placeholder="http://host:9000", full_width=True
    )
    connect_button = mo.ui.run_button(label="Add connection")
    mo.hstack([connection_url, connect_button], align="end", justify="start")
    return connect_button, connection_url


@app.cell
def _(connect_button, connection_url):
    mo.stop(not connect_button.value, mo.md(""))
    try:
        added = api("POST", "/bot-connections", {"url": connection_url.value.strip()})
        connect_result = mo.md(
            f"Connected **{added['connection']['url']}** — "
            f"{len(added.get('bots', []))} bot(s) available."
        )
    except PocketBaseSourceError as exc:
        connect_result = mo.md(f"*Could not add the connection: {exc}*")
    connect_result
    return


if __name__ == "__main__":
    app.run()
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m unittest quality.tests.test_bots_notebook -v`
Expected: PASS, 4 tests

- [ ] **Step 5: Verify marimo accepts it**

Run: `.venv/bin/marimo check applications/notebook_harness/bots.py`
Expected: exit 0, no output

- [ ] **Step 6: Run the full suite, then commit**

```bash
.venv/bin/python -m unittest discover -s quality/tests 2>&1 | tail -5
git add applications/notebook_harness/bots.py quality/tests/test_bots_notebook.py
git commit -m "feat: bots.py replaces the React bots dashboard

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 4: Decouple `create_bot` from `NotebookLauncher`

**Files:**
- Modify: `services/native-runtime/src/ticket_to_ride/backend/service.py:77-81`
- Modify: `services/native-runtime/src/ticket_to_ride/backend/models.py:62-64`
- Modify: `services/native-runtime/src/ticket_to_ride/backend/app.py` (the `/bots/new` route)
- Test: `quality/tests/test_bot_scaffold.py` (modify)

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `create_bot(directory: BotDirectory, name: str) -> BotCreateResponse`, where `BotCreateResponse` is `{botId: str, notebook: str}` — `notebook` is the bot's filename, e.g. `"my_bot.py"`.

This task exists because `create_bot` currently calls `notebook_launcher.launch(...)` to build its response URL. Task 5 cannot delete the launcher until this coupling is gone. Returning a filename rather than a URL is the right shape anyway: with a shared server the caller composes `?file=<notebook>`, and the backend no longer needs to know anything about how notebooks are served.

- [ ] **Step 1: Read the current behaviour and its test**

Run:
```bash
sed -n '70,85p' services/native-runtime/src/ticket_to_ride/backend/service.py
grep -n "create_bot\|BotCreateResponse\|notebook_launcher" quality/tests/test_bot_scaffold.py services/native-runtime/src/ticket_to_ride/backend/app.py
```

Record every call site before editing — the route in `app.py` constructs `create_bot`'s arguments and must change with it.

- [ ] **Step 2: Update the failing test first**

In `quality/tests/test_bot_scaffold.py`, replace assertions about `response.url` with:

```python
    def test_create_bot_returns_the_notebook_filename(self) -> None:
        directory = self.make_directory()

        response = create_bot(directory, "My Bot")

        self.assertEqual(response.botId, "my_bot")
        self.assertEqual(response.notebook, "my_bot.py")
```

Keep every existing test that covers id collision handling — `scaffold_bot`'s
`existing_bot_ids` behaviour is unchanged by this task and must stay green.

- [ ] **Step 3: Run the test to verify it fails**

Run: `.venv/bin/python -m unittest quality.tests.test_bot_scaffold -v`
Expected: FAIL — `create_bot() missing 1 required positional argument` or `BotCreateResponse has no field 'notebook'`

- [ ] **Step 4: Change the model**

In `models.py`, replace the `BotCreateResponse` definition:

```python
class BotCreateResponse(BaseModel):
    botId: str
    notebook: str
```

- [ ] **Step 5: Change the service**

In `service.py`, replace `create_bot`:

```python
def create_bot(directory: BotDirectory, name: str) -> BotCreateResponse:
    existing = {bot.bot_id for bot in directory.list_all().bots if bot.source == "local"}
    scaffolded = scaffold_bot(name, existing_bot_ids=existing)
    return BotCreateResponse(botId=scaffolded.bot_id, notebook=Path(scaffolded.path).name)
```

Add `from pathlib import Path` to the imports if it is not already present.

- [ ] **Step 6: Change the route**

In `app.py`, the `/bots/new` handler drops its launcher argument:

```python
@app.post("/bots/new", response_model=BotCreateResponse)
def post_bots_new(request: BotCreateRequest) -> BotCreateResponse:
    return create_bot(bot_directory, request.name)
```

Match the surrounding style for how `bot_directory` is resolved in this module — do not introduce a new dependency-injection pattern.

- [ ] **Step 7: Run the tests to verify they pass**

Run: `.venv/bin/python -m unittest quality.tests.test_bot_scaffold quality.tests.test_bot_directory_api -v`
Expected: PASS

- [ ] **Step 8: Run the full suite, then commit**

```bash
.venv/bin/python -m unittest discover -s quality/tests 2>&1 | tail -5
git add services/native-runtime/src/ticket_to_ride/backend/ quality/tests/test_bot_scaffold.py
git commit -m "refactor: create_bot returns a notebook filename, not a launcher URL

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 5: Delete `NotebookLauncher` and its endpoint

**Files:**
- Delete: `services/native-runtime/src/ticket_to_ride/backend/notebook_launcher.py`
- Delete: `quality/tests/test_notebook_launcher.py`
- Delete: `quality/tests/test_notebook_launch_api.py`
- Modify: `services/native-runtime/src/ticket_to_ride/backend/app.py` (remove the `/notebooks/{bot_id}/launch` route and the launcher wiring)
- Modify: `services/native-runtime/src/ticket_to_ride/backend/service.py` (remove the launch service function and the `NotebookLauncher` import)
- Modify: `services/native-runtime/src/ticket_to_ride/backend/models.py` (remove `NotebookLaunchResponse`)

**Interfaces:**
- Consumes: Task 4's decoupled `create_bot`.
- Produces: nothing. This task is subtractive.

Deleting the launcher also fixes a standing defect: `NotebookLauncher._sessions` was never reaped, so dead `marimo edit` processes accumulated for the backend's lifetime. A single shared server has nothing to leak.

- [ ] **Step 1: Confirm the launcher has no remaining consumers**

Run:
```bash
grep -rn "NotebookLauncher\|notebook_launcher\|notebooks/.*launch\|NotebookLaunchResponse" \
  --include="*.py" . | grep -v node_modules | grep -v "applications/viewer"
```
Expected: matches only inside the files listed above. If anything else appears, stop and handle that consumer before deleting.

- [ ] **Step 2: Delete the files**

```bash
git rm services/native-runtime/src/ticket_to_ride/backend/notebook_launcher.py
git rm quality/tests/test_notebook_launcher.py
git rm quality/tests/test_notebook_launch_api.py
```

- [ ] **Step 3: Remove the route, service function, and model**

Remove from `app.py` the `@app.post("/notebooks/{bot_id}/launch", ...)` handler and any module-level `NotebookLauncher()` construction. Remove the corresponding launch function and import from `service.py`. Remove `NotebookLaunchResponse` from `models.py`.

- [ ] **Step 4: Verify nothing references the removed names**

Run:
```bash
grep -rn "NotebookLauncher\|notebook_launcher\|NotebookLaunchResponse" \
  --include="*.py" . | grep -v node_modules | grep -v "applications/viewer"
```
Expected: no output.

- [ ] **Step 5: Run the full suite**

Run: `.venv/bin/python -m unittest discover -s quality/tests 2>&1 | tail -5`
Expected: OK. The total drops by however many tests the two deleted modules contained; no failures.

- [ ] **Step 6: Commit**

```bash
git add -A services/native-runtime/src/ticket_to_ride/backend/ quality/tests/
git commit -m "refactor: remove NotebookLauncher; a shared marimo server replaces it

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 6: Visual parity gate — BLOCKING

**Files:**
- Create: `docs/superpowers/notes/2026-09-16-shell-parity-comparison.md`

**Interfaces:**
- Consumes: nothing.
- Produces: a written comparison that either clears Tasks 7–8 or produces a punch list.

This task writes no production code. It exists because the spec verified *data* parity, not *visual* parity, and the deletion is irreversible in spirit even if `git revert` exists. Do not skip it, and do not treat "the notebook opened without error" as passing it.

- [ ] **Step 1: Rebuild the widget bundle**

```bash
cd applications/notebook_harness/widget-src && npm run build && cd -
```

Stale kernel bundles have produced phantom widget bug reports in this repo before. A fresh build first means any difference you see is real.

- [ ] **Step 2: Start the backend and confirm a stored match exists**

```bash
uv run run &
sleep 8
curl -s http://127.0.0.1:8000/matches | head -c 400
```
Expected: at least one match record. If the list is empty, let `run` seed its bootstrap match, then re-check.

- [ ] **Step 3: Open the React dashboard on that match**

```bash
cd applications/viewer && npm run dev
```
Open the Match Replay nav item, select the match, and screenshot: the board, the market strip, destination tickets, current player, player stats, and the match sidebar with playback controls.

- [ ] **Step 4: Open the marimo shell on the same match**

```bash
.venv/bin/marimo edit applications/notebook_harness/replay.py --headless --no-token -p 2780
```
Select the same match. Confirm in the browser console that `window.__routeGraphDebug.build` matches the bundle you built in Step 1.

- [ ] **Step 5: Compare and write the note**

Create `docs/superpowers/notes/2026-09-16-shell-parity-comparison.md` with one row per surface:

```markdown
# Shell vs. Dashboard — Visual Comparison

**Date:** 2026-09-16
**Bundle:** <value of window.__routeGraphDebug.build>

| Surface | React dashboard | marimo shell | Verdict |
|---|---|---|---|
| Board / routes | | | |
| Market strip | | | |
| Destination tickets | | | |
| Current player | | | |
| Player stats | | | |
| Leaderboard | | | |
| Playback controls | | | |

## Verdict

<PASS — proceed to deletion | FAIL — punch list below>
```

Fill every row. The market strip is expected to show less for stored matches in
**both** UIs — `deck_count` is `None` and the pie is empty on the marimo side, and
`replay-model.jsx:119` reads only `marketCards` on the React side. That shared
limitation is not a parity failure; a difference between the two is.

- [ ] **Step 6: Decide**

If any row is a genuine regression, **stop here**. Write the punch list into the note, report it, and treat closing those gaps as new tasks appended to this plan. Tasks 7 and 8 stay blocked until the verdict reads PASS.

- [ ] **Step 7: Commit the note**

```bash
git add docs/superpowers/notes/2026-09-16-shell-parity-comparison.md
git commit -m "docs: record shell/dashboard visual parity comparison

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 6a: Point `uv run run` at the marimo server — ADDED DURING EXECUTION

**Files:**
- Modify: `services/native-runtime/src/ticket_to_ride/runtime/cli.py`
- Test: `quality/tests/test_runtime_cli.py`

**Why this was not in the original plan.** The spec and plan both treated the
viewer as a standalone app. It is not: `uv run run` starts it, via 51 lines of
`cli.py` (`ViewerLaunchResult`, `ViewerRequestHandler`, `build_viewer_url`,
`_start_viewer_server`, `_start_vite_viewer`, `_start_viewer_runtime`,
`_stop_viewer_runtime`) plus the `run()` orchestration, with Vite preferred and
a static HTTP server as fallback. Deleting `applications/viewer` without this
task breaks the project's primary command.

**Decision:** `uv run run` starts the marimo server in the viewer's place, so
one command still brings up PocketBase, the backend, and the notebook surface.

**Interfaces:**
- Produces: `NotebookServerLaunch(process, message)`,
  `build_notebook_url(host, port) -> str`, `_start_notebook_runtime(host, port)`,
  `_stop_notebook_runtime(launch)`.
- Env vars: `TICKET_TO_RIDE_VIEWER_HOST`/`_PORT` become
  `TICKET_TO_RIDE_NOTEBOOK_HOST`/`_PORT`, default port `4173` → `2718`.

- [x] **Step 1: Update the CLI tests first** — replace the `build_viewer_url`
      and `ViewerRequestHandler` tests with one asserting
      `build_notebook_url("127.0.0.1", 2718) == "http://127.0.0.1:2718/"`, and
      repoint the three lifecycle tests from a viewer server MagicMock to a
      notebook process MagicMock asserting `terminate`.
- [x] **Step 2: Run to verify failure** — ImportError on `NotebookServerLaunch`.
- [x] **Step 3: Replace the runtime** — one `_start_notebook_runtime` spawning
      `marimo edit <notebook dir> --headless --host --port --no-token`,
      replacing all three viewer-start functions. Static serving and the
      JSX content-type handler go away entirely.
- [x] **Step 4: Remove orphaned imports** — `threading`, `partial`,
      `SimpleHTTPRequestHandler`, `ThreadingHTTPServer`, `urlencode`.
- [x] **Step 5: Verify** — 28 CLI tests pass, full suite 369 green, and a live
      `uv run run` brings up PocketBase (8090), marimo (2718) and the backend
      (8000), with `?file=bots.py` resolving to `mode: "edit"`.

---

### Task 7: Delete `applications/viewer`

**Files:**
- Delete: `applications/viewer/` (entire directory)
- Modify: `.gitignore` (drop viewer-specific entries, if any)
- Modify: `quality/tests/test_viewer_shell.py`, `quality/tests/test_viewer_playback.py`, `quality/tests/test_viewer_vite_config.py` (delete — they test the deleted app)

**Interfaces:**
- Consumes: Task 6's PASS verdict.
- Produces: nothing. Subtractive.

**Do not start this task unless Task 6's note reads PASS.**

- [ ] **Step 1: Confirm the gate passed**

Run: `grep -A2 "^## Verdict" docs/superpowers/notes/2026-09-16-shell-parity-comparison.md`
Expected: a line beginning `PASS`. If not, stop.

- [ ] **Step 2: Find every reference to the viewer**

Run:
```bash
grep -rn "applications/viewer\|viewer/" --include="*.py" --include="*.toml" \
  --include="*.md" --include="*.json" . | grep -v node_modules | grep -v "^./applications/viewer"
```
Record each one; Step 5 updates them.

- [ ] **Step 3: Delete the app and its tests**

```bash
git rm -r applications/viewer
git rm quality/tests/test_viewer_shell.py quality/tests/test_viewer_playback.py quality/tests/test_viewer_vite_config.py
```

- [ ] **Step 4: Run the full suite**

Run: `.venv/bin/python -m unittest discover -s quality/tests 2>&1 | tail -5`
Expected: OK, with the three viewer test modules' tests gone and no failures.

- [ ] **Step 5: Update the references found in Step 2**

Every path recorded in Step 2 must either be removed or repointed at the notebook surface. Do not leave a doc describing a nav item that no longer exists.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "refactor: delete applications/viewer; notebooks are the app surface

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 8: Document the new entry point

**Files:**
- Modify: `README.md`
- Modify: `docs/architecture/system-overview.md:44,53`
- Modify: `docs/repository-layout.md`
- Modify: `operations/research/README.md`

**Interfaces:**
- Consumes: Tasks 1–7.
- Produces: documentation describing how to start the app.

- [ ] **Step 1: Write the new launch instructions**

The entry point everywhere becomes:

```bash
uv run --extra notebooks marimo edit applications/notebook_harness
```

This serves a file browser at `/` and opens any notebook via `?file=<name>.py`. Document the three surfaces it exposes: `bots.py` (bot directory and creation), `matches.py` (PocketBase queries), `replay.py` (stored match playback). Note that bot notebooks live in `integrations/external/bots/` and are served by pointing the same command at that directory instead.

- [ ] **Step 2: Fix the architecture doc**

`docs/architecture/system-overview.md` lines 44 and 53 describe the viewer's Bots page spawning a `marimo edit` subprocess per bot via `POST /notebooks/{bot_id}/launch`. Both statements are now false. Replace with a description of the single shared server and `?file=` deep links.

- [ ] **Step 3: Verify no doc still describes the viewer**

Run:
```bash
grep -rn "applications/viewer\|Match Replay nav\|notebooks/.*launch" --include="*.md" . | grep -v node_modules
```
Expected: no output, apart from historical spec and plan documents under `docs/superpowers/`, which are records of past decisions and must not be rewritten.

- [ ] **Step 4: Run the full suite one final time**

Run: `.venv/bin/python -m unittest discover -s quality/tests 2>&1 | tail -5`
Expected: OK

- [ ] **Step 5: Commit**

```bash
git add README.md docs/
git commit -m "docs: marimo server is the app entry point

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```
