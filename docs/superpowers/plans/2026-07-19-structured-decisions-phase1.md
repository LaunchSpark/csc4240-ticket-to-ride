# Structured Bot Decisions (Phase 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the flat `act(view, legal_actions)` bot contract with typed, phase-scoped `BotDecision` objects and a `decide(decision)` contract, migrating the engine, all in-repo bots, the template, and the research replay wrappers in one branch.

**Architecture:** A new `engine/decisions.py` module defines frozen decision/option dataclasses built from the *existing* legal-action enumeration (order unchanged). `Player` constructs the right decision per phase, calls `decide`, and enforces selection by **object identity** — an illegal return raises `IllegalActionError` (or substitutes + ERROR-logs + counts a runtime failure under managed execution). Bots keep their internal heuristics; their `act` dispatch becomes a `match` over decision types.

**Tech Stack:** Python 3.12+, stdlib `dataclasses`/`types.MappingProxyType`, `unittest` (run via `uv run`), pyright (via `npx -y pyright`), marimo notebook bots.

**Spec:** `docs/superpowers/specs/2026-07-19-structured-legal-options-design.md`

**Scope:** This plan is the spec's **Phase 1** plus the small code changes Phase 1 mechanically forces in the research wrappers (they sit between `Player` and bots, so they must speak `decide` for the suite to stay green). **Not in this plan:** wire protocol v2 (spec Phase 2 — separate plan; until then remote sidecar seats fail over cleanly to the in-process fallback bot), dataset regeneration/retraining (spec Phase 3 — an operational run after this lands), tunnels (Phase 4).

## Global Constraints

- No backward-compatibility machinery: no engine dispatch shim, no `LegacyBotAdapter` retention plan (the file and its standalone test survive until Phase 2 deletes them, but `Player` stops using it).
- `decision.actions` must contain each selectable leaf **exactly once**, preserving today's deterministic order: (1) blind draw; (2) face-up draws in market order; (3) route payments in map-route and payment-enumeration order; (4) destination-ticket draw; (5) pass when it is the only choice. Keep-ticket decisions preserve `legal_keep_actions` order.
- Selection is checked by **identity** (`id(leaf)`), never value equality.
- Decisions are deeply immutable in practice: frozen dataclasses whose fields are frozen dataclasses, tuples, or `MappingProxyType`.
- Every new public decision/option/contract type gets a substantial behavioral docstring **in the same commit that introduces it**.
- `pass_action` is `None` whenever any other action is legal.
- Seeded replays must be byte-identical through the new dispatch (existing `test_replay`, `test_engine_determinism` must pass unmodified in behavior).
- Test commands: full suite `uv run test`; single module `uv run python -m unittest quality.tests.<module> -v` (or `external.tests.<module>` for `integrations/external/tests`).
- Type check: `npx -y pyright` (pyright 1.1.411 is available via npx; the repo has `pyrightconfig.json`). Before Task 1, record the baseline error count on `main`; no task may add new errors.

## File Structure

| File | Role in this plan |
|---|---|
| `services/native-runtime/src/ticket_to_ride/engine/decisions.py` | **Create.** All decision/option types, `DecisionId`, `DrawResult`, `IllegalActionError`, and the three `build_*_decision` functions. `actions.py` keeps only leaves + enumeration. |
| `quality/tests/test_engine_decisions.py` | **Create.** Contract tests for containers, builders, ordering, immutability, docstrings. |
| `quality/tests/test_player_decide.py` | **Create.** Player-level dispatch tests: identity enforcement, DecisionId determinism, setup vs turn ticket minimums, second-draw context. |
| `services/native-runtime/src/ticket_to_ride/engine/player.py` | **Modify.** `__choose` → decision construction + `__select` (identity check, loud failure), `DrawResult` from draws, decision-scoped ticket offers, drop `LegacyBotAdapter` wrap. |
| `services/native-runtime/src/ticket_to_ride/engine/game.py` | **Modify.** Pass `round_number` through `attach`. |
| `services/native-runtime/src/ticket_to_ride/engine/state/views.py` | **Modify.** Remove `decision`/`ticket_offer` from `PlayerView`. |
| `services/native-runtime/src/ticket_to_ride/engine/replay.py` | **Modify.** `ScriptedBot.decide` resolves recorded actions to canonical leaves. |
| `services/native-runtime/src/ticket_to_ride/runtime/cli.py` | **Modify.** `BootstrapRandomActionBot` → `decide`. |
| `services/native-runtime/src/ticket_to_ride/backend/runtime/round_runtime.py` | **Modify.** `ManagedSeatInterface.decide`, `on_illegal_action`, illegal-action counting. |
| `services/native-runtime/src/ticket_to_ride/backend/runtime/executor.py` | **Modify.** `BotApiExecutor` cleanly rejects `decide` until wire v2. |
| `services/native-runtime/src/ticket_to_ride/backend/models.py`, `backend/runtime/managed_match_runtime.py` | **Modify.** `illegalActions` on seat results; aggregate `runtimeFailures`. |
| `integrations/external/contracts/base_bot.py` | **Modify.** `ActionBot` abstract method becomes `decide`. |
| `integrations/external/bots/*.py` (7 bots), `integrations/external/templates/bots/build_your_bot_here.py` | **Modify.** `match`-dispatch `decide`; keep internal helpers. |
| `operations/research/decision_export.py`, `xg_data_pump.py`, `xg_curriculum.py` | **Modify.** Observer wrappers speak `decide`; export rows gain `decision_type` + `decision_id`. |

Sequencing that keeps every commit green: decisions module first (Tasks 1–2); each bot gains `decide` *alongside* its existing `act` (Tasks 3–7) with tests driving `decide` directly via the builders; then one atomic engine cutover flips `Player` to `decide` (Task 8); managed-runtime failure policy (Task 9); template rewrite (Task 10); contract cleanup deletes every `act` (Task 11).

---

### Task 1: Decision identity, results, option containers, and the error type

**Files:**
- Create: `services/native-runtime/src/ticket_to_ride/engine/decisions.py`
- Test: `quality/tests/test_engine_decisions.py`

**Interfaces:**
- Produces: `DecisionId(round_number: int, turn_index: int, phase_index: int)` (frozen, ordered); `DrawResult(action: DrawBlind | DrawFaceUp, card: str)`; `FaceUpDrawIndex(slots: tuple[DrawFaceUp | None, ...])` with `[i]`, `len()`, `.available`; `DrawOptions(blind, face_up)`; `RouteClaimOptions(route, payments)`; `ClaimOptions(entries, by_route_id)` (a `Sequence`); `DrawTicketOptions(draw)`; `KeepTicketOptions(available, by_indices)`; `IllegalActionError(player_id, decision, returned)`.

- [ ] **Step 0: Record the pyright baseline**

Run: `npx -y pyright 2>&1 | tail -3` and note the error/warning counts in the task notes. Later tasks compare against this.

- [ ] **Step 1: Write the failing tests**

Create `quality/tests/test_engine_decisions.py`:

```python
import dataclasses
import unittest
from types import MappingProxyType

from ticket_to_ride.engine.actions import ClaimRoute, DrawBlind, DrawFaceUp
from ticket_to_ride.engine import decisions as decisions_module
from ticket_to_ride.engine.decisions import (
    ClaimOptions, DecisionId, DrawOptions, DrawResult, DrawTicketOptions,
    FaceUpDrawIndex, IllegalActionError, KeepTicketOptions, RouteClaimOptions,
)


class DecisionIdTests(unittest.TestCase):
    def test_orders_by_position_within_a_turn(self):
        turn = DecisionId(round_number=0, turn_index=4, phase_index=0)
        follow_up = DecisionId(round_number=0, turn_index=4, phase_index=1)
        self.assertLess(turn, follow_up)

    def test_is_frozen(self):
        decision_id = DecisionId(0, 0, 0)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            decision_id.turn_index = 9


class FaceUpDrawIndexTests(unittest.TestCase):
    def test_slots_align_to_market_and_available_skips_gaps(self):
        second = DrawFaceUp(1, "R")
        index = FaceUpDrawIndex(slots=(None, second, None))
        self.assertEqual(len(index), 3)
        self.assertIsNone(index[0])
        self.assertIs(index[1], second)
        self.assertEqual(index.available, (second,))


class ImmutabilityTests(unittest.TestCase):
    def test_all_public_dataclasses_are_frozen(self):
        for name in dir(decisions_module):
            obj = getattr(decisions_module, name)
            if isinstance(obj, type) and dataclasses.is_dataclass(obj):
                self.assertTrue(
                    obj.__dataclass_params__.frozen,
                    f"{name} must be a frozen dataclass",
                )

    def test_claim_options_mapping_is_read_only(self):
        options = ClaimOptions(entries=(), by_route_id=MappingProxyType({}))
        with self.assertRaises(TypeError):
            options.by_route_id["x"] = None


class DocstringTests(unittest.TestCase):
    def test_every_public_type_documents_its_behavior(self):
        public = [
            getattr(decisions_module, name)
            for name in dir(decisions_module)
            if not name.startswith("_")
        ]
        for obj in public:
            if isinstance(obj, type) or callable(obj):
                self.assertTrue(
                    (obj.__doc__ or "").strip(),
                    f"{obj!r} needs a non-empty docstring",
                )


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run python -m unittest quality.tests.test_engine_decisions -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ticket_to_ride.engine.decisions'`

- [ ] **Step 3: Create `decisions.py` with the identity/option layer**

