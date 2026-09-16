# System Overview

The project is organized around one central backend service that coordinates the UI, replay storage, the game engine, and bot execution.

## Diagram

```text
Browser
  -> React viewer
  -> main backend API
       -> backend repository layer
            -> PocketBase
       -> backend/runtime package
            -> engine
            -> replay transport
            -> BotApiExecutor
                 -> external bot API
                      -> bot plugin loader/session manager
                           -> integrations/external/bots/*.py
```

## Who Owns What

- `applications/notebook_harness` (marimo notebooks)
  - operator UI for replays, the bot directory, and PocketBase queries
  - one directory-rooted `marimo edit` server; notebooks open via `?file=`
  - talks to the main backend API over HTTP for writes, and reads PocketBase's
    SQLite directly (read-only) for SQL cells
- `services/native-runtime/src/ticket_to_ride/backend/app.py`
  - HTTP entrypoint for `/bots`, `/matches`, and `/managed-matches`
- `services/native-runtime/src/ticket_to_ride/backend/runtime/`
  - managed series execution
  - round-scoped clocks, controller routing, failover, and executor calls
- `services/native-runtime/src/ticket_to_ride/backend/repository.py` and `services/native-runtime/src/ticket_to_ride/backend/pocketbase.py`
  - persistence contract and PocketBase-backed storage
- `services/native-runtime/src/ticket_to_ride/engine/`
  - game rules, legal actions, and turn progression
- `integrations/external/clients/bot_api/`
  - compatibility bot execution service over HTTP
- `integrations/external/clients/bot_api/loader.py` and `integrations/external/contracts/base_bot.py`
  - bot plugin discovery, metadata validation, and bot class loading
- `applications/notebook_harness`
  - pure-Python test harness for bot notebooks: builds in-process games, renders GraphWidget-ready board state from an in-memory turn log
  - no dependency on the backend, PocketBase, or HTTP — bot notebooks run fully offline
- `services/native-runtime/src/ticket_to_ride/runtime/cli.py`
  - `uv run run` starts PocketBase, the backend, and one shared marimo server

## Network Boundaries

- Notebooks -> main backend API: HTTP
- Main backend API -> PocketBase: repository abstraction backed by PocketBase HTTP APIs
- Main backend runtime -> external bot API: HTTP through `BotApiExecutor`
- Main backend runtime -> engine: in-process calls
- External bot API -> bot plugin system: in-process calls
- Notebooks -> PocketBase SQLite: direct read-only file access, for SQL cells only

## Runtime Package Layout

The managed runtime now lives in `services/native-runtime/src/ticket_to_ride/backend/runtime/`:

- `managed_match_runtime.py`
  - match lifecycle, round sequencing, aggregate results
- `round_runtime.py`
  - one full round/game, player construction, engine wiring
- `clock.py`
  - round-local time accounting
- `controllers.py`
  - seat/controller lifecycle and runtime views
- `failover.py`
  - switch-to-fallback transitions
- `executor.py`
  - `BotExecutor` plus the concrete `BotApiExecutor`
- `replay_transport.py`
  - repository-backed replay/log bridge
- `models.py`
  - internal runtime dataclasses and status literals
