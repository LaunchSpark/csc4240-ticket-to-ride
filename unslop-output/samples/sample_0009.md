# Architecture

The system is organized as four cooperating subsystems: a **game engine** that owns the rules and canonical state, an **agent runner** that turns policies into validated moves, a **tournament orchestrator** that schedules and supervises many games, and a **results logger** that persists everything durably for later analysis. Each subsystem talks to its neighbors through narrow, well-defined interfaces so that any one of them can be swapped, tested, or scaled independently.

## Module Layout

```
                        ┌───────────────────────────────────────┐
                        │        tournament/orchestrator          │
                        │  • match scheduling & pairings          │
                        │  • seat assignment / seed control       │
                        │  • concurrency & lifecycle supervision  │
                        └───────────────┬─────────────────────────┘
                                        │ spawns N games
                                        │ (config, seed, roster)
                                        ▼
        ┌───────────────────────────────────────────────────────────┐
        │                      game/engine                           │
        │   ┌───────────────┐   ┌───────────────┐   ┌──────────────┐ │
        │   │ state.py       │   │ rules.py      │   │ transition.py│ │
        │   │ (immutable     │   │ (legal-move   │   │ (apply +     │ │
        │   │  GameState)    │   │  generation,  │   │  advance)    │ │
        │   │                │   │  validation)  │   │              │ │
        │   └───────────────┘   └───────────────┘   └──────────────┘ │
        └───────▲───────────────────────────┬───────────────────────┘
                │ observation                │ Action
                │ (per-seat view)            │ (candidate move)
                │                            ▼
        ┌───────┴─────────────────────────────────────────────────┐
        │                     agent/runner                          │
        │   ┌──────────────┐   ┌───────────────┐  ┌──────────────┐ │
        │   │ protocol.py   │   │ sandbox.py    │  │ policies/    │ │
        │   │ (Agent iface) │   │ (timeouts,    │  │ (random,     │ │
        │   │               │   │  isolation)   │  │  greedy, ml) │ │
        │   └──────────────┘   └───────────────┘  └──────────────┘ │
        └───────────────────────────────┬───────────────────────────┘
                                         │ turn records, outcomes,
                                         │ violations, timings
                                         ▼
        ┌───────────────────────────────────────────────────────────┐
        │                      results/logger                        │
        │   • append-only event stream (JSONL / SQLite)              │
        │   • per-match summaries + aggregate standings              │
        │   • replay serialization                                   │
        └───────────────────────────────────────────────────────────┘
```

The dependency arrows point in one direction only: the orchestrator depends on the engine and runner; the runner depends on the engine's public types; and the logger depends on nothing but the event schemas emitted to it. The engine has **no** knowledge of tournaments, agents, or logging — it is a pure rules kernel. This acyclic layering is what keeps the engine deterministic and trivially unit-testable.

## Responsibilities

**`game/engine`** is the single source of truth. `state.py` defines an immutable `GameState` (board, decks, per-player hands, scoring markers, and whose turn it is). `rules.py` is a pure function library: given a state it can enumerate the set of legal actions for the active seat, and given a state-plus-action it can decide whether that action is legal and why. `transition.py` applies a validated action to produce the *next* immutable state. Because states are immutable and transitions are pure, any turn can be replayed byte-for-byte from a seed.

**`agent/runner`** adapts arbitrary decision-making policies to the engine. `protocol.py` defines the minimal `Agent` interface — essentially `choose(observation) -> Action`. `sandbox.py` wraps each agent call with resource limits (wall-clock timeout, memory ceiling, exception trapping) so a misbehaving or slow policy degrades gracefully into a forfeit or a default no-op rather than crashing the match. The runner is deliberately thin: it never mutates game state and never judges legality itself; it only ferries observations out and candidate actions back.

**`tournament/orchestrator`** owns scheduling. It builds the pairing table (round-robin, Swiss, or single-elimination), assigns seats, fixes the RNG seed per game for reproducibility, and drives the main game loop. It can run games concurrently in a worker pool, supervising each for hangs and restarting or abandoning as policy dictates. It is the only component that holds a mutable, evolving state reference for a live game.

**`results/logger`** is a write-mostly sink. Every turn, every rule violation, every final score, and every timing sample is appended to an event stream. From that stream it derives per-match summaries and tournament-wide standings, and it can serialize a full replay. Keeping it append-only means logging never blocks or corrupts a game in progress.

## Data Flow of a Single Turn

A turn is a request/response cycle mediated entirely by the orchestrator; the agent never touches canonical state directly.

1. **State generation.** The orchestrator holds the current `GameState`. It asks the engine (`rules.py`) to compute the **legal action set** for the active seat and to build a **per-seat observation** — a redacted projection of the state that hides information the seat shouldn't see (e.g. opponents' concealed hands, the order of face-down decks). The legal action set may be shipped alongside the observation or withheld, depending on whether the tournament is testing an agent's own legality reasoning.

2. **Decision.** The orchestrator hands the observation to the `agent/runner`, which invokes the seated policy inside its sandbox. The runner returns exactly one candidate `Action` (or a sentinel — timeout, exception, resignation). Timing for the call is captured here.

3. **Action validation.** The candidate `Action` goes back to the engine. `rules.py` validates it against the *authoritative* full state — never against the redacted observation — guarding against illegal, malformed, or impossible moves. Validation is the trust boundary: nothing an agent returns is believed until the engine confirms it. On failure the engine returns a typed violation reason; the orchestrator applies the tournament's illegal-move policy (default action, penalty, or forfeit) and the violation is logged.

4. **Transition.** On success, `transition.py` applies the validated action and returns a new immutable `GameState`. The old state is retained for replay; the orchestrator advances its reference to the new one.

5. **Logging & advance.** The orchestrator emits a turn record — observation digest, chosen action, validation result, resulting state hash, and timing — to `results/logger`. It then checks the engine's terminal predicate. If the game has ended, final scores are logged and the match closes; otherwise the active seat rotates and the cycle repeats from step 1.

Because state generation, validation, and transition are all pure functions of an immutable state and a fixed seed, an entire game is a deterministic fold over its action sequence — which is precisely what lets the logger's replay reconstruct any match exactly.