```python
"""Structured bot decisions: phase-scoped option menus over canonical actions.

The engine asks a bot for one choice at a time by calling
``decide(decision)`` with one of the concrete types in ``BotDecision``
(added in this module alongside the builders). Every decision carries:

- ``decision_id`` — the game position this decision belongs to;
- ``state`` — a :class:`PlayerView` of everything the seat may know now;
- ``actions`` — the flat tuple of canonical selectable leaves, in the
  engine's deterministic enumeration order (blind draw; face-up draws in
  market order; route payments in map-route and payment-enumeration order;
  destination-ticket draw; pass only when nothing else is legal).

The concrete decision type adds navigation (``draws``, ``claims``,
``choices`` …) whose entries are the *same objects* as in ``actions``.
A bot must return one of those canonical leaves. The engine checks
membership by identity — a value-equal reconstruction is an illegal
return and raises :class:`IllegalActionError` (or, under managed
execution, substitutes, logs at ERROR, and counts a runtime failure).
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal, Mapping, Optional, Sequence, Union

from ticket_to_ride.engine.actions import (
    Action, ClaimRoute, DrawBlind, DrawFaceUp, DrawTickets, KeepTickets, Pass,
)
from ticket_to_ride.engine.state.decks import DestinationTicket
from ticket_to_ride.engine.state.map import Route
from ticket_to_ride.engine.state.views import PlayerView


@dataclass(frozen=True, order=True)
class DecisionId:
    """Where in the game a decision happened, derived from position.

    ``round_number`` is the managed-match round (0 for single games),
    ``turn_index`` the global 0-based turn counter, ``phase_index`` 0 for
    the turn-opening decision and 1 for a follow-up (second draw, keep
    tickets, and later tunnel responses). The setup ticket keep — dealt
    before any turn exists — uses ``turn_index=-1, phase_index=1`` so it
    sorts before every turn decision.

    Identical seeded games produce identical id sequences regardless of
    threading, because ids come from position, not a counter. They are
    unique per (match, seat), totally ordered within a turn, and (in wire
    protocol v2) used to reject stale remote responses.
    """

    round_number: int
    turn_index: int
    phase_index: int


@dataclass(frozen=True)
class DrawResult:
    """The card a just-applied draw produced.

    ``action`` is the canonical leaf the bot selected; ``card`` is the
    color that actually arrived. For a face-down draw the card is private
    information: it appears only in the acting player's decision, and any
    serialization of decision envelopes for non-acting seats (export,
    replay tooling, spectator views) must scrub it.
    """

    action: "DrawBlind | DrawFaceUp"
    card: str


@dataclass(frozen=True)
class FaceUpDrawIndex(Sequence["DrawFaceUp | None"]):
    """Face-up draw leaves indexed by their actual market slot.

    ``index[i]`` is the legal :class:`DrawFaceUp` for market slot ``i`` or
    ``None`` when that slot is not currently takeable (empty slot, or a
    locomotive during the second draw). Slots are never compacted, so an
    index always means the same physical card position. ``available``
    lists the legal leaves in market order.
    """

    slots: "tuple[DrawFaceUp | None, ...]"

    def __getitem__(self, index):
        return self.slots[index]

    def __len__(self) -> int:
        return len(self.slots)

    @property
    def available(self) -> "tuple[DrawFaceUp, ...]":
        """Every legal face-up draw leaf, in market order."""
        return tuple(leaf for leaf in self.slots if leaf is not None)


@dataclass(frozen=True)
class DrawOptions:
    """Train-card draw menu for one decision.

    ``blind`` is the :class:`DrawBlind` leaf, or ``None`` when the draw
    and discard piles are both empty. ``face_up`` indexes the takeable
    market cards by actual market slot (see :class:`FaceUpDrawIndex`).
    """

    blind: "DrawBlind | None"
    face_up: FaceUpDrawIndex


@dataclass(frozen=True)
class RouteClaimOptions:
    """One claimable route and every legal way to pay for it.

    ``payments`` holds the canonical :class:`ClaimRoute` leaves in the
    deterministic payment-enumeration order; each appears exactly once
    across the whole decision. Example::

        best = max(route_options.payments, key=payment_utility)
        return best
    """

    route: Route
    payments: "tuple[ClaimRoute, ...]"


@dataclass(frozen=True)
class ClaimOptions(Sequence[RouteClaimOptions]):
    """Every route the acting player can claim right now.

    Sequence access (``claims[3]``) means the fourth *currently claimable*
    route in map-route order — not the fourth route on the map — and
    exists for ranking and display. Stable plans should use
    ``by_route_id``, which maps ``route_id`` to the same entries and
    raises ``KeyError`` for routes that are not currently claimable::

        payment = claims.by_route_id["Seattle-Portland-1"].payments[0]

    Unlike ``decision.state.routes`` (every route on the board), only
    claimable routes appear here.
    """

    entries: tuple[RouteClaimOptions, ...]
    by_route_id: Mapping[str, RouteClaimOptions]

    def __getitem__(self, index):
        return self.entries[index]

    def __len__(self) -> int:
        return len(self.entries)


@dataclass(frozen=True)
class DrawTicketOptions:
    """The known choice to request a destination-ticket offer.

    ``draw`` is the canonical :class:`DrawTickets` leaf, or ``None`` when
    the ticket deck cannot serve a 3-card offer. The offer itself is
    unknown until the engine deals it and sends a follow-up
    ``KeepTicketsDecision``.
    """

    draw: "DrawTickets | None"


@dataclass(frozen=True)
class KeepTicketOptions:
    """Every legal keep-subset of the current ticket offer.

    ``available`` preserves ``legal_keep_actions`` enumeration order.
    ``by_indices`` maps a sorted index tuple (e.g. ``(0, 2)``) to the same
    canonical leaf and raises ``KeyError`` for subsets below the minimum
    keep.
    """

    available: "tuple[KeepTickets, ...]"
    by_indices: "Mapping[tuple[int, ...], KeepTickets]"


class IllegalActionError(ValueError):
    """A bot returned an action that is not a canonical leaf of the
    current decision.

    Raised on the spot in notebooks, spectate, and direct engine use so a
    buggy bot fails at the decision that produced the bug, not turns
    later. The message names the decision type and id, the offending
    return value, and the complete legal menu.
    """

    def __init__(self, player_id: str, decision, returned) -> None:
        self.player_id = player_id
        self.decision = decision
        self.returned = returned
        super().__init__(
            f"Player {player_id} returned an illegal action for "
            f"{type(decision).__name__} {decision.decision_id}: {returned!r}. "
            f"Selections must be canonical leaves of decision.actions "
            f"(identity, not equality). Legal menu: {decision.actions!r}"
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run python -m unittest quality.tests.test_engine_decisions -v`
Expected: PASS (all four test classes)

- [ ] **Step 5: Pyright check**

Run: `npx -y pyright services/native-runtime/src/ticket_to_ride/engine/decisions.py`
Expected: no errors beyond the Task 1 Step 0 baseline for that file (a brand-new file should be clean).

- [ ] **Step 6: Commit**

```bash
git add services/native-runtime/src/ticket_to_ride/engine/decisions.py quality/tests/test_engine_decisions.py
git commit -m "feat(engine): decision identity, option containers, and IllegalActionError"
```

---

### Task 2: Decision types and builders

**Files:**
- Modify: `services/native-runtime/src/ticket_to_ride/engine/decisions.py` (append)
- Test: `quality/tests/test_engine_decisions.py` (append)

**Interfaces:**
- Consumes: Task 1 types; `legal_turn_actions`, `legal_second_draw_actions`, `legal_keep_actions` from `engine/actions.py` (unchanged).
- Produces:
  - `TurnDecision(decision_id, state, draws, claims, destination_tickets, pass_action, actions)`
  - `SecondDrawDecision(decision_id, state, first_draw, draws, actions)`
  - `KeepTicketsDecision(decision_id, state, source, offer, minimum_to_keep, choices, actions)`
  - `BotDecision = TurnDecision | SecondDrawDecision | KeepTicketsDecision`
  - `build_turn_decision(*, decision_id, state, legal_actions) -> TurnDecision`
  - `build_second_draw_decision(*, decision_id, state, first_draw, legal_actions) -> SecondDrawDecision`
  - `build_keep_tickets_decision(*, decision_id, state, source, offer, minimum_to_keep, legal_actions) -> KeepTicketsDecision`
  - All builders store `tuple(legal_actions)` verbatim as `actions` — same objects, same order — and every grouped leaf **is** (identity) a member of `actions`.

- [ ] **Step 1: Write the failing tests**

Append to `quality/tests/test_engine_decisions.py` (model the fixture on `quality/tests/test_engine_actions.py:11-21`):

```python
from ticket_to_ride.engine.actions import (
    DrawTickets, KeepTickets, Pass,
    legal_keep_actions, legal_second_draw_actions, legal_turn_actions,
)
from ticket_to_ride.engine.decisions import (
    KeepTicketsDecision, SecondDrawDecision, TurnDecision,
    build_keep_tickets_decision, build_second_draw_decision, build_turn_decision,
)
from ticket_to_ride.engine.player import Player
from ticket_to_ride.engine.state.game_context import GameContext
from ticket_to_ride.engine.state.views import PlayerView


class _StubInterface:
    def set_player(self, player):
        self.player = player

    def decide(self, decision):  # never called in these tests
        raise AssertionError


def _game_and_player(seed=11):
    context = GameContext(["p0", "p1"], seed=seed)
    players = [Player(f"p{i}", _StubInterface(), f"p{i}", "red") for i in range(2)]
    for p in players:
        p.attach(context, players)
    return context, players[0]


def _turn_decision(context, player):
    view = PlayerView(player.player_id, context, [player] + [p for p in []])
    ...
```

Use this exact final fixture instead (the view needs both players):

