---
name: ticket-to-ride-readme
description: Rewrite or review documentation for this Python Ticket to Ride AI course project using current source evidence, runnable examples, and precise experiment claims. Use for its README and related project documentation.
---

# Ticket to Ride README writing

Unslop profile for README documentation for a Python AI course project that evaluates Ticket to Ride bots.

Read the current dependency manifest, launcher, bot template, and relevant experiment scripts before changing run instructions. Treat this profile's repository details as checks to revisit when the code changes. The observations behind it are in [analysis.md](analysis.md).

## Unsupported specifics to avoid

- Do not substitute plausible packages such as `ttr`, `ttr_arena`, or a `ttr-arena` CLI for the repository's actual commands. Check command flags, import paths, output locations, and required extras against the files that implement them.
- Do not default to a `requirements.txt` and manual virtualenv recipe for this uv project. Several bot modules import marimo, so a bot or test command can need the `notebooks` extra even without a browser. Training commands also need the `xgb` extra.
- Do not describe every bot as a notebook. Check each file; XG Bot is currently a Python module. Use the real bot metadata and `act(view, legal_actions)` contract instead of invented lifecycle hooks.
- Do not imply that opening a bot notebook saves a match to PocketBase. Explain the storage used by the workflow being documented. Do not make the database a prerequisite for an in-memory game.
- Do not give `pocketbase.exe` as the executable for every platform. Verify platform paths and the launcher's binary override.
- Do not add CI badges, a project license, grading thresholds, submission branches, academic-integrity policies, team contributions, or deadlines without supporting repository files or the supplied assignment. Distinguish the group's project from a hypothetical bot-programming assignment.

## Performance claims to avoid

- Avoid “full implementation of Ticket to Ride rules” unless the specific edition's mechanics are implemented and verified. Check ferry payments, tunnel handling, and stations separately.
- Avoid “same seed means the same game” without checking engine randomness and bot randomness. The current replay contract uses the engine seed plus the action sequence.
- Do not turn 100 games, seed 42, or an example leaderboard into evidence. Those are recurring sample defaults. State what a command runs and label proposed experiments separately from completed measurements.
- Do not equate a trainer's fit report with held-out accuracy or wins against other bots. Verify the evaluation split. Document XG Bot's model-loading fallback so a fallback game cannot be mistaken for a learned-policy result.
- Do not infer that a bot named “Best” wins the comparison. Preserve names without converting them into rankings.

## Prose defaults to avoid

- Cut “handles everything so you can focus on strategy,” “rather than plumbing,” “lightweight framework,” and similar promises when they replace an explanation of what the reader can run.
- Do not repeat the launcher command and architecture ownership labels across several introductions. Put prerequisites next to the command they affect, and link to deeper architecture notes.
- Skip “That's it,” “Good luck building your railroads,” train-emoji sign-offs, and recaps that repeat the opening. Avoid promising a five-minute setup unless it was measured under stated conditions.
- Do not build every list from bold labels followed by em-dash explanations. Use tables, lists, headings, and ordinary sentences where the content benefits from them; do not ban those formats or force novelty.

## Final review

Check local links and exercise the smallest useful run example. Separate validation performed now from untested workflows. Preserve technical terms such as seed, replay, win rate, and time budget when they communicate necessary facts. A less generic README should be more useful to someone running this repository, not merely different in tone.
