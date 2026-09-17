# Ticket to Ride Bot Arena

A lightweight Python framework for running Ticket to Ride bots against each other and ranking them.

## Overview

Bot Arena runs automated tournaments between AI agents that play Ticket to Ride. Each bot implements a simple decision interface; the framework handles the game rules, turn order, scoring, and match results — so you can focus on strategy.

## Features

- Full Ticket to Ride game engine (routes, tickets, train cards, scoring)
- Simple `Bot` interface — implement one method to compete
- Round-robin and head-to-head tournament modes
- Reproducible matches via seeded randomness
- Match logs and final standings with win rates and average scores

## Installation

```bash
git clone https://github.com/yourname/ttr-bot-arena.git
cd ttr-bot-arena
pip install -e .
```

## Quick Start

Write a bot by subclassing `Bot`:

```python
from ttr_arena import Bot

class GreedyBot(Bot):
    def act(self, state):
        # Return the highest-value legal move
        return max(state.legal_moves(), key=state.value)
```

Run a tournament:

```python
from ttr_arena import Tournament
from mybots import GreedyBot, RandomBot

results = Tournament([GreedyBot(), RandomBot()], games=100, seed=42).run()
results.print_standings()
```

Or from the command line:

```bash
python -m ttr_arena --bots mybots.GreedyBot mybots.RandomBot --games 100
```

## The Bot Interface

Each bot receives a read-only `GameState` and returns a legal `Move`:

| Method | Description |
|--------|-------------|
| `act(state)` | Required. Return your chosen move for the current turn. |
| `on_game_start(state)` | Optional. Called once at the start of each game. |
| `on_game_end(result)` | Optional. Called once when a game finishes. |

Illegal moves are rejected and cost the bot its turn.

## Scoring

Bots are ranked by wins, with ties broken by average final score across all games. Standings report win rate, total points, and completed routes.

## Project Structure

```
ttr_arena/
  engine/      # game rules and state
  bots/        # example bots
  tournament/  # match runner and scoring
```

## License

MIT — course project, provided as-is.