```python
def _decisions_fixture(seed=11, hand=None):
    context = GameContext(["p0", "p1"], seed=seed)
    players = [Player(f"p{i}", _StubInterface(), f"p{i}", "red") for i in range(2)]
    for p in players:
        p.attach(context, players)
    player = players[0]
    if hand:
        player.get_hand().update(hand)
    view = PlayerView(player.player_id, context, players)
    return context, players, player, view


class TurnDecisionBuilderTests(unittest.TestCase):
    def test_actions_is_the_legal_list_verbatim(self):
        _, _, player, view = _decisions_fixture(hand=["R"] * 4 + ["L"])
        legal = legal_turn_actions(player)
        decision = build_turn_decision(
            decision_id=DecisionId(0, 0, 0), state=view, legal_actions=legal,
        )
        self.assertEqual(decision.actions, tuple(legal))
        for stored, original in zip(decision.actions, legal):
            self.assertIs(stored, original)

    def test_grouped_leaves_are_canonical_and_exactly_once(self):
        _, _, player, view = _decisions_fixture(hand=["R"] * 4 + ["L"])
        legal = legal_turn_actions(player)
        decision = build_turn_decision(
            decision_id=DecisionId(0, 0, 0), state=view, legal_actions=legal,
        )
        canonical_ids = {id(a) for a in decision.actions}
        grouped = []
        if decision.draws.blind is not None:
            grouped.append(decision.draws.blind)
        grouped.extend(decision.draws.face_up.available)
        for route_options in decision.claims:
            grouped.extend(route_options.payments)
        if decision.destination_tickets.draw is not None:
            grouped.append(decision.destination_tickets.draw)
        if decision.pass_action is not None:
            grouped.append(decision.pass_action)
        self.assertEqual(len(grouped), len(decision.actions))
        self.assertEqual({id(a) for a in grouped}, canonical_ids)

    def test_claims_sequence_and_by_route_id_share_entries(self):
        _, _, player, view = _decisions_fixture(hand=["R"] * 4 + ["L"])
        decision = build_turn_decision(
            decision_id=DecisionId(0, 0, 0), state=view,
            legal_actions=legal_turn_actions(player),
        )
        self.assertGreater(len(decision.claims), 0)
        for route_options in decision.claims:
            self.assertIs(
                decision.claims.by_route_id[route_options.route.route_id],
                route_options,
            )
            self.assertGreater(len(route_options.payments), 0)

    def test_face_up_index_aligns_to_market_slots(self):
        context, _, player, view = _decisions_fixture()
        decision = build_turn_decision(
            decision_id=DecisionId(0, 0, 0), state=view,
            legal_actions=legal_turn_actions(player),
        )
        market = context.get_train_deck().get_face_up()
        self.assertEqual(len(decision.draws.face_up), len(market))
        for slot, leaf in enumerate(decision.draws.face_up):
            self.assertIsNotNone(leaf)
            self.assertEqual(leaf.index, slot)
            self.assertEqual(leaf.card, market[slot])

    def test_pass_action_is_none_when_anything_else_is_legal(self):
        _, _, player, view = _decisions_fixture()
        decision = build_turn_decision(
            decision_id=DecisionId(0, 0, 0), state=view,
            legal_actions=legal_turn_actions(player),
        )
        self.assertIsNone(decision.pass_action)

    def test_turn_decision_carries_no_first_draw_or_offer(self):
        _, _, player, view = _decisions_fixture()
        decision = build_turn_decision(
            decision_id=DecisionId(0, 0, 0), state=view,
            legal_actions=legal_turn_actions(player),
        )
        self.assertFalse(hasattr(decision, "first_draw"))
        self.assertFalse(hasattr(decision, "offer"))


class SecondDrawDecisionBuilderTests(unittest.TestCase):
    def test_locomotive_slots_are_none_and_phase_has_no_claims(self):
        context, _, player, view = _decisions_fixture()
        legal = legal_second_draw_actions(player)
        first = DrawResult(action=DrawBlind(), card="R")
        decision = build_second_draw_decision(
            decision_id=DecisionId(0, 0, 1), state=view,
            first_draw=first, legal_actions=legal,
        )
        self.assertIs(decision.first_draw, first)
        market = context.get_train_deck().get_face_up()
        for slot, card in enumerate(market):
            if card == "L":
                self.assertIsNone(decision.draws.face_up[slot])
        self.assertFalse(hasattr(decision, "claims"))
        self.assertFalse(hasattr(decision, "destination_tickets"))
        self.assertEqual(decision.actions, tuple(legal))


class KeepTicketsDecisionBuilderTests(unittest.TestCase):
    def test_offer_minimum_and_indices_lookup(self):
        context, _, player, view = _decisions_fixture()
        offer = tuple(context.get_ticket_deck().deal_unique(3))
        legal = legal_keep_actions(len(offer), 2)
        decision = build_keep_tickets_decision(
            decision_id=DecisionId(0, -1, 1), state=view, source="setup",
            offer=offer, minimum_to_keep=2, legal_actions=legal,
        )
        self.assertEqual(decision.offer, offer)
        self.assertEqual(decision.minimum_to_keep, 2)
        self.assertEqual(decision.source, "setup")
        self.assertEqual(decision.choices.available, tuple(legal))
        self.assertIs(
            decision.choices.by_indices[(0, 2)],
            next(a for a in decision.actions if a.indices == (0, 2)),
        )
        with self.assertRaises(KeyError):
            decision.choices.by_indices[(0,)]
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run python -m unittest quality.tests.test_engine_decisions -v`
Expected: FAIL with `ImportError: cannot import name 'TurnDecision'`

- [ ] **Step 3: Append decision types and builders to `decisions.py`**

```python
@dataclass(frozen=True)
class TurnDecision:
    """The turn-opening decision: claim, draw, take tickets, or pass.

    Emitted once at the start of every turn. All alternatives are already
    known, so route selection *and* payment selection happen inside this
    one decision — the engine only calls back again when applying the
    chosen action reveals new information (a drawn card, a dealt offer).

    ``pass_action`` is ``None`` whenever any other action is legal; pass
    appears only as the sole remaining choice, so ``return
    decision.pass_action`` is valid only after establishing nothing else
    is available. Example navigation::

        route_options = decision.claims.by_route_id[target_route_id]
        return max(route_options.payments, key=payment_utility)
    """

    decision_id: DecisionId
    state: PlayerView
    draws: DrawOptions
    claims: ClaimOptions
    destination_tickets: DrawTicketOptions
    pass_action: "Pass | None"
    actions: tuple[Action, ...]


@dataclass(frozen=True)
class SecondDrawDecision:
    """The second train-card pick, after the first draw was applied.

    Emitted only when the first draw did not end the turn (a face-up
    locomotive ends it immediately and produces no second decision).
    ``state`` already contains the first card in the hand and the
    refilled market; ``first_draw`` makes the transition explicit — for a
    blind first draw its ``card`` is the acting player's private
    information. Face-up locomotives are illegal here, so their market
    slots read ``None`` in ``draws.face_up``. Claims and ticket draws are
    not legal in this phase and do not appear as properties. When the
    decks are dry, ``actions`` holds a single ``Pass`` leaf.
    """

    decision_id: DecisionId
    state: PlayerView
    first_draw: DrawResult
    draws: DrawOptions
    actions: tuple[Action, ...]


@dataclass(frozen=True)
class KeepTicketsDecision:
    """Choose which destination tickets to keep from a dealt offer.

    Emitted after the engine deals an offer: during setup
    (``source="setup"``, ``minimum_to_keep=2``, id
    ``turn_index=-1, phase_index=1``) and after a turn-time
    ``DrawTickets`` (``source="turn"``, ``minimum_to_keep=1``,
    ``phase_index=1``). The offer and its keep rule live here, not on
    ``PlayerView``. Example::

        decision.choices.by_indices[(0, 2)]   # keep tickets 0 and 2
        decision.choices.available            # every legal keep-set
    """

    decision_id: DecisionId
    state: PlayerView
    source: Literal["setup", "turn"]
    offer: tuple[DestinationTicket, ...]
    minimum_to_keep: int
    choices: KeepTicketOptions
    actions: tuple[KeepTickets, ...]


BotDecision = Union[TurnDecision, SecondDrawDecision, KeepTicketsDecision]
"""The typed union a bot's ``decide`` receives.

Dispatch with ``match``; pyright flags any bot whose ``match`` does not
handle a newly added member (this is how ``TunnelDecision`` will announce
itself in Phase 4).
"""


def _draw_options(blind, face_up_by_slot, market_size) -> DrawOptions:
    """Group draw leaves into a market-slot-aligned :class:`DrawOptions`."""
    slots = tuple(face_up_by_slot.get(slot) for slot in range(market_size))
    return DrawOptions(blind=blind, face_up=FaceUpDrawIndex(slots=slots))


def build_turn_decision(*, decision_id: DecisionId, state: PlayerView,
                        legal_actions) -> TurnDecision:
    """Group a turn-opening legal-action list, order and objects intact.

    ``actions`` stores the given leaves verbatim; every grouped property
    references those same objects, so identity checks hold across both
    surfaces.
    """
    actions = tuple(legal_actions)
    blind = ticket_draw = pass_leaf = None
    face_up_by_slot: "dict[int, DrawFaceUp]" = {}
    payments_by_route: "dict[str, list[ClaimRoute]]" = {}
    for leaf in actions:
        if isinstance(leaf, DrawBlind):
            blind = leaf
        elif isinstance(leaf, DrawFaceUp):
            face_up_by_slot[leaf.index] = leaf
        elif isinstance(leaf, ClaimRoute):
            payments_by_route.setdefault(leaf.route_id, []).append(leaf)
        elif isinstance(leaf, DrawTickets):
            ticket_draw = leaf
        elif isinstance(leaf, Pass):
            pass_leaf = leaf
        else:
            raise ValueError(f"Unexpected leaf in a turn menu: {leaf!r}")
    entries = tuple(
        RouteClaimOptions(route=state.route_by_id(route_id),
                          payments=tuple(payments))
        for route_id, payments in payments_by_route.items()
    )
    return TurnDecision(
        decision_id=decision_id,
        state=state,
        draws=_draw_options(blind, face_up_by_slot, len(state.face_up_cards)),
        claims=ClaimOptions(
            entries=entries,
            by_route_id=MappingProxyType(
                {options.route.route_id: options for options in entries}
            ),
        ),
        destination_tickets=DrawTicketOptions(draw=ticket_draw),
        pass_action=pass_leaf,
        actions=actions,
    )


def build_second_draw_decision(*, decision_id: DecisionId, state: PlayerView,
                               first_draw: DrawResult,
                               legal_actions) -> SecondDrawDecision:
    """Group a second-draw legal-action list, order and objects intact."""
    actions = tuple(legal_actions)
    blind = None
    face_up_by_slot: "dict[int, DrawFaceUp]" = {}
    for leaf in actions:
        if isinstance(leaf, DrawBlind):
            blind = leaf
        elif isinstance(leaf, DrawFaceUp):
            face_up_by_slot[leaf.index] = leaf
        elif not isinstance(leaf, Pass):
            raise ValueError(f"Unexpected leaf in a second-draw menu: {leaf!r}")
    return SecondDrawDecision(
        decision_id=decision_id,
        state=state,
        first_draw=first_draw,
        draws=_draw_options(blind, face_up_by_slot, len(state.face_up_cards)),
        actions=actions,
    )


def build_keep_tickets_decision(*, decision_id: DecisionId, state: PlayerView,
                                source, offer, minimum_to_keep: int,
                                legal_actions) -> KeepTicketsDecision:
    """Group a keep-tickets legal-action list, order and objects intact."""
    actions = tuple(legal_actions)
    for leaf in actions:
        if not isinstance(leaf, KeepTickets):
            raise ValueError(f"Unexpected leaf in a keep menu: {leaf!r}")
    return KeepTicketsDecision(
        decision_id=decision_id,
        state=state,
        source=source,
        offer=tuple(offer),
        minimum_to_keep=minimum_to_keep,
        choices=KeepTicketOptions(
            available=actions,
            by_indices=MappingProxyType(
                {leaf.indices: leaf for leaf in actions}
            ),
        ),
        actions=actions,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run python -m unittest quality.tests.test_engine_decisions -v`
