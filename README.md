# Ticket to Ride: bot experiments

A Python implementation of Ticket to Ride for running, inspecting, and comparing automated players. This repository supports a CSC 4240/5240 Artificial Intelligence class project: use AI tools and techniques to make game decisions, then evaluate those decisions through repeated games.

The code includes a game engine, seven bot implementations, marimo notebooks for watching games, a FastAPI backend with PocketBase storage, and scripts for tournament evaluation and XGBoost training. Bots choose from the engine's legal actions using a view of their own cards, tickets, and public game information.

## Run a game

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and use Python 3.12 or newer. Run these commands from the repository root:

```bash
uv sync
uv run marimo edit .
```

In marimo's file browser, open `integrations/external/bots/random_bot.py`. Choose a map, bots for at least two seats, and a round count. The notebook runs the selected games and provides playback controls, the route map, player hands, tickets, and scores. Changing the match controls runs a new series.

This demo runs in memory without PocketBase or the backend. JavaScript widget bundles are committed under `applications/notebook_harness/static/`; running the notebooks does not require a Node.js build.

For a game without opening a browser:

```bash
uv run python -c "import random; from external.bots.random_bot import RandomBot; from notebook_harness.game_runner import initialize_game; random.seed(7); game = initialize_game([RandomBot(), RandomBot()], map_name='classic', seed=7); game.play(); print(game.game.context.scores)"
```

The output is a score dictionary keyed by `bot_0` and `bot_1`. The engine seed controls card and ticket shuffles; `random.seed(7)` separately fixes RandomBot's choices. Recorded games preserve both the engine seed and the action sequence for replay.

## Bots and game rules

| Bot | Decision method |
| --- | --- |
| [Random Bot](integrations/external/bots/random_bot.py) | Random choice from legal actions; a baseline for comparisons. |
| [Example Bot](integrations/external/bots/example_bot.py) | Plans connections between destination tickets, using route point values as a cost estimate. |
| [Qualifier Bot](integrations/external/bots/qualifier_bot.py) | Uses expected turns to collect cards and claim routes as its planning cost. |
| [Fable Best Bot](integrations/external/bots/fable_best_bot.py) | Adds endgame timing, contested-route priorities, and locomotive spending heuristics. |
| [Codex Best Bot](integrations/external/bots/codex_best_bot.py) | Evaluates ticket portfolios and card draws with expected-turn costs and route risk. |
| [Bayesian Utility Bot](integrations/external/bots/bayesian_utility_bot.py) | Scores actions by expected utility and estimates opponents' hidden cards from public information. |
| [XG Bot](integrations/external/bots/xg_bot.py) | Ranks legal actions with a trained XGBoost model; falls back to QualifierBot when the model is unavailable or inference fails. |

The first six bot files are editable marimo notebooks with the shared game viewer. XG Bot is a Python module and can be selected as an opponent in those notebooks. “Best” is part of two bot names, not a measured ranking.

The engine loads `classic` and `europe` maps from `operations/data/maps/`, with destination tickets under `operations/data/`. It handles train-card draws, ticket selection, route payments, parallel-route restrictions, scoring, and endgame turns. Europe includes ferry payments with locomotive requirements. Tunnel flags are stored in the map, but tunnel reveal/surcharge mechanics and train stations are not implemented; games on that map use the rules currently implemented by this engine.

## Stored matches and the backend

