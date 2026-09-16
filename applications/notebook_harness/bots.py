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
    mo.vstack([
        mo.md("### Open a bot notebook"),
        *[
            mo.md(f"[{row['name']}]({notebook_link(row['notebook'])})")
            for row in local_rows
        ],
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
