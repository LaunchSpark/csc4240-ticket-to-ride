## Why Ticket to Ride Is Secretly a Nightmare for Bots

At first glance, *Ticket to Ride* looks friendly: collect colored train cards, claim railway routes between cities, and try to connect the destinations on your secret tickets. Grandparents love it. So why does teaching a computer to play it well turn into a genuinely hard AI problem? Let's break it down.

### 1. You Can't See the Whole Board (Hidden Information)

Chess and checkers are **perfect information** games — everything you need to know is sitting right there on the board. Ticket to Ride is not so polite.

- You can't see your opponents' **destination tickets**, so you don't know where they're secretly trying to go.
- You can't see the cards in their **hands**, so you don't know if they're one card away from snatching the route you've been eyeing.

A bot has to play detective. If your rival keeps hoarding cards and never builds, they might be saving up for a long, juicy route — maybe the coast-to-coast one worth a pile of points. Good human players *infer* this. Bots have to model these invisible possibilities, essentially reasoning about a game state they can only guess at. That's the difference between "calculate the one true answer" and "make a smart bet under fog."

### 2. Thinking Ten Moves Ahead (Long-Term Route Planning)

Claiming a single route is easy. Claiming the *right sequence* of routes to actually connect Los Angeles to New York — while someone else is chipping away at the map — is where it gets spicy.

The map is basically a **graph**: cities are dots, routes are the lines between them, and each line has a length and a color requirement. To complete a ticket, your bot has to find a path through that graph, then plan which segments to grab and in what order. The catch:

- Every route an opponent claims can **sever your plan**, forcing an expensive detour.
- Building requires the *right colored cards in the right amounts*, so your plan depends on cards you may not have drawn yet.
- Points come at the very end, so a move that feels useless now might be the linchpin of a winning route later.

This is planning under a moving, adversarial deadline. A greedy bot that just grabs whatever route looks good *right now* will get boxed in and lose to anyone thinking about the whole journey.

### 3. The Big Gamble: Build Now or Draw More Tickets?

Here's the tension that makes the game sing — and makes bots sweat.

You can spend a turn **claiming a route** (guaranteed progress toward what you already have) or **drawing new destination tickets** (a gamble that could hand you big points... or dead weight you can't complete in time).

- Draw tickets **too early**, and you might commit to routes you can't finish before the game ends — and unfinished tickets *cost* you points. Ouch.
- Draw tickets **too late**, and you leave easy points on the table that a bolder player scooped up.
- Claim routes **too aggressively** without a plan, and you burn cards on track that doesn't connect anything useful.

This is a classic **risk-versus-reward** and **exploration-versus-exploitation** tradeoff, the same family of problems that shows up all over AI. There's no formula that's always right; the best choice depends on the hidden state, the map, and how close the game is to ending. A bot has to weigh a sure thing against a gamble, over and over, with incomplete information.

### Putting It Together

So a strong Ticket to Ride bot has to juggle *all three at once*: reason about what it can't see, plan long chains of moves across a graph that opponents keep vandalizing, and constantly gamble on whether to lock in progress or reach for more. Any one of these is a solid AI exercise. Stacked together, they turn a cozy family board game into a delightfully tricky playground for game AI — which is exactly why it's such a fun problem to tackle. 🚂