To keep match history and use the database notebooks, install a [PocketBase binary for your operating system](https://pocketbase.io/docs/). The repository includes a Windows executable; macOS and Linux need their own executable.

| Platform | Default binary location |
| --- | --- |
| Windows | `operations/tools/pocketbase/pocketbase.exe` |
| macOS / Linux | `operations/tools/pocketbase/pocketbase` |

On macOS or Linux, make a downloaded binary executable with `chmod +x operations/tools/pocketbase/pocketbase`. The launcher also searches `PATH`; set `POCKETBASE_BINARY` to an absolute executable path to use another location.

```bash
uv run run
```

The launcher starts PocketBase when available, prepares its collections, starts the backend and marimo, and opens the notebook browser. When no stored replay matches exist, it creates a random-bot match with 10 rounds by default. Stop the launcher with `Ctrl+C` to stop the processes it started.

| Service | Default address |
| --- | --- |
| Notebook browser | <http://127.0.0.1:2718/> |
| Backend API documentation | <http://127.0.0.1:8000/docs> |
| PocketBase administration | <http://127.0.0.1:8090/_/> |

For local development, the launcher creates or updates the PocketBase superuser using `admin@example.com` / `12345678`. Set `POCKETBASE_ADMIN_EMAIL` and `POCKETBASE_ADMIN_PASSWORD` before startup to use different credentials. Database files live in `operations/data/pocketbase/`.

Open these files from the notebook browser:

| Notebook | Purpose and dependencies |
| --- | --- |
| [bots.py](applications/notebook_harness/bots.py) | Lists local bots without a backend; bot creation, remote listings, and connections use the backend. |
| [matches.py](applications/notebook_harness/matches.py) | Queries the local PocketBase SQLite database through read-only SQL cells. |
| [replay.py](applications/notebook_harness/replay.py) | Loads stored matches through the backend and displays their rounds in the shared viewer. |

If PocketBase is unavailable, the backend falls back to memory storage. Those records disappear when it stops, and `matches.py` still needs a local PocketBase database. Games played directly in bot notebooks stay in memory and are not automatically added to stored match history.

Local bots run through `act(view, legal_actions)`. The optional external HTTP bot service still uses the legacy `choose_*` protocol; enable it only for integration work with `TICKET_TO_RIDE_ENABLE_BOT_API=1`. See [external integration notes](integrations/external/README.md).

## Evaluate bot behavior

The [bot lab](operations/research/bot_lab.py) runs FableBestBot against `qualifier`, `example`, or `random`. It alternates seats across games and uses consecutive engine seeds. For example, this runs 20 games against each of two opponents, for 40 games total:

```bash
uv run python operations/research/bot_lab.py --games 20 --opponents qualifier,example --seed-base 9000 --tag baseline
uv run marimo edit operations/research/bot_lab_dashboard.py
```

Results accumulate in `operations/research/results/`:

- `games.jsonl`: wins, score margins, score components, action counts, and heuristic settings.
- `claims.jsonl`: route-claim events.
- `records.jsonl`: engine seeds and action logs for replay.

The lab also accepts `--set KEY=VALUE` and `--sweep KEY=V1,V2,...` to vary FableBestBot's numeric settings. `--fresh` deletes the existing lab result files before a run. Export recorded decisions with:

```bash
uv run python operations/research/decision_export.py
```

This writes `operations/research/results/decisions.jsonl`, including the acting player's view, legal options, chosen action, and final outcome. Map analysis and its dashboard are described in [the research notes](operations/research/README.md).

For the course evaluation, report the bot versions, map, game count, seeds, seating, and settings alongside the results. The current lab uses the classic map and alternates seats on different seeds; a stronger follow-up experiment would play each seed in both seat orders. RandomBot's choices need a separate random seed for repeatable reruns. Keep experiment outputs with the report: `operations/research/results/` is gitignored, so cloning the repository does not retrieve them.

## Train XG Bot

The training tools use XGBoost's pairwise ranking objective to learn action preferences from recorded QualifierBot decisions. Generate a small local dataset and train a model with:

```bash
uv sync --extra xgb
uv run --extra xgb python operations/research/xg_data_pump.py --games 10 --seed-base 9000 --no-db
uv run --extra xgb python operations/research/train_xg_bot.py --limit 5000
uv run --extra xgb marimo edit operations/research/xg_bot_training_dashboard.py
```

`--no-db` skips backend logging while retaining local training outputs. The pump writes cached decision groups to `operations/research/results/xg_pump_feature_rows.jsonl`. Training writes `xg_bot_ranker.json` and `xg_bot_features.json` in that directory; XG Bot loads those files by default.

This is imitation of a heuristic teacher. The trainer's report measures agreement on its training data, so it does not establish performance on unseen games. Evaluate the trained bot on separate games before claiming an improvement, and check that it loaded the model instead of using its fallback.

## Write a bot

Use **New bot** in `applications/notebook_harness/bots.py` with the backend running, or copy [the starter notebook](integrations/external/templates/bots/build_your_bot_here.py) into `integrations/external/bots/`.

Give the copy a unique `BOT_META["id"]`, a display name, version, and description. Rename its class and corresponding notebook references. Discovery expects exactly one concrete `BaseBot` subclass; the template extends `ActionBot` and sets `META = BOT_META` on the class.

Implement `act(view, legal_actions)` and return one of the supplied actions. The engine provides the legal menu for each decision, including ticket selection and a second card draw. Keep module imports free of game-running side effects. Open the copied notebook to edit the strategy and compare it against existing bots.

## Tests and source layout

```bash
uv run test
uv run python -m unittest discover -s integrations/external/tests
```

The first command runs `unittest` discovery in `quality/tests/`, covering engine rules, replay, bot behavior, backend APIs, runtime execution, notebook integration, and marimo file checks. The second runs the separate external integration suite. Include `--extra xgb` when exercising the optional training dependencies.

| Directory | Contents |
| --- | --- |
| `services/native-runtime/src/ticket_to_ride/` | Engine, player views, logging, backend, runtime launcher. |
| `applications/notebook_harness/` | Notebook pages, game runner, playback widgets, and bundled JavaScript. |
| `integrations/external/` | Bots, starter template, contracts, and external clients. |
| `operations/research/` | Tournament, map evaluation, decision export, and training tools. |
| `operations/data/` | Map and ticket CSVs plus local PocketBase state. |
| `quality/tests/` | Main automated test suite. |
| `docs/` | Architecture notes, designs, and implementation plans. |

`uv sync` installs the `ticket_to_ride`, `notebook_harness`, and `external` packages from these directories. For implementation details, see the [system overview](docs/architecture/system-overview.md), [bot execution path](docs/architecture/bot-execution-path.md), and [repository layout](docs/repository-layout.md). Design and planning documents may describe work beyond the current implementation.

## CSC 4240/5240 submission

The assignment asks for an executable project with dependency and run instructions, an evaluation, and an explanation of the chosen AI tools and techniques. This README supplies the run instructions and identifies the experiment tools. The report still needs measured results, major approaches tried or abandoned, reasons for the technical choices, and each team member's contribution.

The supplied assignment lists the proposal for September 17, progress meetings for October 25–November 5, report and code for November 25, and presentations during the week of December 1. CSC 4240 reports are limited to four pages; CSC 5240 reports are limited to six pages excluding references and require a research-paper format with a literature review. The README and passing software tests do not replace that evaluation or report.
