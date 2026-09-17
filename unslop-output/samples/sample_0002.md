## Getting Started

Welcome! This guide gets you from zero to your first bot match in about five minutes. All you need is **Python 3.10+** and **git** installed.

### 1. Clone the repo

```bash
git clone https://github.com/your-org/ticket-to-ride-bots.git
cd ticket-to-ride-bots
```

### 2. Set up a virtual environment

Creating a virtualenv keeps this project's dependencies isolated from the rest of your system.

```bash
python -m venv .venv
```

Activate it:

```bash
# macOS / Linux
source .venv/bin/activate

# Windows (PowerShell)
.venv\Scripts\Activate.ps1
```

You'll know it worked when you see `(.venv)` at the start of your terminal prompt.

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

> **Tip:** If `pip` feels slow, upgrade it first with `pip install --upgrade pip`.

### 4. Run your first match

Two starter bots ship with the repo. Pit them against each other:

```bash
python -m ttr.play --p1 bots.random_bot --p2 bots.greedy_bot
```

You should see the game log stream by, ending with something like:

```
Match complete!
  greedy_bot ....... 87 points  🏆
  random_bot ....... 42 points
```

That's it — you just ran a full Ticket to Ride bot match. 🎉

### Next steps

- **Watch it live:** add `--render` to see the board update turn by turn.
- **Write your own bot:** copy `bots/random_bot.py` to `bots/my_bot.py` and start editing the `choose_action()` method.
- **Test your bot:** run it with `python -m ttr.play --p1 bots.my_bot --p2 bots.greedy_bot`.

Stuck? Check the [Troubleshooting](#troubleshooting) section or open an issue — we're happy to help.