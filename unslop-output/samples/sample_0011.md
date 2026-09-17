## Example Walkthrough: Your First Bot on the Arena

This walkthrough follows a student, `astro`, from registering a fresh bot through reading a losing match and tuning their strategy. Every command below is run from the repository root inside your activated environment.

### 1. Register your bot

Scaffold a new agent from the starter template and register it with the local arena:

```bash
$ ttr-arena new-bot pathfinder --template baseline
Created bots/pathfinder/
  ├── agent.py          # implement decide() here
  ├── bot.toml          # metadata + entry point
  └── README.md

$ ttr-arena register bots/pathfinder
✓ Validated entry point: bots.pathfinder.agent:PathfinderAgent
✓ Registered "pathfinder" (id: bot_7f3a91)
  seat class:  student
  api version: 2.1
```

`bot.toml` is where the arena discovers your agent:

```toml
[bot]
name = "pathfinder"
entry = "bots.pathfinder.agent:PathfinderAgent"
api_version = "2.1"

[meta]
author = "astro"
```

### 2. Run against the baseline agents

The arena ships three reference opponents: `random-bot` (picks legal moves uniformly), `greedy-router` (always claims the longest available route), and `ticket-hoarder` (draws destination tickets aggressively). Run a best-of-100 match against all three:

```bash
$ ttr-arena match pathfinder --vs baselines --games 100 --seed 42
Loading arena config … ok
Opponents: random-bot, greedy-router, ticket-hoarder (4-player games)

Playing 100 games  [████████████████████████] 100/100  (0:00:37)

Results written to leaderboard.json
Replays written to replays/2026-09-16T14-22-08/
```

A per-game summary streams as it runs; the final tally is persisted to `leaderboard.json`.

### 3. Read the leaderboard

```bash
$ cat leaderboard.json
```

```json
{
  "match_id": "m_20260916_142208",
  "seed": 42,
  "games": 100,
  "standings": [
    { "bot": "greedy-router",  "wins": 41, "avg_score": 108.2, "avg_rank": 1.7 },
    { "bot": "pathfinder",     "wins": 23, "avg_score":  94.6, "avg_rank": 2.3 },
    { "bot": "ticket-hoarder", "wins": 21, "avg_score":  91.8, "avg_rank": 2.5 },
    { "bot": "random-bot",     "wins": 15, "avg_score":  62.1, "avg_rank": 3.5 }
  ],
  "pathfinder": {
    "wins": 23,
    "losses": 77,
    "avg_score": 94.6,
    "score_breakdown": {
      "routes": 78.4,
      "longest_path_bonus": 2.1,
      "tickets_completed": 21.3,
      "tickets_failed": -7.2
    }
  }
}
```

You beat `random-bot` comfortably and edged out `ticket-hoarder`, but `greedy-router` is winning nearly twice as often. The `score_breakdown` is the tell: your route points are healthy, but `tickets_failed: -7.2` is dragging you down, and your `longest_path_bonus` is almost nonexistent.

### 4. Interpret a losing game

Inspect a specific loss. The `replay show` command reconstructs the final board and your unfinished tickets:

```bash
$ ttr-arena replay show replays/2026-09-16T14-22-08/game_017.jsonl --focus pathfinder
Game 17 — pathfinder finished RANK 3 (score 71)

Final tickets:
  ✓ Denver → El Paso        (+4)   completed turn 12
  ✗ Seattle → New York      (-20)  INCOMPLETE  (missing: Chicago–New York)
  ✗ Portland → Nashville    (-13)  INCOMPLETE  (missing: Salt Lake–Denver)

Turn 12 note: drew 2 destination tickets while holding 3 unfinished.
Turn 15 note: opponent greedy-router claimed Chicago–New York (needed).
```

Two failed long-haul tickets cost you 33 points, and you drew *more* tickets on turn 12 while three were still open. Worse, a route you needed (`Chicago–New York`) was claimed by `greedy-router` on turn 15 — you waited too long to secure a contested edge.

### 5. Improve the strategy

The diagnosis points to two concrete changes in `agent.py`:

1. **Stop hoarding tickets.** Don't draw new destination tickets while more than one is unfinished.
2. **Prioritize contested routes.** Claim routes on your active tickets earlier, favoring double-route bottlenecks that opponents are eyeing.

```python
def decide(self, state):
    open_tickets = [t for t in self.tickets if not state.is_complete(t)]

    # Change 1: only draw tickets when the board is nearly clear
    if state.can_draw_tickets and len(open_tickets) <= 1:
        return DrawTickets()

    # Change 2: claim the highest-priority needed route first,
    # breaking ties toward contested (single-remaining) segments
    needed = self.routes_for(open_tickets, state)
    claimable = [r for r in needed if state.can_claim(r)]
    if claimable:
        target = max(claimable, key=lambda r: (state.contested(r), r.length))
        return ClaimRoute(target)

    return DrawTrainCard(state.best_card_for(needed))
```

Re-run the same match with the same seed so the comparison is fair:

```bash
$ ttr-arena match pathfinder --vs baselines --games 100 --seed 42
...
Results written to leaderboard.json

$ ttr-arena leaderboard diff --against m_20260916_142208
bot          wins        avg_score       tickets_failed
pathfinder   23 → 38     94.6 → 111.4    -7.2 → -1.8
greedy-router 41 → 32     108.2 → 104.9
```

Wins jumped from 23 to 38 and your ticket-failure penalty nearly vanished — enough to move `pathfinder` into first place against the baselines. From here, replay a few of your remaining losses (`ttr-arena replay show … --focus pathfinder`) to find the next weakness to tune.

---

**Tip:** Keep `--seed` fixed while iterating so score changes reflect your strategy, not luck. Once you're happy, run a final unseeded `--games 500` to confirm the gains hold across random deals.