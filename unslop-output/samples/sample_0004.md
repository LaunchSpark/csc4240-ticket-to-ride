## Troubleshooting / FAQ

Common setup and evaluation issues, with fixes. If your problem isn't listed, check that you're on the supported Python version (3.10+) and running commands from the repository root.

### `ModuleNotFoundError: No module named 'ticket_to_ride'` (or a dependency)

This almost always means the package isn't installed into the interpreter you're actually running, or you're launching scripts from the wrong directory.

- **Install the project in editable mode from the repo root:**
  ```bash
  pip install -e .
  ```
  The `-e` flag lets you edit source without reinstalling. Skipping it is the most common cause of the game engine importing but your local changes not showing up.

- **Confirm you're using the right interpreter.** If you use a virtual environment, activate it *before* installing and *before* running:
  ```bash
  python -m venv .venv
  source .venv/bin/activate        # Windows: .venv\Scripts\activate
  pip install -e .
  ```
  A frequent gotcha: installing with a system `pip` but running the game with a venv `python` (or vice versa). Check with `which python` and `which pip` — they should point into the same environment.

- **Run modules, not loose files.** Launch bots as modules so imports resolve against the package:
  ```bash
  python -m ttr.evaluate --bots mybot random_bot
  ```
  Running `python mybot.py` from inside a subdirectory breaks relative imports.

- **A missing third-party dependency** (e.g. `numpy`) means requirements weren't installed. Re-run `pip install -e .`, or `pip install -r requirements.txt` if you're not installing the package itself.

### The evaluator times out on slow bots

Each bot move is given a fixed time budget. If your bot does heavy computation (deep search, large simulations), the evaluator will forfeit the turn or disqualify the bot when it exceeds that budget.

- **See the current limit and raise it** for local testing:
  ```bash
  python -m ttr.evaluate --bots mybot --move-timeout 5.0
  ```
  `--move-timeout` is in seconds and applies per move. The default is intentionally short so full tournaments finish quickly; a higher value is fine while you're developing, but note the **graded/tournament runs use the default limit**, so a bot that only wins with a raised timeout will still fail under grading.

- **Profile before you increase the budget.** Timeouts are usually a sign of an inefficient move function, not an unreasonable limit. Cache expensive computations between turns, prune your search, and avoid recomputing the full game state each call.

- **Timeouts vs. hangs.** If a bot never returns (infinite loop), it will hit the timeout rather than freeze the whole run — the evaluator isolates each move. If the *entire* evaluator appears stuck, it's usually a bot spinning on every turn; run a single game with `--verbose` to find the offender.

### Results aren't deterministic (different winners each run)

By default, the game shuffles the deck and draws destination tickets randomly, so **win rates vary run to run** — especially over a small number of games. This is expected, not a bug.

- **Run more games** to get a stable estimate rather than reading into a single match:
  ```bash
  python -m ttr.evaluate --bots mybot baseline --games 500
  ```
  A handful of games tells you almost nothing; a few hundred gives a meaningful win-rate signal.

- **Non-determinism inside your bot** is a separate cause. If your bot itself calls `random` without a seed, uses set/dict iteration order in a way that affects moves, or depends on wall-clock time, its behavior will drift even when the game is seeded. Keep bot randomness routed through the seed the engine hands you (see below) so games stay reproducible.

### Setting a random seed for reproducible games

Pass an explicit seed to make shuffles, deals, and draws identical across runs. Same seed + same bots ⇒ same game, every time — essential for debugging a specific loss or filing a reproducible bug report.

```bash
python -m ttr.evaluate --bots mybot baseline --games 10 --seed 42
```

With a fixed `--seed`, the *sequence* of the 10 games is reproducible (each game derives its own sub-seed from the base seed), so game #7 plays out the same way on every run.

From Python:

```python
from ttr.evaluate import run_series

results = run_series(bots=["mybot", "baseline"], games=10, seed=42)
```

**Make your bot honor the seed.** Don't create a bare global `random` state. Seed a local generator from the value the engine provides so your bot is reproducible alongside the game:

```python
import random

class MyBot:
    def __init__(self, seed=None):
        self.rng = random.Random(seed)   # use self.rng everywhere, not random.*

    def choose_move(self, state):
        return self.rng.choice(state.legal_moves())
```

If you use NumPy, seed a dedicated generator the same way (`np.random.default_rng(seed)`) rather than calling `np.random.*` globally, which shares state across the whole process and defeats reproducibility.

> **Tip:** When reporting a bug to the TA, always include the exact command *and* the `--seed` you used. Without the seed, the failure often can't be reproduced.