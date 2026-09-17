# Ticket to Ride Bot Evaluation Platform

A testing ground for Ticket to Ride bots. Point it at your agents, run them through repeatable matches, and get clear numbers on how they actually play — not just who won, but why. The platform handles game orchestration, rule enforcement, and scoring so you can focus on strategy rather than plumbing. Whether you're tuning a heuristic, training a learning agent, or just settling an argument about the best opening route, it gives you a consistent, reproducible arena to do it in.

## Features

- **Deterministic match engine** — full implementation of Ticket to Ride rules with seedable shuffles, so any game can be replayed exactly.
- **Pluggable bot interface** — drop in a new agent by implementing a small, well-documented API; no framework lock-in.
- **Tournament runner** — schedule round-robins, brackets, or bulk head-to-head series across any number of bots.
- **Rich scoring & stats** — win rates, average final scores, route completion, longest-path frequency, and per-turn decision breakdowns.
- **Match replays** — step through any recorded game move by move to see where a bot made its calls.
- **Reproducible configs** — declare players, seeds, and map variants in a single file for shareable, rerunnable experiments.
- **Parallel execution** — run large batches concurrently to keep evaluation fast.
- **Baseline opponents included** — random, greedy, and route-focused reference bots to benchmark against out of the box.