Expected: PASS. Note the docstring and frozen-dataclass tests from Task 1 now also cover the new types automatically.

- [ ] **Step 5: Full suite + pyright**

Run: `uv run test` — expected: all pass (nothing existing changed).
Run: `npx -y pyright` — expected: no new errors vs baseline.

- [ ] **Step 6: Commit**

```bash
git add services/native-runtime/src/ticket_to_ride/engine/decisions.py quality/tests/test_engine_decisions.py
git commit -m "feat(engine): TurnDecision/SecondDrawDecision/KeepTicketsDecision and builders"
```

---

### Task 3: RandomBot speaks `decide`

**Files:**
- Modify: `integrations/external/bots/random_bot.py:22-41`
- Test: `integrations/external/tests/test_random_bot.py`

**Interfaces:**
- Consumes: `BotDecision` union and builders (Task 2).
- Produces: `RandomBot.decide(decision) -> Action` returning `random.choice(decision.actions)`. **Keep the existing `act` method for now** — the engine still calls `act` until Task 8; Task 11 deletes it.

- [ ] **Step 1: Write the failing test**

Replace the body of `integrations/external/tests/test_random_bot.py`'s selection test (line 21 currently calls `bot.act(SimpleNamespace(decision="turn"), legal_actions)`) with a decide-based one, keeping any other assertions in the file intact:

```python
import unittest

from external.bots.random_bot import RandomBot
from ticket_to_ride.engine.actions import legal_turn_actions
from ticket_to_ride.engine.decisions import DecisionId, build_turn_decision
from ticket_to_ride.engine.player import Player
from ticket_to_ride.engine.state.game_context import GameContext
from ticket_to_ride.engine.state.views import PlayerView


class RandomBotTests(unittest.TestCase):
    def test_decide_returns_a_canonical_leaf(self):
        context = GameContext(["p0", "p1"], seed=7)
        bot = RandomBot()
        players = [Player("p0", bot, "p0", "red"),
                   Player("p1", RandomBot(), "p1", "blue")]
        for player in players:
            player.attach(context, players)
        view = PlayerView("p0", context, players)
        decision = build_turn_decision(
            decision_id=DecisionId(0, 0, 0), state=view,
            legal_actions=legal_turn_actions(players[0]),
        )
        chosen = bot.decide(decision)
        self.assertIn(id(chosen), {id(a) for a in decision.actions})
```

Note: until Task 8 the `Player` constructor still accepts act-style bots, so this construction works throughout the branch.

- [ ] **Step 2: Run to verify failure**

Run: `uv run python -m unittest external.tests.test_random_bot -v`
Expected: FAIL with `AttributeError: 'RandomBot' object has no attribute 'decide'`

- [ ] **Step 3: Implement `decide` on RandomBot**

In `integrations/external/bots/random_bot.py`, inside the `RandomBot` class (keep `act` untouched for now), add:

```python
    def decide(self, decision):
        """Pick a uniformly random canonical leaf from ``decision.actions``.

        ``decision.actions`` is always the complete legal menu, so this one
        line is a complete bot for every decision type.
        """
        return random.choice(decision.actions)
```

Update the class docstring to describe `decide` receiving a `BotDecision` (state in `decision.state`, menu in `decision.actions`) instead of describing `act`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run python -m unittest external.tests.test_random_bot -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add integrations/external/bots/random_bot.py integrations/external/tests/test_random_bot.py
git commit -m "feat(bots): RandomBot implements decide(decision)"
```

---

### Task 4: ExampleBot speaks `decide`

**Files:**
- Modify: `integrations/external/bots/example_bot.py` (dispatch at lines 70-76, keep handler at lines 401-413)
- Test: `quality/tests/test_example_bot.py` (view construction at lines 40-44)

**Interfaces:**
- Consumes: `TurnDecision`, `SecondDrawDecision`, `KeepTicketsDecision`, builders.
- Produces: `ExampleBot.decide(decision) -> Action`. Internal helpers keep their `(view, legal_actions)` signatures; `_keep_action` changes to take the decision (the offer moved off the view). Keep `act` until Task 11.

- [ ] **Step 1: Update the keep-tickets test to drive `decide`**

In `quality/tests/test_example_bot.py`, replace the `PlayerView(..., decision="keep_tickets", ticket_offer=offer)` + `example_bot.act(view, ...)` block (lines ~40-44) with:

```python
        from ticket_to_ride.engine.decisions import (
            DecisionId, build_keep_tickets_decision,
        )
        offer = game.context.get_ticket_deck().deal_unique(3)
        view = PlayerView(player.player_id, game.context, game.players)
        decision = build_keep_tickets_decision(
            decision_id=DecisionId(0, -1, 1), state=view, source="setup",
            offer=tuple(offer), minimum_to_keep=2,
            legal_actions=legal_keep_actions(len(offer), 2),
        )
        choice = example_bot.decide(decision)
```

Also add one turn-phase test mirroring Task 3's pattern: build a `TurnDecision` for a position where the bot has cards (seed + hand as in `test_bayesian_utility_bot.py:80-96` if the file lacks one) and assert `id(bot.decide(decision))` is in `{id(a) for a in decision.actions}`.

- [ ] **Step 2: Run to verify failure**

Run: `uv run python -m unittest quality.tests.test_example_bot -v`
Expected: FAIL with `AttributeError: ... no attribute 'decide'`

- [ ] **Step 3: Implement `decide` on ExampleBot**

Add to the class (imports for the decision types go in the notebook's setup cell alongside the existing `ticket_to_ride.engine.actions` imports):

```python
    def decide(self, decision):
        """Route each decision phase to the matching planning helper."""
        match decision:
            case TurnDecision():
                self._view = decision.state
                return self._turn_action(decision.state, list(decision.actions))
            case SecondDrawDecision():
                self._view = decision.state
                return self._draw_action(decision.state, list(decision.actions))
            case KeepTicketsDecision():
                self._view = decision.state
                return self._keep_action(decision)
```

Change `_keep_action` (currently `def _keep_action(self, view, legal_actions)` reading `view.ticket_offer` at lines 402-403) to:

```python
    def _keep_action(self, decision):
        offer = list(decision.offer)
        legal_actions = list(decision.actions)
        kept = self._select_tickets(offer)
        indices = tuple(sorted(offer.index(t) for t in kept))
        return decision.choices.by_indices.get(indices) or min(
            (a for a in legal_actions if set(indices) <= set(a.indices)),
            key=lambda a: len(a.indices),
            default=legal_actions[0],
        )
```

(`Mapping.get` works on `MappingProxyType`; the superset fallback preserves the old behavior when `_select_tickets` returns an under-minimum set.) Keep the old `act` method delegating as-is until Task 11 — it still backs the engine until Task 8 flips.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run python -m unittest quality.tests.test_example_bot -v`
Expected: PASS (both the new decide tests and the untouched act-based game tests).

- [ ] **Step 5: Commit**

```bash
git add integrations/external/bots/example_bot.py quality/tests/test_example_bot.py
git commit -m "feat(bots): ExampleBot implements decide(decision)"
```

---

### Task 5: QualifierBot and FableBestBot speak `decide`

**Files:**
- Modify: `integrations/external/bots/qualifier_bot.py` (dispatch at lines 75-81, keep handler at lines 463-466)
- Modify: `integrations/external/bots/fable_best_bot.py` (dispatch at lines 112-118, keep handler at lines 671-674)
- Test: `quality/tests/test_qualifier_bot.py`, `quality/tests/test_codex_best_bot.py` — no, fable's tests: check `quality/tests` for the fable test module; if none exists, add the decide test to `test_qualifier_bot.py` only and cover fable via the turn-decision pattern inside `test_mixed_map_bots.py`'s existing imports — **do not skip**: each bot gets at least one direct `decide` unit test in the module that already tests it.

**Interfaces:**
- Consumes: decision types + builders.
- Produces: `QualifierBot.decide`, `FableBestBot.decide`. Both bots follow the exact ExampleBot pattern: `match` dispatch, `self._prime_view(decision.state)` where the old `act` called `_prime_view(view)`, helpers keep `(view, legal_actions)` signatures, `_keep_action` rewritten to take the decision (same code as Task 4 Step 3's `_keep_action`, adjusted to each bot's `_select_tickets` call). Keep `act` until Task 11.

- [ ] **Step 1: Write the failing tests** — one per bot, in that bot's existing test module, using the Task 3/Task 4 `build_turn_decision` + `build_keep_tickets_decision` patterns (seeded `GameContext`, real `Player`, assert the returned object's `id` is in the menu).

- [ ] **Step 2: Run to verify failure**

Run: `uv run python -m unittest quality.tests.test_qualifier_bot -v`
Expected: FAIL with `AttributeError: ... 'decide'`

- [ ] **Step 3: Implement `decide` on both bots**

