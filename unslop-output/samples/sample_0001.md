# Ticket to Ride Agent Assignment

A course project for implementing and evaluating game-playing agents for a simplified version of *Ticket to Ride*. You will build three agents of increasing sophistication — a random baseline, a greedy heuristic player, and a minimax search player — and submit them to an automated tournament runner that scores them against reference opponents.

---

## Overview

*Ticket to Ride* is a route-building board game. Players collect colored train cards and spend them to claim railway routes between cities on a shared map. Points are awarded for claiming routes and for completing secret "destination tickets" (city-to-city connection goals). The player with the most points at the end wins.

For this assignment, you will work against a **simplified, fully-observable variant** of the game exposed through a fixed Python API. You do **not** need to implement the game rules — the engine handles legality, turn order, scoring, and endgame detection. Your job is to write the *decision-making logic*: given a game state and the set of legal actions, choose one.

You will implement three agents:

| Agent | Strategy | Goal |
|-------|----------|------|
| `RandomAgent` | Picks a legal action uniformly at random. | Warm-up; verify you understand the interface. |
| `GreedyAgent` | Chooses the action that maximizes an immediate heuristic score. | Introduce state evaluation. |
| `MinimaxAgent` | Searches ahead with depth-limited minimax and alpha-beta pruning. | Introduce adversarial search under a time budget. |

Each agent is graded on correctness (it produces only legal moves and never crashes or times out) and on performance in the tournament (win rate and average score against reference opponents).

**Learning objectives**

- Translate an abstract strategy into concrete, testable code against a given interface.
- Design and justify a state-evaluation heuristic.
- Implement depth-limited adversarial search with alpha-beta pruning and a move-time budget.
- Reason about the trade-off between search depth, evaluation quality, and time limits.

---

## Requirements

- **Python 3.11 or newer** (the codebase uses `match` statements and modern typing syntax).
- **numpy** (used by the engine for board representation and by the harness for statistics).
- Roughly 500 MB of free disk for logs and replay files during tournaments.
- No GPU or network access is required. Everything runs locally on CPU.

All Python dependencies are pinned in `requirements.txt`.

---

## Installation

We strongly recommend a virtual environment so your submission's dependencies match the autograder's.

```bash
# 1. Clone (or unzip) the assignment into a working directory
git clone https://example.edu/courses/ai/ticket-to-ride-assignment.git
cd ticket-to-ride-assignment

# 2. Create and activate a virtual environment
python3.11 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 3. Install dependencies
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

# 4. Verify the installation
python -m ttr.selftest
```

`python -m ttr.selftest` runs a 10-game smoke test using the built-in `RandomAgent`. If it prints `SELFTEST OK` and exits with status `0`, your environment is ready. If it fails, re-check your Python version first (`python --version` must report 3.11+).

---

## Project Structure

```
ticket-to-ride-assignment/
├── README.md                  # This file
├── requirements.txt           # Pinned dependencies (python 3.11+, numpy)
├── ttr/                        # Game engine and harness (DO NOT MODIFY)
│   ├── __init__.py
│   ├── engine.py               # Core game rules, turn loop, scoring
│   ├── state.py                # GameState, Action, and observation types
│   ├── base_agent.py           # BaseAgent abstract class — your interface
│   ├── reference/              # Reference opponents used for grading
│   │   ├── rookie_bot.py
│   │   └── veteran_bot.py
│   ├── harness.py              # Tournament runner (entry point below)
│   └── selftest.py             # Environment smoke test
├── agents/                     # YOUR CODE GOES HERE
│   ├── __init__.py
│   ├── random_agent.py         # Implement RandomAgent
│   ├── greedy_agent.py         # Implement GreedyAgent
│   └── minimax_agent.py        # Implement MinimaxAgent
├── maps/
│   └── standard.json           # The board used for grading
├── tests/
│   └── test_agents.py          # Public tests you can run locally
└── replays/                    # Tournament output is written here
```

You should only ever edit files inside `agents/`. Anything under `ttr/` is provided, is identical to what the autograder uses, and **must not be modified** — changes there are ignored at grading time and may cause your submission to fail to load.

---

## How to Implement Your Own Bot

Every agent must subclass `ttr.base_agent.BaseAgent` and implement the `choose_action` method. The engine constructs your agent once per game, then calls `choose_action` on each of your turns.

### The `BaseAgent` interface

