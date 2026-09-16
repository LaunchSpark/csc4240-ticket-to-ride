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

    ``transport`` exists so tests can drive this without a live server; it
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
