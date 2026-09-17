## Evaluation & Scoring

Bots are evaluated in a **round-robin tournament**: every bot plays against every other bot exactly once as a pairing. To smooth out the variance introduced by shuffled decks and route deals, each pairing plays **100 games**, with starting player alternating between games to neutralize first-move advantage.

### How points are earned

Within a single game, a bot accumulates points from two sources:

- **Completed routes** — Each destination route a bot successfully connects at game end awards its face value. Uncompleted routes are *not* scored here; they only affect a bot's own game total, not the metrics below.
- **Longest-path bonus** — The bot holding the single longest continuous path of claimed track at the end of the game receives a fixed **+10** bonus. Ties split the bonus evenly among the tied bots.

A bot's **game score** is the sum of its completed-route points and any longest-path bonus for that game. (Track-length points claimed during play are tracked separately and are not part of the evaluation score.)

### Aggregation and ranking

After all pairings finish, results are aggregated per bot across every game it played:

1. **Average score** — the bot's mean game score across all 100-game pairings it participated in. This is the primary ranking key.
2. **Win rate** — the fraction of games the bot finished with the highest game score. This is used **only as a tiebreaker** when two bots have identical (or rounded-equal) average scores.

Bots are sorted by average score descending; where averages tie, the higher win rate ranks first.

### Example results

| Rank | Bot            | Games | Avg Score | Win Rate |
|-----:|----------------|------:|----------:|---------:|
| 1    | `pathfinder-v3` |   500 |     87.4  |   0.612  |
| 2    | `greedy-router` |   500 |     81.9  |   0.548  |
| 3    | `longhaul-ai`   |   500 |     79.2  |   0.503  |
| 4    | `balanced-bot`  |   500 |     79.2  |   0.471  |
| 5    | `random-baseline` | 500 |    42.6  |   0.088  |

In this example, `longhaul-ai` and `balanced-bot` post the same average score (79.2), so the tiebreaker applies: `longhaul-ai` ranks higher on the strength of its **0.503** win rate versus `balanced-bot`'s **0.471**.