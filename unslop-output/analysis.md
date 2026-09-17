# README writing analysis

Domain: README documentation for a Python AI course project that evaluates Ticket to Ride bots.

## Corpus and method

Ran [unslop](https://github.com/mshumer/unslop), revision `edcb62386d129c65e4395f0cfcc9168eb1ba2148`, in a temporary clone using its Python virtual environment. The text run requested 12 samples with concurrency 3. No visual analysis or screenshots were needed.

The first run let the sample generator inspect the unslop clone. Several outputs discussed a repository mismatch instead of writing documentation. That corpus and its profile were rejected for this task: the profile even discouraged mentioning unsupported claims and missing code, which would undermine an accurate README.

The retained run reused unslop's original generated prompts, adding an instruction to produce standalone synthetic writing examples without inspecting the working directory. No project files or repository-derived fact sheet were sent to Claude. Automatic approval review rejected a proposed fact-sheet run because it would transfer repository-derived information to that external service; the synthetic run was approved instead.

The retained inputs are in [prompts.json](prompts.json), with all 12 outputs under [samples/](samples/). Sample IDs below refer to filenames: `0000` means `sample_0000.md`. Counts are the number of files containing a pattern, not the number of occurrences. I reviewed every sample and checked the listed counts against the text locally.

## Repeated patterns

| Pattern | Count | Sample IDs | Evidence and implication |
| --- | --- | --- | --- |
| Plausible placeholder APIs and commands | 7/12 | 0000, 0001, 0002, 0003, 0004, 0007, 0011 | Examples include `python -m ttr.harness`, `from ttr.agent import Agent`, and `ttr-arena register`. A hypothetical command must not become a repository run instruction without checking its entry point. |
| Added course enforcement rules | 3/12 | 0001, 0004, 0007 | Departmental reporting rules, mandatory grading timeouts, and submissions being returned without grading are asserted beyond what the corresponding prompts specify. The supplied assignment must determine course policy. |
| Complete-rule claims | 2/12 | 0000, 0005 | “Full Ticket to Ride game engine” and “full implementation of Ticket to Ride rules” conceal which edition and mechanics are implemented. |
| The same seed example | 4/12 | 0000, 0001, 0004, 0011 | Each uses `seed=42` or `--seed 42`. A familiar seed is harmless, but it does not establish that bot choices and engine shuffles share a random generator. |
| A default batch size of 100 games | 5/12 | 0000, 0001, 0006, 0007, 0011 | Only prompt 0006 explicitly requests 100 games. In the other four, the number is a default example, not an experiment-design justification. |
| “Focus on strategy” promise | 2/12 | 0000, 0005 | Both say the framework lets the reader “focus on strategy.” Neither phrase explains the concrete bot interface or what the harness measures. |
| Celebratory or recap endings | 3/12 | 0001, 0002, 0010 | “Good luck, and have fun,” “That's it — you just,” and “Putting It Together” add a stock sign-off or restate prior content. |
| Bold label followed by an em-dash explanation | 2/12 | 0005, 0006 | Repeated feature/scoring bullets use this exact format. This is a minor stylistic observation, not a reason to ban readable lists. |

Reproducibility claims need a semantic check as well as phrase counts. Sample 0004 promises “Same seed + same bots ⇒ same game, every time,” while 0009 says a seed can reproduce any turn byte for byte. The real engine separates deck randomness from RandomBot's global random choices and records actions for replay. The README therefore explains both seeds and the action log.

## Sampling limits

These are synthetic README sections of different lengths, generated with Claude Code's configured default model. The run did not pin a model version. The model received no subject-repository source files. Hypothetical implementation details were permitted, so their presence is not evidence that the model would invent facts when supplied with code.

Some patterns were requested: prompt 0008 asks for badges and a table of contents; 0006 asks for 100 games and a results table; 0007 supplies rubric weights. Those requested features are not independent evidence of a model default. Headings, tables, code fences, and lists remain useful documentation tools.

The sample count is small and the prompts cover both full READMEs and individual sections. Frequencies describe this corpus only. The finished [skill.md](skill.md) combines the reviewed patterns with a separate local source audit; it does not turn every recurring feature into a prohibition.

The generated analysis and skill were both reviewed and revised. The analysis conflated bold lead-ins with the narrower bold-label-plus-em-dash pattern and listed incorrect sample IDs for 100-game examples. The table above uses corrected counts. The generated skill also banned useful terms such as “time budget,” discouraged stating the working directory, and restricted punctuation mechanically. Those rules were removed. Necessary technical information and clear formatting take precedence over stylistic variety.

## Before/after review

The tool's [test prompt](before-after/test-prompt.txt), [before](before-after/before.md), and [after](before-after/after.md) are retained. This comparison used the generated, unreviewed profile, not the finished local skill. The after sample is shorter and uses fewer headings, but its scoring description changes the tiebreaker from overall win rate to head-to-head wins. Both versions explain a tiebreaker using unequal average scores. These are synthetic examples with unreliable scoring claims, not project results or evidence that the generated profile improved correctness.

The final README was checked against the locally reviewed skill and repository implementation. Source accuracy, working instructions, and clear experiment limits were the acceptance criteria; shorter prose alone was not.

## Local repository review

The original README repeated “native” 13 times, `uv run run` seven times, and the Windows `pocketbase.exe` path three times. It spent substantial space on ownership boundaries while omitting the bot comparison, research commands, and XGBoost workflow.

The rewrite replaces that emphasis with executable entry points and their prerequisites. It documents all seven bots, notebook-only games, stored matches, platform-specific PocketBase paths, tournament outputs, training artifacts and fallback behavior, implemented Europe rules, and the supplied CSC 4240/5240 deliverables. It makes no measured bot-performance claim.

Validation: the README's headless game command completed; all local Markdown link targets exist; the four research CLIs loaded with `--help`; 364 main tests and 8 external integration tests passed. The GUI was not manually exercised and a new XGBoost training experiment was not run for this documentation change.
