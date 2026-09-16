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
        SELECT m.name             AS match,
               t.active_player_id AS player,
               MAX(t.active_player_score) AS final_score,
               COUNT(*)           AS turns_taken
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
