```markdown
## Contributing a Bot

This section is for students submitting agents to the course tournament. Read it fully before opening a pull request — submissions that don't follow these conventions are sent back without grading.

### Naming Conventions

Every bot lives in its own file under the `agents/` directory:

```
agents/<lastname>_bot.py
```

- Use your **lowercase last name** only, followed by `_bot.py`. Example: a student named Ada Lovelace submits `agents/lovelace_bot.py`.
- If two students share a last name, append your first initial: `agents/lovelace_a_bot.py`.
- The file must define exactly one class named `Bot` that subclasses `BaseBot`:

  ```python
  from ttr.base import BaseBot

  class Bot(BaseBot):
      def take_turn(self, state, actions):
          ...
  ```

- Do **not** add files outside `agents/`, and do not modify shared engine code. Anything you need beyond the standard library and the packages in `requirements.txt` must be requested on the course forum first.

### Running Lint and Tests Locally

Before you submit, your bot must pass the same checks CI runs. From the repository root:

```bash
# 1. Install dev dependencies (once)
pip install -r requirements-dev.txt

# 2. Auto-format, then lint
black agents/
ruff check agents/

# 3. Run the full test suite against your bot
pytest tests/ -q

# 4. Run the smoke match — your bot must complete 100 games without crashing
python -m ttr.harness --bot agents/<lastname>_bot.py --games 100
```

All four steps must exit cleanly (`0`). The smoke match enforces the per-move time budget (**500 ms**); a bot that times out on any move counts as forfeiting that game and will lose performance points. Fix warnings locally — CI treats lint warnings as errors.

### Pull Request Format

Open one PR per submission against the `submissions` branch. Use this title and body template:

**Title:**
```
[Bot] <Lastname> — <short strategy name>
```

**Body:**
```markdown
## Summary
One or two sentences on your bot's strategy.

## Checklist
- [ ] File is named agents/<lastname>_bot.py
- [ ] `black`, `ruff`, and `pytest` all pass locally
- [ ] Smoke match completes 100 games with no crashes or timeouts
- [ ] No changes to files outside agents/

## Notes for graders
Anything unusual (heuristics, known weaknesses, external references).
```

- Keep the PR to a **single commit** if possible; squash before requesting review.
- Do not `@`-mention other students' bots or reference their code — submissions are graded independently.
- Push additional commits to the same PR to iterate; the **last commit before the deadline** is the one graded.

### Grading Rubric

Each submission is scored out of 100 points across three categories:

| Category | Weight | What we measure |
|---|---:|---|
| **Correctness** | **40%** | Bot always returns legal moves, never crashes, respects the game rules, and passes the full `pytest` suite. |
| **Performance** | **40%** | Win rate and average score across a round-robin tournament versus the reference bots and your classmates, under the 500 ms/move budget. |
| **Code Quality** | **20%** | Readability, structure, docstrings, meaningful names, and a clean `ruff`/`black` run with no suppressed warnings. |

Notes:

- **Correctness is a gate as well as a score.** A bot that crashes or emits illegal moves during the tournament forfeits the affected games, which also drags down its performance score.
- **Performance** is measured relative to the cohort, so a well-behaved but simple bot still earns solid correctness and code-quality points even if it doesn't top the leaderboard.
- **Code quality** is graded from the exact file you submit — comment your heuristics and keep `take_turn` legible. Cleverness that a grader can't follow is not rewarded.
```