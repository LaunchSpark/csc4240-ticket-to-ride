## Evaluation & Scoring

Every bot in the pool is evaluated against every other bot in a **round-robin tournament**. For each unordered pairing, the two bots play **100 games**, alternating who moves first so that turn-order advantage is evenly distributed across the sample. This produces a large, symmetric body of results and keeps any single lucky game from distorting a bot's standing.

### How points are earned

Within each game, a bot accumulates points from two sources:

- **Completed routes** — every route (destination ticket) a bot fully connects by the end of the game contributes its face value. Incomplete routes are ignored rather than penalized, so the score reflects positive achievement only.
- **Longest-path bonus** — the bot holding the single longest continuous path of claimed track at the end of the game receives a fixed bonus. Ties on path length split the bonus evenly between the tied bots.

A bot's **game score** is the sum of its route points and any longest-path bonus. Scores are recorded per game so that both averages and win counts can be derived from the same raw data.

### Aggregation and ranking

After all pairings finish, results are aggregated per bot across every game it played:

1. **Average score** is the primary ranking key — the mean game score across all 100-game matches the bot participated in. Averaging (rather than summing) keeps the metric comparable even if the number of games per bot shifts as the pool changes.
2. **Win rate** is the tiebreaker, applied when two bots have average scores within the reporting precision. It is the fraction of individual games the bot won outright (a drawn game counts toward neither bot's wins).

Bots are sorted by descending average score, then descending win rate. The result is a single ordered leaderboard.

### Example results table

| Rank | Bot | Games | Avg. Score | Win Rate | Avg. Routes | Longest-Path Wins |
|-----:|-----------------|------:|-----------:|---------:|------------:|------------------:|
| 1 | `PathfinderV3` | 700 | 84.2 | 61.4% | 3.9 | 214 |
| 2 | `GreedyClaim` | 700 | 79.6 | 58.1% | 3.4 | 176 |
| 3 | `RouteWeaver` | 700 | 79.5 | 52.7% | 3.6 | 141 |
| 4 | `BlockerBot` | 700 | 72.1 | 49.0% | 2.8 | 198 |
| 5 | `LongHaul` | 700 | 70.8 | 44.3% | 2.5 | 233 |
| 6 | `RandomWalk` | 700 | 41.3 | 12.9% | 1.4 | 61 |

In this example, `RouteWeaver` and `GreedyClaim` post nearly identical average scores (79.5 vs. 79.6), so the tiebreaker decides their order: `GreedyClaim`'s higher win rate (58.1% vs. 52.7%) places it second. Note also that `LongHaul` leads the field in longest-path wins without leading in average score — collecting the bonus consistently is not enough on its own to top the leaderboard.