For each bot, add (adjusting `_prime_view` to the bot's actual per-decision cache method):

```python
    def decide(self, decision):
        """Route each decision phase to the matching planning helper."""
        match decision:
            case TurnDecision():
                self._prime_view(decision.state)
                return self._turn_action(decision.state, list(decision.actions))
            case SecondDrawDecision():
                self._prime_view(decision.state)
                return self._draw_action(decision.state, list(decision.actions))
            case KeepTicketsDecision():
                self._prime_view(decision.state)
                return self._keep_action(decision)
```

and convert `_keep_action` to the decision-based form exactly as in Task 4 Step 3.

- [ ] **Step 4: Run both bots' test modules to verify they pass**

Run: `uv run python -m unittest quality.tests.test_qualifier_bot quality.tests.test_mixed_map_bots -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add integrations/external/bots/qualifier_bot.py integrations/external/bots/fable_best_bot.py quality/tests/
git commit -m "feat(bots): QualifierBot and FableBestBot implement decide(decision)"
```

---

### Task 6: CodexBestBot and BayesianUtilityBot speak `decide`

These two also branch on `view.decision` *inside* their evaluation helpers, so they additionally need an explicit second-draw flag.

**Files:**
- Modify: `integrations/external/bots/codex_best_bot.py` (dispatch at lines 86-93; internal read at line 766 `action.card == "L" and view.decision != "draw_second"`; keep handler at lines 787-790)
- Modify: `integrations/external/bots/bayesian_utility_bot.py` (dispatch at lines 74-87; internal reads at lines 175 and 191 `self._view.decision == "draw_second"`; offer reads at lines 572 and 599)
- Test: `quality/tests/test_codex_best_bot.py`, `quality/tests/test_bayesian_utility_bot.py` (act-based construction at lines ~91-96)

**Interfaces:**
- Consumes: decision types + builders.
- Produces: `decide` on both bots; a private `self._is_second_draw: bool` set at every `decide` call replaces `view.decision == "draw_second"` reads; Bayesian's keep path takes the offer from the decision (store `self._current_offer` in `decide` before delegating; replace `self._view.ticket_offer or []` at line 572 with `self._current_offer`). Keep `act` until Task 11 — set `self._is_second_draw = (view.decision == "draw_second")` and `self._current_offer = list(view.ticket_offer or [])` at the top of `act` so both entry points feed the same internals.

- [ ] **Step 1: Write the failing tests** — in each bot's test module: (a) the standard turn-`decide` canonical-leaf test; (b) for Bayesian, a keep test building a `KeepTicketsDecision` (offer dealt from the context as in Task 4) asserting the choice is canonical and keeps ≥ `minimum_to_keep`. Update `test_bayesian_utility_bot.py:96` (`bot.act(view, legal)`) to `bot.decide(decision)` with a built `TurnDecision`.

- [ ] **Step 2: Run to verify failure**

Run: `uv run python -m unittest quality.tests.test_codex_best_bot quality.tests.test_bayesian_utility_bot -v`
Expected: FAIL with `AttributeError: ... 'decide'`

- [ ] **Step 3: Implement**

CodexBestBot:

```python
    def decide(self, decision):
        """Route each decision phase to the matching planning helper."""
        match decision:
            case TurnDecision():
                self._prime_view(decision.state)
                self._is_second_draw = False
                return self._turn_action(decision.state, list(decision.actions))
            case SecondDrawDecision():
                self._prime_view(decision.state)
                self._is_second_draw = True
                return self._draw_action(decision.state, list(decision.actions))
            case KeepTicketsDecision():
                self._prime_view(decision.state)
                return self._keep_action(decision)
```

At line 766 replace `view.decision != "draw_second"` with `not self._is_second_draw`. Initialize `self._is_second_draw = False` in `__init__`. Convert `_keep_action` per Task 4.

BayesianUtilityBot — same shape; its `decide` for keep is:

```python
            case KeepTicketsDecision():
                self._prepare(decision.state)
                self._current_offer = list(decision.offer)
                return max(decision.actions, key=self._keep_utility)
```

Replace lines 175/191 `self._view.decision == "draw_second"` with `self._is_second_draw`, and line 572's `self._view.ticket_offer or []` with `self._current_offer`. Initialize both fields in `__init__` (`False`, `[]`).

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run python -m unittest quality.tests.test_codex_best_bot quality.tests.test_bayesian_utility_bot -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add integrations/external/bots/codex_best_bot.py integrations/external/bots/bayesian_utility_bot.py quality/tests/
git commit -m "feat(bots): CodexBestBot and BayesianUtilityBot implement decide(decision)"
```

---

### Task 7: XGBot speaks `decide`

**Files:**
- Modify: `integrations/external/bots/xg_bot.py:52-112`
- Test: `quality/tests/test_xg_bot.py:25-40`

**Interfaces:**
- Consumes: decision types; `xgb_features.state_from_view` (unchanged — its `getattr(view, "decision", "turn")` fallback already tolerates views without `.decision`).
- Produces: `XGBot.decide(decision)`; feature rows keep the legacy decision one-hot labels via an explicit mapping, so existing trained models stay aligned. Fallback delegates `decide` to `QualifierBot.decide` (available since Task 5). Keep `act` until Task 11.

- [ ] **Step 1: Update the fallback test to drive `decide`** — in `test_xg_bot.py`, replace `bot.act(view, legal)` with a built `TurnDecision` + `bot.decide(decision)`; assert membership by identity against `decision.actions`.

- [ ] **Step 2: Run to verify failure**

Run: `uv run python -m unittest quality.tests.test_xg_bot -v`
Expected: FAIL with `AttributeError: ... 'decide'`

- [ ] **Step 3: Implement**

```python
_DECISION_LABELS = {
    "TurnDecision": "turn",
    "SecondDrawDecision": "draw_second",
    "KeepTicketsDecision": "keep_tickets",
}


    def decide(self, decision):
        """Score every canonical leaf and return the best; fall back to
        QualifierBot when the model is unavailable."""
        legal_actions = list(decision.actions)
        if not self._load_model():
            return self._fallback_decide(decision)
        try:
            state = xgb_features.state_from_view(decision.state)
            legal_dicts = xgb_features.actions_to_dicts(legal_actions)
            rows = xgb_features.build_action_feature_rows(
                {
                    "player": decision.state.player_id,
                    "decision": _DECISION_LABELS[type(decision).__name__],
                    "state": state,
                },
                legal_dicts,
            )
            matrix = xgb_features.vectorize(rows, self._feature_names)
            scores = list(self._booster.predict(self._xgb.DMatrix(matrix)))
        except Exception as exc:
            self._fallback_reason = f"inference failed: {exc}"
            return self._fallback_decide(decision)
        if len(scores) != len(legal_actions):
            self._fallback_reason = (
                "model returned a score count that did not match the legal action menu"
            )
            return self._fallback_decide(decision)
        best = max(range(len(scores)), key=lambda i: (float(scores[i]), -i))
        return legal_actions[best]

    def _fallback_decide(self, decision):
        if not self._fallback_warned:
            _LOGGER.warning("XG Bot falling back to QualifierBot: %s.", self._fallback_reason)
            self._fallback_warned = True
        if self._fallback_bot is None:
            from external.bots.qualifier_bot import QualifierBot
            self._fallback_bot = QualifierBot()
            if hasattr(self, "player"):
                self._fallback_bot.set_player(self.player)
        return self._fallback_bot.decide(decision)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run python -m unittest quality.tests.test_xg_bot -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add integrations/external/bots/xg_bot.py quality/tests/test_xg_bot.py
git commit -m "feat(bots): XGBot implements decide(decision)"
```

---

### Task 8: Engine cutover — `Player` speaks `decide`, everywhere

This is the atomic flip. Everything that sits between `Player` and a bot changes in one commit so the suite stays green: `player.py`, `game.py`, `views.py`, `replay.py`, the CLI bootstrap bot, `ManagedSeatInterface`, the executor guard, and the research observer wrappers.

**Files:**
- Modify: `services/native-runtime/src/ticket_to_ride/engine/player.py`
- Modify: `services/native-runtime/src/ticket_to_ride/engine/game.py:41-42`
- Modify: `services/native-runtime/src/ticket_to_ride/engine/state/views.py:34-70`
- Modify: `services/native-runtime/src/ticket_to_ride/engine/replay.py:72-83`
- Modify: `services/native-runtime/src/ticket_to_ride/runtime/cli.py:530-537`
- Modify: `services/native-runtime/src/ticket_to_ride/backend/runtime/round_runtime.py:70-75`
- Modify: `services/native-runtime/src/ticket_to_ride/backend/runtime/executor.py:128-141`
- Modify: `operations/research/decision_export.py`, `operations/research/xg_data_pump.py:88-100`, `operations/research/xg_curriculum.py:80-83`
- Modify tests: `quality/tests/test_engine_actions.py:107-120`, `quality/tests/test_replay.py:21`, `quality/tests/test_runtime_executor.py:106-152`, `quality/tests/test_decision_export.py`, `quality/tests/test_xg_data_pump.py`
- Create test: `quality/tests/test_player_decide.py`

**Interfaces:**
- Consumes: builders and `IllegalActionError` (Tasks 1–2); every in-repo bot's `decide` (Tasks 3–7).
- Produces:
  - `Player` calls `interface.decide(decision)` and enforces identity membership. Interfaces without a callable `decide` are rejected at construction with `TypeError`.
  - `Player.attach(game_context, players, round_number=0)` — `Game.__init__` passes its `round_number`.
  - `Player.__apply_draw(action) -> DrawResult` (was `bool`).
  - Optional interface hook consumed by Task 9: if the interface has a callable `on_illegal_action(decision, returned)`, `Player` logs at ERROR, calls the hook, and substitutes `decision.actions[0]` instead of raising.
  - `PlayerView` loses `decision` and `ticket_offer` (constructor params and attributes).
  - `ScriptedBot.decide(decision)` resolves the recorded action to the value-equal canonical leaf (replay records are reconstructed objects, so identity can't hold; the scripted bot's job is to return the engine's own leaf).
  - Export rows gain `"decision_type"` (class name) and `"decision_id"` (`[round, turn, phase]`), keep `"decision"` as the legacy label for feature alignment; `STATE_SCHEMA_VERSION` bumps to 2.

- [ ] **Step 1: Write the failing player-level tests**

Create `quality/tests/test_player_decide.py`:

```python
import random
import unittest

from ticket_to_ride.engine.actions import DrawBlind, Pass
from ticket_to_ride.engine.decisions import (
    IllegalActionError, KeepTicketsDecision, SecondDrawDecision, TurnDecision,
)
from ticket_to_ride.engine.game import Game
from ticket_to_ride.engine.player import Player
from ticket_to_ride.engine.state.game_context import GameContext


class _SilentLogger:
    def record_turn(self, *args, **kwargs):
        return None


class _RecordingRandomBot:
    """Plays uniformly at random and records every decision it saw."""

    def __init__(self, rng_seed=0):
        self.rng = random.Random(rng_seed)
        self.decisions = []

    def set_player(self, player):
        self.player = player

    def decide(self, decision):
        self.decisions.append(decision)
        return self.rng.choice(decision.actions)


class _ReconstructingBot(_RecordingRandomBot):
    """Returns a value-equal copy instead of the canonical leaf."""

    def decide(self, decision):
        super().decide(decision)
        return DrawBlind()


def _play_seeded_game(seed, bot_factory):
    bots = [bot_factory(0), bot_factory(1)]
    players = [Player(f"p{i}", bots[i], f"p{i}", "red") for i in range(2)]
    context = GameContext([p.player_id for p in players], seed=seed)
    game = Game(context, players, _SilentLogger(), 0)
    game.play()
    return bots


class PlayerDecideTests(unittest.TestCase):
    def test_interfaces_without_decide_are_rejected(self):
        class ActOnly:
            def set_player(self, player): ...
            def act(self, view, legal_actions): ...

        with self.assertRaises(TypeError):
            Player("p0", ActOnly(), "p0", "red")

    def test_illegal_reconstructed_action_raises_with_context(self):
        with self.assertRaises(IllegalActionError) as caught:
            _play_seeded_game(23, lambda i: _ReconstructingBot(i))
        message = str(caught.exception)
        self.assertIn("KeepTicketsDecision", message)  # setup keep comes first
        self.assertIn("DrawBlind", message)
        self.assertIn("Legal menu", message)

    def test_seeded_games_produce_identical_decision_id_sequences(self):
        first = _play_seeded_game(31, lambda i: _RecordingRandomBot(i))
        second = _play_seeded_game(31, lambda i: _RecordingRandomBot(i))
        for bot_a, bot_b in zip(first, second):
            self.assertEqual(
                [d.decision_id for d in bot_a.decisions],
                [d.decision_id for d in bot_b.decisions],
            )

    def test_setup_and_turn_keeps_report_their_minimums(self):
        bots = _play_seeded_game(31, lambda i: _RecordingRandomBot(i))
        keeps = [
            d for bot in bots for d in bot.decisions
            if isinstance(d, KeepTicketsDecision)
        ]
        setup_keeps = [d for d in keeps if d.source == "setup"]
        self.assertEqual(len(setup_keeps), 2)
        for decision in setup_keeps:
            self.assertEqual(decision.minimum_to_keep, 2)
            self.assertEqual(decision.decision_id.turn_index, -1)
            self.assertEqual(len(decision.offer), 3)
        for decision in keeps:
            if decision.source == "turn":
                self.assertEqual(decision.minimum_to_keep, 1)

    def test_second_draw_reports_first_draw_and_updated_hand(self):
        bots = _play_seeded_game(31, lambda i: _RecordingRandomBot(i))
        seconds = [
            d for bot in bots for d in bot.decisions
            if isinstance(d, SecondDrawDecision)
        ]
        self.assertTrue(seconds)
        for decision in seconds:
            self.assertIn(decision.first_draw.card,
                          {"R", "O", "Y", "G", "B", "P", "W", "K", "L"})
            self.assertGreaterEqual(decision.state.hand[decision.first_draw.card], 1)
            self.assertEqual(decision.decision_id.phase_index, 1)

    def test_player_view_no_longer_carries_offer_or_phase(self):
        bots = _play_seeded_game(31, lambda i: _RecordingRandomBot(i))
        any_decision = bots[0].decisions[0]
        self.assertFalse(hasattr(any_decision.state, "ticket_offer"))
        self.assertFalse(hasattr(any_decision.state, "decision"))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run python -m unittest quality.tests.test_player_decide -v`
Expected: FAIL — `Player` currently wraps `ActOnly` in `LegacyBotAdapter` instead of raising, and `_RecordingRandomBot` has no `act`, so game play crashes.

- [ ] **Step 3: Rewrite `player.py`'s decision plumbing**

In `services/native-runtime/src/ticket_to_ride/engine/player.py`:

1. Replace the imports block's adapter line (`from ticket_to_ride.engine.legacy_adapter import LegacyBotAdapter`) with:

```python
from ticket_to_ride.engine.decisions import (
    DecisionId, DrawResult, IllegalActionError,
    build_keep_tickets_decision, build_second_draw_decision, build_turn_decision,
)
```

2. In `__init__` (lines 28-31), replace the adapter wrap with a hard requirement, and add the round field:

```python
        self.__raw_interface = interface
        if not callable(getattr(interface, "decide", None)):
            raise TypeError(
                f"{type(interface).__name__} does not implement decide(decision). "
                "The act(view, legal_actions) contract was removed; see "
                "engine/decisions.py for the BotDecision union."
            )
        self.__interface = interface
        self.__interface.set_player(self)
        self._round_number = 0
```

3. Extend `attach`:

```python
    def attach(self, game_context, players: 'List[Player]',
               round_number: int = 0) -> None:
        """Bind the live GameContext (the engine's mutation channel), the
        seat list, and the round number used in DecisionIds. Views handed
        to bots never carry these."""
        self._game = game_context
        self._players = list(players)
        self._round_number = round_number
```

4. Replace `__choose` with view/id helpers and the identity-enforcing selector:

```python
    def __view(self) -> PlayerView:
        """A fresh view of everything this seat may know right now."""
        return PlayerView(self.player_id, self._game, self._players)

    def __decision_id(self, phase_index: int, *, setup: bool = False) -> DecisionId:
        """Derive the position-based DecisionId for the next decision.

        Setup ticket keeps happen before any turn exists and use
        turn_index=-1 so they order before every turn decision.
        """
        turn_index = -1 if setup else self._game.turn_num
        return DecisionId(self._round_number, turn_index, phase_index)

    def __select(self, decision):
        """Ask the interface to decide; enforce canonical-leaf identity.

        An illegal return raises IllegalActionError. Interfaces that
        declare on_illegal_action(decision, returned) — managed execution —
        get the substitution behavior instead: ERROR log, hook call (which
        counts a runtime failure), then decision.actions[0].
        """
        action = self.__interface.decide(decision)
        if id(action) not in {id(leaf) for leaf in decision.actions}:
            handler = getattr(self.__interface, "on_illegal_action", None)
            if not callable(handler):
                raise IllegalActionError(self.player_id, decision, action)
            substitute = decision.actions[0]
            logger.error(
                "Player %s returned illegal action %r for %s %s; substituting %r. "
                "Legal menu: %r",
                self.player_id, action, type(decision).__name__,
                decision.decision_id, substitute, decision.actions,
            )
            handler(decision, action)
            action = substitute
        logger.debug("decision %s: %s chose %r",
                     decision.decision_id, self.player_id, action)
        self._game.action_log.append((self.player_id, action))
        return action
```

5. Rewrite `take_turn`'s decision flow (keep the begin/end hooks and `check_ticket_completion` exactly as they are):

```python
            turn_decision = build_turn_decision(
                decision_id=self.__decision_id(0),
                state=self.__view(),
                legal_actions=legal_turn_actions(self),
            )
            action = self.__select(turn_decision)
            if isinstance(action, (DrawBlind, DrawFaceUp)):
                first = self.__apply_draw(action)
                face_up_locomotive = (
                    isinstance(action, DrawFaceUp) and first.card == "L"
                )
                if not face_up_locomotive:
                    second_decision = build_second_draw_decision(
                        decision_id=self.__decision_id(1),
                        state=self.__view(),
                        first_draw=first,
                        legal_actions=legal_second_draw_actions(self),
                    )
                    second = self.__select(second_decision)
                    if not isinstance(second, Pass):
                        self.__apply_draw(second)
            elif isinstance(action, ClaimRoute):
                self.__apply_claim(action)
            elif isinstance(action, DrawTickets):
                self.__draw_destination_tickets()
```

6. `__apply_draw` returns a `DrawResult`:

```python
    def __apply_draw(self, action) -> DrawResult:
        """Apply a draw and report which card arrived. A face-up
        locomotive (DrawResult.card == "L" on a DrawFaceUp) ends the
        drawing for this turn; a blind locomotive does not."""
        deck = self._game.get_train_deck()
        if isinstance(action, DrawFaceUp):
            card = deck.draw_face_up(action.index)
            self.__add_cards([card], True)
            return DrawResult(action=action, card=card)
        card = deck.draw_face_down()
        self.__add_cards([card], False)
        return DrawResult(action=action, card=card)
```

7. `__draw_destination_tickets` gains `source` and builds the decision:

```python
    def __draw_destination_tickets(self, min_keep: int = 1,
                                   source: str = "turn") -> bool:
        """Deal an offer and ask the interface which tickets to keep."""
        try:
            offer = self._game.get_ticket_deck().deal_unique(3)
        except Exception as e:
            logger.warning("Ticket draw failed for player %s: %s", self.player_id, e)
            return False
        if not offer:
            logger.info("No destination tickets available for %s.", self.player_id)
            return False

        decision = build_keep_tickets_decision(
            decision_id=self.__decision_id(1, setup=(source == "setup")),
            state=self.__view(),
            source=source,
            offer=tuple(offer),
            minimum_to_keep=min_keep,
            legal_actions=legal_keep_actions(len(offer), min_keep),
        )
        choice = self.__select(decision)
        kept = [offer[i] for i in choice.indices]
        self.__tickets.extend(kept)
        returned = [t for i, t in enumerate(offer) if i not in choice.indices]
        self._game.get_ticket_deck().return_tickets(returned)
        return True
```

and `set_context`'s setup call becomes `self.__draw_destination_tickets(min_keep=2, source="setup")`.

- [ ] **Step 4: The supporting engine/runtime/research edits (same commit)**

1. `game.py:41-42` — `for p in players: p.attach(context, players, round_number)` (pass `self.round_number`... it is assigned at line 34; use the constructor argument).
2. `views.py` — remove the `decision`/`ticket_offer` parameters and attribute assignments from `PlayerView.__init__` (lines 47-56) and rewrite the class docstring's last paragraph: phase context now lives on the `BotDecision` types in `engine/decisions.py`.
3. `replay.py` — replace `ScriptedBot.act` (line 81) with:

```python
    def decide(self, decision):
        """Return the canonical leaf matching the next recorded action.

        Recorded actions are value-equal reconstructions, so the scripted
        bot maps them back onto the engine's own leaves; a mismatch means
        the replay has diverged and raises immediately.
        """
        expected = self._script.popleft()
        for leaf in decision.actions:
            if leaf == expected:
                return leaf
        raise ValueError(
            f"Replay diverged at {decision.decision_id}: recorded action "
            f"{expected!r} is not in the current legal menu {decision.actions!r}"
        )
```

4. `runtime/cli.py:536-537` — `BootstrapRandomActionBot.act` becomes `def decide(self, decision): return random.choice(decision.actions)` (update its docstring accordingly).
5. `round_runtime.py:70-75` — replace `ManagedSeatInterface.act` with:

```python
    def decide(self, decision):
        """Send the engine's decision to the seat's executor."""
        return self.round_context.execute_action(
            self.seat_id, "decide", self.player, decision
        )
```

(`InProcessBotExecutor.invoke` already dispatches by `getattr(self.bot, action_name)`, so in-process seats work unchanged. Leave the `choose_*` forwarding methods alone — Phase 2 deletes them with the wire protocol.)
6. `executor.py` — at the top of `BotApiExecutor.invoke` (line 128), before building the payload:

```python
        if action_name == "decide":
            return ExecutionResult(
                status="transport_error",
                elapsed_ms=0,
                detail=(
                    "Remote bot sessions do not support the decision envelope "
                    "yet (wire protocol v2). The seat fails over to its "
                    "fallback bot."
                ),
            )
```

7. `decision_export.py` — `_ObservingBot` now extends the decide-based `ScriptedBot`:

```python
class _ObservingBot(ScriptedBot):
    """Feeds the recorded actions back while capturing every decision."""

    def __init__(self, script, sink, player_id):
        super().__init__(script)
        self._sink = sink
        self._player_id = player_id

    def decide(self, decision):
        action = super().decide(decision)
        self._sink.append((self._player_id, decision, action))
        return action
```

`symbolic_state(view)` becomes `symbolic_state(view, ticket_offer=None)` — the trailing `"ticket_offer"` entry reads from the parameter instead of `view.ticket_offer`. `decisions_from_record` unpacks `(player_id, decision, action)` and emits:

```python
    _LEGACY_LABELS = {
        "TurnDecision": "turn",
        "SecondDrawDecision": "draw_second",
        "KeepTicketsDecision": "keep_tickets",
    }
    ...
        offer = getattr(decision, "offer", None)
        rows.append({
            **meta,
            "state_schema_version": STATE_SCHEMA_VERSION,   # now 2
            "decision_index": index,
            "player": player_id,
            "decision": _LEGACY_LABELS[type(decision).__name__],
            "decision_type": type(decision).__name__,
            "decision_id": [decision.decision_id.round_number,
                            decision.decision_id.turn_index,
                            decision.decision_id.phase_index],
            "state": symbolic_state(decision.state, ticket_offer=offer),
            "legal_actions": [action_to_dict(a) for a in decision.actions],
            "chosen": action_to_dict(action),
            "outcome": {...unchanged...},
        })
```

Bump `STATE_SCHEMA_VERSION = 2` with a comment noting the offer/decision-type change. Update `quality/tests/test_decision_export.py` expectations (keep-ticket rows still expose `state.ticket_offer`; add an assertion that every row has `decision_type` and a 3-element `decision_id`).
8. `xg_data_pump.py:88-100` — the wrapper's `act` becomes:

```python
    def decide(self, decision: Any) -> Any:
        action = self.inner.decide(decision)
        if self.capture_decisions:
            offer = getattr(decision, "offer", None)
            self.sink.append((
                self.seat_id,
                _LEGACY_LABELS[type(decision).__name__],
                symbolic_state(decision.state, ticket_offer=offer),
                [action_to_dict(leaf) for leaf in decision.actions],
                action_to_dict(action),
            ))
        return action
```

(import `_LEGACY_LABELS` from `decision_export` or duplicate the 3-line map; drop the old `action not in legal_actions → legal_actions[0]` substitution — `Player` now enforces legality loudly, and silently repairing here would mask bot bugs). Same one-line `act`→`decide` change in `xg_curriculum.py:80-83`.
9. Test updates in the same commit:
   - `test_engine_actions.py:107-120` — the two stub classes gain `def decide(self, decision): ...` bodies equivalent to their `act` bodies (`decision.actions` in place of `legal_actions`); their assertions keep working because Task 2 guarantees `decision.actions == tuple(legal)`.
   - `test_replay.py:21` — the recording stub's `act` becomes `decide(self, decision)` returning per its old logic with `decision.actions`.
   - `test_runtime_executor.py:106-152` — the fake bots' `act(self, view, legal_actions)` become `decide(self, decision)`; the corresponding `invoke("act", ...)` calls become `invoke("decide", ..., args=(decision,))` with a minimal stand-in decision object (the in-process executor only forwards args, so `SimpleNamespace(actions=(...))` is sufficient there). Add one new test: `BotApiExecutor().invoke("decide", ...)` returns `status == "transport_error"` mentioning wire protocol v2.

- [ ] **Step 5: Run the new tests, then the full suite**

Run: `uv run python -m unittest quality.tests.test_player_decide -v` — expected: PASS.
Run: `uv run test` — expected: PASS across the board (bots already speak `decide` from Tasks 3–7; their `act` methods are now dead code, deleted in Task 11). Triage any straggler test that constructs `PlayerView(..., decision=..., ticket_offer=...)` or calls `.act(...)` on an engine-driven path — the fix is always the same builder pattern used above. Known stragglers to check: `quality/tests/test_xg_data_pump.py`, `quality/tests/test_xg_curriculum.py`, `quality/tests/test_train_xg_bot.py` (fixture dicts with `"ticket_offer"` keys are exported-row fixtures and remain valid).
Run: `npx -y pyright` — expected: no new errors vs baseline.

- [ ] **Step 6: Commit**

```bash
git add -A services/native-runtime operations/research quality/tests integrations/external
git commit -m "feat!: engine dispatches decide(BotDecision); illegal returns fail loudly"
```

---

### Task 9: Managed-execution illegal-action policy

**Files:**
- Modify: `services/native-runtime/src/ticket_to_ride/backend/runtime/round_runtime.py` (interface + context + finalizers)
- Modify: `services/native-runtime/src/ticket_to_ride/backend/models.py:137-146`
- Modify: `services/native-runtime/src/ticket_to_ride/backend/runtime/managed_match_runtime.py:302-316`
- Test: `quality/tests/test_runtime_controllers.py` (or `quality/tests/test_managed_match_api.py`, whichever already exercises `RoundExecutionContext` finalization — add there)

**Interfaces:**
- Consumes: `Player.__select`'s `on_illegal_action` hook (Task 8).
- Produces: `ManagedSeatInterface.on_illegal_action(decision, returned)`; `RoundExecutionContext.record_illegal_action(seat_id)`; `ManagedSeatRoundResult.illegalActions: int = 0`; aggregate `runtimeFailures` increments once per round for any seat with `illegalActions > 0`.

- [ ] **Step 1: Write the failing test**

In the module that already builds a `RoundExecutionContext` (follow its existing fixture pattern), add:

```python
    def test_illegal_actions_count_into_seat_results(self):
        round_context = self._build_round_context()          # existing fixture helper
        seat_id = round_context.match_context.seats[0].seatId
        interface = ManagedSeatInterface(round_context, seat_id)
        interface.on_illegal_action(decision=None, returned=None)
        interface.on_illegal_action(decision=None, returned=None)
        self.assertEqual(round_context.illegal_actions[seat_id], 2)
```

and a finalization assertion that a seat with recorded illegal actions produces `ManagedSeatRoundResult(illegalActions=2, ...)`. For `managed_match_runtime`, extend the existing `_update_aggregate_results` test (or add one) asserting `runtimeFailures` increments when a result carries `illegalActions=2` and does not when `illegalActions=0`.

- [ ] **Step 2: Run to verify failure**

Run: `uv run python -m unittest quality.tests.test_runtime_controllers -v`
Expected: FAIL with `AttributeError: ... 'on_illegal_action'`

- [ ] **Step 3: Implement**

1. `ManagedSeatInterface`:

```python
    def on_illegal_action(self, decision, returned) -> None:
        """Count an illegal return against this seat (Player already
        logged the ERROR and substituted the first legal action)."""
        self.round_context.record_illegal_action(self.seat_id)
```

2. `RoundExecutionContext.__init__` adds `self.illegal_actions: dict[str, int] = {seat.seatId: 0 for seat in match_context.seats}` and:

```python
    def record_illegal_action(self, seat_id: str) -> None:
        """Tally one substituted illegal return for the seat's results."""
        with self.lock:
            self.illegal_actions[seat_id] += 1
```

3. Both finalizers pass `illegalActions=self.illegal_actions[player.player_id]` into `ManagedSeatRoundResult`.
4. `models.py` — add `illegalActions: int = 0` to `ManagedSeatRoundResult`.
5. `managed_match_runtime._update_aggregate_results` — after the existing outcome tallies:

```python
            if result.illegalActions:
                entry["runtimeFailures"] += 1
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run python -m unittest quality.tests.test_runtime_controllers quality.tests.test_managed_match_api -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add services/native-runtime/src/ticket_to_ride/backend quality/tests
git commit -m "feat(runtime): managed seats substitute illegal returns and surface them as runtime failures"
```

---

### Task 10: Template teaches the new contract

**Files:**
- Modify: `integrations/external/templates/bots/build_your_bot_here.py:6-28`
- Test: `quality/tests/test_bot_template.py:38-44` (and check `quality/tests/test_bot_scaffold.py` still passes — it scaffolds from this file)

**Interfaces:**
- Consumes: `BotDecision` union; `ActionBot` (still act-abstract until Task 11 — the template class defines `decide` and a vestigial `act` is **not** needed because `ActionBot.act` is abstract... it *is* abstract, so the template must keep a one-line `act` stub until Task 11 flips the contract: `def act(self, view, legal_actions): raise RuntimeError("this bot decides via decide()")`. Task 11 deletes it.)
- Produces: a runnable-without-edits template showing `match` dispatch, `random.choice(decision.actions)`, and `decision.claims[0].payments[0]` navigation.

- [ ] **Step 1: Update the template tests**

In `quality/tests/test_bot_template.py` replace `test_template_bot_is_an_action_bot_that_picks_the_first_legal_action` (lines 38-44) with:

```python
    def test_template_bot_completes_a_seeded_game_choosing_canonical_leaves(self) -> None:
        module = load_template_module()
        self.assertTrue(issubclass(module.YourBotName, ActionBot))

        import random
        from ticket_to_ride.engine.game import Game
        from ticket_to_ride.engine.player import Player
        from ticket_to_ride.engine.state.game_context import GameContext

        class _Verifying(module.YourBotName):
            def decide(self, decision):
                chosen = super().decide(decision)
                assert id(chosen) in {id(a) for a in decision.actions}
                return chosen

        class _Silent:
            def record_turn(self, *args, **kwargs):
                return None

        players = [Player(f"p{i}", _Verifying(), f"p{i}", "red") for i in range(2)]
        context = GameContext([p.player_id for p in players], seed=17)
        Game(context, players, _Silent(), 0).play()
```

Keep the placeholder/META/marimo-structure tests unchanged.

- [ ] **Step 2: Run to verify failure**

Run: `uv run python -m unittest quality.tests.test_bot_template -v`
Expected: FAIL — the template still implements `act` only, so `Player.__init__` raises `TypeError`.

- [ ] **Step 3: Rewrite the template's setup and class cells**

Setup cell imports become:

```python
with app.setup(hide_code=True):
    import random
    from typing import Any

    from external.contracts.base_bot import ActionBot
    from ticket_to_ride.engine.decisions import (
        BotDecision, KeepTicketsDecision, SecondDrawDecision, TurnDecision,
    )
```

Class cell:

```python
@app.class_definition
class YourBotName(ActionBot):
    META = BOT_META

    def decide(self, decision: BotDecision) -> Any:
        """Choose one canonical action exposed by the current decision.

        The engine sends a new decision only after something changed:
        applying your first card draw (SecondDrawDecision, with the drawn
        card already in decision.state.hand) or dealing a ticket offer
        (KeepTicketsDecision, with the offer in decision.offer). Always
        return a leaf the decision itself handed you — decision.actions is
        the complete flat menu and random.choice(decision.actions) is
        already a complete bot. Never rebuild an action dataclass by hand;
        the engine rejects anything that is not its own object.
        """
        match decision:
            case TurnDecision():
                return self.choose_turn(decision)
            case SecondDrawDecision():
                return self.choose_second_card(decision)
            case KeepTicketsDecision():
                return self.choose_tickets(decision)

    def choose_turn(self, decision: TurnDecision) -> Any:
        """Hierarchical navigation: claim when possible, otherwise draw.

        decision.claims lists every claimable route with all of its legal
        payments (decision.claims.by_route_id for stable lookups);
        decision.draws.face_up[i] is market slot i or None; pass_action is
        only non-None when nothing else is legal.
        """
        if len(decision.claims):
            return decision.claims[0].payments[0]
        return random.choice(decision.actions)

    def choose_second_card(self, decision: SecondDrawDecision) -> Any:
        """decision.first_draw says what just arrived; face-up locomotives
        are off this menu, so their slots read None."""
        if decision.draws.blind is not None:
            return decision.draws.blind
        return random.choice(decision.actions)

    def choose_tickets(self, decision: KeepTicketsDecision) -> Any:
        """Keep the fewest tickets allowed (decision.minimum_to_keep is 2
        during setup, 1 later); decision.choices.by_indices addresses a
        specific keep-set."""
        return min(decision.actions, key=lambda keep: len(keep.indices))
```

(No `act` stub is needed if Task 11 runs next in sequence and `ActionBot.act` is still abstract — it is, so **do** add the temporary stub `def act(self, view: Any, legal_actions: list[Any]) -> Any: raise RuntimeError("this bot decides via decide()")` and let Task 11 delete it.) Leave the four spectate cells untouched.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run python -m unittest quality.tests.test_bot_template quality.tests.test_bot_scaffold -v`
Expected: PASS, including the marimo `check` structural test.

- [ ] **Step 5: Commit**

```bash
git add integrations/external/templates/bots/build_your_bot_here.py quality/tests/test_bot_template.py
git commit -m "feat(template): teach match-based decide with hierarchical and flat navigation"
```

---

### Task 11: Contract cleanup — `act` is gone

**Files:**
- Modify: `integrations/external/contracts/base_bot.py:56-83`
- Modify: all 7 bots + the template (delete `act` methods and the template stub)
- Modify: `services/native-runtime/src/ticket_to_ride/engine/actions.py:1-7` (module docstring still documents the act contract)
- Test: `quality/tests/test_engine_decisions.py` (append), plus the whole suite

**Interfaces:**
- Produces: `ActionBot` with abstract `decide(self, decision: Any) -> Any` and no `act`. `BaseBot`'s `choose_*` abstract methods stay (the sidecar's wire protocol still exists until Phase 2). `engine/legacy_adapter.py` and `quality/tests/test_legacy_adapter.py` also stay until Phase 2 deletes the whole choose-method surface.