```python
# ttr/base_agent.py  (provided — shown here for reference)

from abc import ABC, abstractmethod
from ttr.state import GameState, Action, PlayerView


class BaseAgent(ABC):
    """Base class for all Ticket to Ride agents.

    A new instance is created at the start of each game. Instances are
    NOT reused across games, so per-game state can safely live on self.
    """

    def __init__(self, player_id: int, rng_seed: int | None = None) -> None:
        """Store your player id and (optionally) seed any randomness.

        Args:
            player_id: Your seat index (0 or 1) for this game.
            rng_seed:  A per-game seed. If you use randomness, seed your
                       generator with this so your games are reproducible.
        """
        self.player_id = player_id

    @abstractmethod
    def choose_action(self, view: PlayerView, legal_actions: list[Action]) -> Action:
        """Return the action to take this turn.

        Args:
            view:          A read-only observation of the game from your
                           perspective (see PlayerView below).
            legal_actions: The non-empty list of currently legal actions.
                           You MUST return one of these exact objects.

        Returns:
            The chosen Action. Returning an action not in `legal_actions`,
            raising an exception, or exceeding the per-move time budget
            results in a forfeited turn (a random legal move is played
            on your behalf and a penalty is recorded).
        """
        raise NotImplementedError

    def on_game_end(self, final_view: PlayerView, won: bool) -> None:
        """Optional hook called once when the game finishes.

        Override for logging or learning between turns. The default
        implementation does nothing. Not called during grading time limits.
        """
        return None
```

### The types you receive

You do not need to know the full engine internals, only the read-only observation and action types:

```python
# Key fields available on PlayerView (read-only; do not mutate):
#
#   view.my_score          -> int            your current score
#   view.opponent_score    -> int            opponent's current score
#   view.my_hand           -> dict[str,int]  color -> count of train cards you hold
#   view.my_trains_left    -> int            train pieces remaining in your supply
#   view.my_tickets        -> list[Ticket]   your destination tickets (city_a, city_b, points)
#   view.claimed_routes    -> list[Route]    routes already claimed, with owner ids
#   view.open_routes       -> list[Route]    routes still available to claim
#   view.face_up_cards     -> list[str]      the 5 face-up train cards in the market
#   view.turn_number       -> int            0-indexed turn counter
#
# An Action is an immutable dataclass; you never build one yourself.
# You inspect its .kind and choose among the provided legal_actions:
#
#   action.kind == "draw_card"     draw a train card (see action.color / "blind")
#   action.kind == "claim_route"   claim a route (see action.route)
#   action.kind == "draw_tickets"  draw new destination tickets
```

`view` also exposes helper methods you will find useful:

- `view.route_cost(route) -> dict[str, int]` — the cards required to claim a given route.
- `view.can_afford(route) -> bool` — whether your current hand can pay for it.
- `view.shortest_path_len(city_a, city_b) -> int | None` — length of the shortest remaining path between two cities using unclaimed routes, or `None` if disconnected.

### A minimal example: `RandomAgent`

```python
# agents/random_agent.py
import random
from ttr.base_agent import BaseAgent
from ttr.state import Action, PlayerView


class RandomAgent(BaseAgent):
    def __init__(self, player_id: int, rng_seed: int | None = None) -> None:
        super().__init__(player_id, rng_seed)
        self._rng = random.Random(rng_seed)

    def choose_action(self, view: PlayerView, legal_actions: list[Action]) -> Action:
        return self._rng.choice(legal_actions)
```

### Sketching `GreedyAgent`

Score each legal action with a heuristic and return the best one. A reasonable starting heuristic rewards claiming routes that advance an incomplete destination ticket and penalizes wasting cards. Break ties deterministically (e.g., by a stable sort key) so your results are reproducible.

```python
# agents/greedy_agent.py  (skeleton)
class GreedyAgent(BaseAgent):
    def choose_action(self, view, legal_actions):
        return max(legal_actions, key=lambda a: self._heuristic(view, a))

    def _heuristic(self, view, action) -> float:
        ...  # your evaluation — document your reasoning in a comment
```

### Sketching `MinimaxAgent`

Implement depth-limited minimax with alpha-beta pruning over a copy of the game state.

- Use `view.simulate(action)` to get the successor `PlayerView` **without** mutating the real game (the engine provides a deterministic, sampling-free simulation for search).
- Reuse (and improve) your greedy heuristic as the leaf-node evaluation function.
- **Respect the time budget.** Track elapsed wall-clock time and return the best action found so far before you hit the limit. Iterative deepening is the recommended pattern.

```python
# agents/minimax_agent.py  (skeleton)
import time

class MinimaxAgent(BaseAgent):
    TIME_BUDGET_S = 0.9   # stay safely under the 1.0s per-move limit

    def choose_action(self, view, legal_actions):
        deadline = time.monotonic() + self.TIME_BUDGET_S
        best = legal_actions[0]
        depth = 1
        while time.monotonic() < deadline:
            best = self._search_to_depth(view, legal_actions, depth, deadline)
            depth += 1
        return best
```

---

## Running the Evaluation Harness

The tournament runner lives in `ttr.harness`. It loads your agent, pairs it against reference opponents, plays a batch of games, and reports aggregate statistics.

