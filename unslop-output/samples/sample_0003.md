## Bot API Reference

All bots extend the abstract `Agent` base class and implement its three lifecycle methods. The game engine instantiates your agent once per match and invokes these callbacks in response to game events.

### `Agent` methods

#### `choose_action(state)`

Called on each of the bot's turns. This is the only method a bot **must** override; it drives all decision-making.

| Parameter | Type | Description |
|-----------|------|-------------|
| `state` | `GameState` | An immutable snapshot of the board from this bot's perspective, including the player's hand, visible face-up cards, remaining train pieces, claimed routes, and current scores. |

**Returns:** `Action` — one of the concrete action types (`DrawCards`, `ClaimRoute`, or `DrawTickets`). The action must be legal given `state`; returning an illegal or malformed action forfeits the turn.

**Raises:** May raise nothing by contract. Uncaught exceptions are treated as a forfeited turn and logged by the engine.

#### `on_game_start(player_id)`

Called once before the first turn. Use it to record the bot's seat and initialize any per-match internal state.

| Parameter | Type | Description |
|-----------|------|-------------|
| `player_id` | `int` | The bot's seat index (`0`-based) for this match. Stable for the entire game. |

**Returns:** `None`.

#### `on_game_end(result)`

Called once after the final turn. Use it to release resources, persist statistics, or update a learning model.

| Parameter | Type | Description |
|-----------|------|-------------|
| `result` | `GameResult` | Final outcome, including `result.winner` (`int`), `result.scores` (`dict[int, int]`), and `result.longest_route_holder` (`int \| None`). |

**Returns:** `None`.

### Minimal example

```python
from ttr.agent import Agent
from ttr.actions import Action, DrawCards, ClaimRoute
from ttr.state import GameState, GameResult


class GreedyBot(Agent):
    """Claims the first affordable route, otherwise draws cards."""

    def on_game_start(self, player_id: int) -> None:
        self.player_id = player_id

    def choose_action(self, state: GameState) -> Action:
        for route in state.available_routes:
            if state.can_claim(route):
                return ClaimRoute(route)
        return DrawCards()

    def on_game_end(self, result: GameResult) -> None:
        won = result.winner == self.player_id
        print(f"Player {self.player_id} {'won' if won else 'lost'}")
```

Register the subclass with the engine (e.g. `engine.add_agent(GreedyBot())`) and the lifecycle methods are called automatically.