- [ ] **Step 1: Write the failing test**

Append to `quality/tests/test_engine_decisions.py`:

```python
class ContractCleanupTests(unittest.TestCase):
    def test_action_bot_contract_is_decide_only(self):
        from external.contracts.base_bot import ActionBot
        self.assertTrue(getattr(ActionBot.decide, "__isabstractmethod__", False))
        self.assertTrue((ActionBot.decide.__doc__ or "").strip())
        self.assertFalse(hasattr(ActionBot, "act"))

    def test_no_bot_ships_an_act_method(self):
        import external.bots.random_bot as random_bot
        self.assertFalse(hasattr(random_bot.RandomBot, "act"))
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run python -m unittest quality.tests.test_engine_decisions.ContractCleanupTests -v`
Expected: FAIL (`ActionBot` still abstracts `act`).

- [ ] **Step 3: Flip the contract and delete every `act`**

1. `base_bot.py` — replace `ActionBot`:

```python
class ActionBot(BaseBot):
    """Engine-facing bot: implement ``decide(decision) -> Action``.

    ``decision`` is one of the ``BotDecision`` types from
    ``ticket_to_ride.engine.decisions`` — dispatch with ``match`` on the
    concrete type. Whatever you return must be a canonical leaf supplied
    by that decision (``decision.actions`` or any grouped property);
    the engine checks identity and raises IllegalActionError on anything
    else (managed matches substitute, ERROR-log, and count a runtime
    failure instead). The legacy choose_* contract is stubbed out — the
    engine never calls it on a bot that defines decide().
    """

    @abstractmethod
    def decide(self, decision: Any) -> Any:
        """Return one canonical action exposed by ``decision``."""
        raise NotImplementedError
```