Run a quick match of your greedy agent against the rookie reference bot:

```bash
python -m ttr.harness \
    --agent agents.greedy_agent:GreedyAgent \
    --opponent rookie \
    --games 100 \
    --map maps/standard.json \
    --seed 42
```

Common flags:

| Flag | Default | Meaning |
|------|---------|---------|
| `--agent MODULE:CLASS` | *(required)* | Import path to your agent, e.g. `agents.minimax_agent:MinimaxAgent`. |
| `--opponent {rookie,veteran,random,self}` | `rookie` | Reference opponent. `self` mirrors your own agent. |
| `--games N` | `50` | Number of games to play (seats are swapped each game to remove first-move bias). |
| `--map PATH` | `maps/standard.json` | Board to play on. Grading always uses `standard.json`. |
| `--seed N` | `0` | Master seed; makes the whole run reproducible. |
| `--time-limit S` | `1.0` | Per-move time budget in seconds. Exceeding it forfeits the turn. |
| `--save-replays` | off | Write per-game replay files to `replays/`. |
| `--quiet` | off | Suppress per-game lines; print only the final summary. |

Run the full local test suite before submitting:

```bash
python -m pytest tests/
```

The public tests check that each of your agents (a) loads, (b) returns only legal actions across many random states, and (c) stays within the time limit. Passing them is necessary but **not** sufficient for full marks — the autograder runs additional hidden games.

---

## Understanding the Scoring Output

At the end of a run the harness prints a summary block:

```
==================== TOURNAMENT SUMMARY ====================
Agent:        agents.greedy_agent:GreedyAgent
Opponent:     rookie
Games:        100      (seats swapped every game)
Seed:         42
------------------------------------------------------------
Wins:         67       (67.0%)
Losses:       30       (30.0%)
Draws:         3        (3.0%)
Avg score (you):        84.2   +/- 11.5
Avg score (opponent):   71.9   +/- 13.1
Avg score margin:      +12.3
Avg turn time:          0.021s   (max 0.089s, limit 1.000s)
Illegal-move forfeits:  0
Timeout forfeits:       0
Crashes:                0
------------------------------------------------------------
RESULT: PASS   (win rate 67.0% >= 55.0% threshold vs rookie)
============================================================
```

How to read it:

- **Win rate** is the headline number. Each opponent has a passing threshold (e.g. beat `rookie` ≥ 55%, `veteran` ≥ 40%). These thresholds are what grade correctness of your *strategy*.
- **Avg score / margin** is a secondary signal used for the leaderboard and partial credit. A positive margin means you generally outscore the opponent even in games you lose.
- **`+/-`** values are one standard deviation across games — a wide spread means your agent is inconsistent, which usually points to a fragile heuristic.
- **Avg / max turn time** must stay under the limit. If `max` approaches `limit`, your minimax search is cutting it close; lower your time budget.
- **Forfeits and crashes must all be `0`.** Any nonzero value here means your agent produced an illegal move, timed out, or raised an exception — the single most common cause of lost points. Use `--save-replays` and inspect the offending game in `replays/` to debug.
- **`RESULT: PASS/FAIL`** reflects only the win-rate threshold for that opponent. The autograder aggregates results across all reference opponents.

Exit codes: `0` on `PASS`, `1` on `FAIL`, `2` on a harness/loading error (usually a bad `--agent` import path or a syntax error in your file).

---

## Academic Integrity

This is an individual assignment unless your instructor states otherwise. The following rules apply:

- **Write your own agents.** You may discuss strategies, heuristics, and search algorithms at a conceptual level with classmates, but the code you submit in `agents/` must be written by you, alone.
- **Do not share code.** Sharing your `agents/` files — in whole or in part, before or after the deadline — is a violation, as is using another student's code.
- **Cite your sources.** If you adapt an idea, pseudocode, or a technique from a textbook, paper, blog post, or AI assistant, add a comment in your code crediting the source. Adapting *ideas* with attribution is fine; copying *implementations* is not.
- **Do not modify or circumvent the engine or harness.** Editing anything under `ttr/`, probing hidden test internals, hard-coding against the reference bots' specific behavior, reading files outside the sandbox, or attempting to influence the grader are all serious violations.
- **No plagiarism-by-generation.** If you use an AI tool to help, you remain fully responsible for understanding and being able to explain every line you submit. You may be asked to walk through your code in an oral check; inability to explain your own submission is treated as evidence of misconduct.
- **Reproducibility.** Your agents must be deterministic given a fixed seed. Non-determinism that makes results impossible to reproduce may be treated as an attempt to game the autograder.

Violations are reported to the department and handled under the university's academic integrity policy. When in doubt about what is permitted, **ask the course staff before you submit** — asking is always safe.

---

*Good luck, and have fun building your railroads.* 🚂