keeping the `choose_*` RuntimeError stubs beneath it unchanged.
2. Delete the `act` method from: `random_bot.py`, `example_bot.py`, `qualifier_bot.py`, `fable_best_bot.py`, `codex_best_bot.py`, `bayesian_utility_bot.py`, `xg_bot.py` (also delete XGBot's now-unused `_fallback_action`), and the template's temporary `act` stub from Task 10.
3. `actions.py:1-7` — rewrite the module docstring paragraph that documents `act(view, legal_actions)` + silent substitution to point at `decide` and `engine/decisions.py`, e.g.: "Bots receive these leaves grouped into BotDecision menus (see engine/decisions.py) and return one canonical leaf from `decide(decision)`; an illegal return fails loudly."
4. Sweep for stragglers: `grep -rn "def act(" --include="*.py" services integrations applications operations quality | grep -v legacy_adapter | grep -v node_modules` — expected: no hits outside `engine/legacy_adapter.py` (Phase 2 deletes that file).

- [ ] **Step 4: Full verification**

Run: `uv run test` — expected: PASS.
Run: `uv run python -m unittest external.tests.test_random_bot external.tests.test_bot_api external.tests.test_bot_loader -v` — expected: PASS.
Run: `npx -y pyright` — expected: no new errors vs the Task 1 baseline. This is also the exhaustiveness guarantee: pyright now sees `decide(decision: BotDecision)` matched over three concrete types in every bot.

- [ ] **Step 5: Commit**

```bash
git add -A integrations/external services/native-runtime quality/tests
git commit -m "feat!: retire act(view, legal_actions); ActionBot contract is decide(decision)"
```

---

## Acceptance-criteria traceability

| Spec acceptance criterion | Covered by |
|---|---|
| Every legal action exactly once, no illegal ones, order preserved | Task 2 builder tests (verbatim tuple + exactly-once grouping) |
| Existing seeded games replay identically | Task 8 (`ScriptedBot.decide` + untouched `test_replay`/`test_engine_determinism`) |
| Route + payments without scanning; face-up by market index | Task 2 (`by_route_id`, `FaceUpDrawIndex` alignment tests) |
| Follow-ups carry new state + explicit context | Task 8 `test_second_draw_reports_first_draw_and_updated_hand`, keep-decision tests |
| Callback only when information changes | Structural: `Player.take_turn` emits exactly the three decision points (Task 8) |
| Identity-only selection; loud failure both modes | Task 8 (raise) + Task 9 (substitute/ERROR/count) |
| `random.choice(decision.actions)` is a complete bot | Task 3 RandomBot + template |
| `TunnelDecision` will surface via pyright | Task 11 pyright gate over `match`-dispatched `BotDecision` |
| Template runnable, teaches both paths | Task 10 |
| Docstrings everywhere | Task 1 docstring test (module-wide) + Task 11 contract test |
| No `act` entry points remain (choose-method wire + `LegacyBotAdapter` die in Phase 2) | Task 11 sweep |

Deferred to the **Phase 2 plan** (wire protocol v2): decision-envelope serialization with `selectionId`s, stale-`decisionId` rejection, scrubbing `first_draw.card` for non-acting seats in serialized envelopes, deletion of choose-method endpoints/models/`LegacyBotAdapter`/`ApiBotInterface`. Deferred to **Phase 3 operations**: regenerating `results/decisions.jsonl` / xG datasets (schema v2) and retraining.
