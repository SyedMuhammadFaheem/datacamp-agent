# dcai — Build state and verification notes

Maintainer's working notes: what was verified live against DataCamp's UI, known risks, and the phase plan.
DataCamp's markup changes over time, so treat the selector findings below as a dated snapshot.
Last updated: 2026-09-29

## Current phase
Phase 1: first vertical slice — live-verified against a real course
(`working-with-the-openai-api`, exercises 1-6) via CDP. All three exercise
kinds it should handle (coding, MCQ, video) now solve end-to-end and are
confirmed accepted by DataCamp across repeated live runs. The three gaps
flagged in the first verification pass (MCQ, cache correctness, video) are
now fixed — see "Second pass" below.

## Live verification findings (2026-09-29)
Fixed (real bugs, not the pre-existing "unverified placeholder" selectors):
- `cdp_transport.open_new_tab` used GET on `/json/new` — modern Chrome
  returns 405; needs PUT.
- Chrome also now requires launching with `--remote-allow-origins=*` (or
  the specific origin) for the CDP websocket handshake to succeed at all —
  add this flag to the README launch command.
- `CDPAdapter._find_execution_context` guessed a context from drained
  `Runtime.executionContextCreated` events and regularly picked a
  dead/unrelated one, crashing every `Runtime.evaluate` with "Cannot find
  context with specified id". DataCamp's exercise DOM (Monaco + sidebar)
  lives in the main frame — removed the guessing, default context (`None`)
  is correct and sufficient.
- `CDPAdapter.click()` interpolated the selector into a single-quoted JS
  string unescaped — any selector containing a single quote broke the
  query silently. Now uses `json.dumps()`.
- `CDPAdapter.click()` used synthetic `Input.dispatchMouseEvent` coordinate
  clicks — DataCamp's submit button silently swallowed these (no request
  fired at all, confirmed via Network domain). Switched to a direct
  `el.click()` DOM call, which works reliably.
- `selectors.SELECTOR_SUBMIT_BUTTON`, `SELECTOR_INSTRUCTIONS`,
  `SELECTOR_FEEDBACK_*` were unverified placeholders that never matched
  live markup (`data-testid`/class names DataCamp doesn't use). Replaced
  with real selectors found via live DOM inspection:
  - submit: `[data-cy="submit-button"]` (consistent across MCQ/coding).
  - instructions: `[data-cy='left-panel'] .dc-panel__body` (MCQ layout) or
    `.exercise--sidebar-content` (coding layout) — DataCamp uses two
    different sidebar DOM structures per exercise type.
  - feedback: there is no distinct success root — `.dc-sct-feedback` only
    renders for wrong-answer/error outcomes; a correct submission renders
    **no panel** and instead shows a "Continue" button with an XP
    increase. `get_feedback()` now waits for either and classifies
    accordingly, plus waits for the panel's title text to actually
    populate (it mounts before React fills it in — reading immediately
    can capture an empty string).

## Second pass (2026-09-29): the three flagged gaps, fixed and live-verified

**MCQ solve path.** `classify()` now checks for real MCQ options
(`[data-testid="radio-list-option"]`) before falling back, and falls back to
`VIDEO`/`THEORY` (not `MCQ`) when there's no Monaco and no options — see
video fix below. `normalize()` extracts the option texts into
`Exercise.context["options"]`. `llm_solver.solve_mcq()` asks the LLM for the
exact option text (not an index — order isn't guaranteed stable, matching
by text is safer). `pipeline._submit_and_validate` calls
`adapter.select_option(options.index(content))` instead of
`set_editor_content` for MCQ. The code-repair loop no longer runs for MCQ
(a wrong pick has no code to repair; MCQ failures are just recorded).
Live gotcha found while fixing this: `select_option`'s first
implementation clicked the `<li data-testid="radio-list-option">` itself,
which live-verified does nothing (no click handler) — the real
`<input type="radio">` is nested inside via a `<label>`; fixed to click that
instead, confirmed by the input's `checked` state flipping. Verified
end-to-end on `working-with-the-openai-api` ex=2 (correct answer accepted,
XP increase).

**Video/non-exercise pages.** `classify()` now returns `VIDEO` when neither
Monaco nor MCQ options are present but a "Got It!" button is (a course-intro
video), or `THEORY` if none of the three signals match. `pipeline.solve()`
short-circuits both to `_advance_non_exercise()`, which clicks "Got It!" via
the new `BrowserAdapter.click_button_with_text()` and records success/failure
— no LLM call, no cache, no editor write. Also fixed `navigate()`, which
previously waited up to 100s for the submit button specifically on every
page; it now waits for submit-button-OR-Got-It-button (`JS_PAGE_READY`),
since video pages have neither. Verified end-to-end on ex=1 and ex=4.

**Cache success-gating, plus a deeper bug it exposed.** The original ask was
"cache returns unverified content" — true, but fixing just that surfaced a
worse, pre-existing bug: `find_current_solution_by_hash` joined
`solutions → exercises` and filtered on `exercises.instructions_hash`. Since
`start.py` hardcodes `exercise_number=1` for every exercise (a known,
documented Phase-1 limitation), *every* exercise in a run shares one mutable
DB row, and `upsert_exercise` overwrites that row's `instructions_hash`
column on every call — so by the time the cache query ran, the WHERE clause
was comparing the just-written parameter against itself and matched
*any* solution ever attached to that row. Live-caught concretely: an MCQ
answer ("2015") got served as "the cached solution" for a later, unrelated
coding exercise and was submitted as Python code. Fix: added
`solutions.instructions_hash` (set once at insert time, never mutated) and
query solutions directly by that column — no join through the shared
exercises row at all. Combined with an `EXISTS(attempts.result='success')`
gate. Regression test added
(`test_cache_does_not_leak_across_exercises_sharing_a_db_row`) reproducing
the exact scenario. Schema change: `solutions` gained a NOT NULL
`instructions_hash` column — no migration framework exists yet (Phase 1,
pre-real-usage), so this requires a fresh DB file for anyone with an
existing one.

All three fixes verified via `dcai start` itself (not manual scripts) across
repeated runs: ex=1 (video), ex=2 (MCQ), ex=3/5/6 (coding) all solved and
confirmed accepted by DataCamp. 18 offline tests pass (6 new, covering all
three fixes plus the cache-leak regression).

**Known remaining risk, not chased further:** one coding run (ex=5)
captured a wrong `starter_code`/editor snapshot (an unrelated exercise's
text) in a single normalize() call that did not reproduce on retry or on a
fresh exercise (ex=6) — looks like a one-off DOM/Monaco read race right
after navigation, not a systemic bug. It did not cause a silent bad
submission (DataCamp correctly rejected the resulting attempt; `dcai`
correctly recorded it as failed, per the "never fabricate success" rule).
Revisit only if it reproduces.

**Known remaining LLM-quality issue, not a dcai bug:** the coding solve
prompt sometimes reinstantiates a client/variable the exercise already
provides (`client = OpenAI()` when the sandbox already defines `client`).
Added one line to `SYSTEM_PROMPT` telling the model not to redefine
pre-existing sandbox variables — reduced but did not eliminate this;
inherent to the model, not the pipeline. The repair loop is the designed
safety net for this and correctly attempts a fix before giving up.

## Done
- [x] Phase 0 (partial): repo scaffold, `schema.sql`, package layout, CLI skeleton.
- [x] Phase 1 code: `CDPAdapter` (attach/navigate/editor read-write/click/submit/feedback), normalization for `type=coding, language=python`, solver pipeline (cache → LLM → submit → validate → repair, cap=1), `dcai start <url>` wired end-to-end.
- [x] Two LLM providers: `llm/claude_code.py` (`claude-code`, default — subscription-authenticated via the `claude` CLI, no API key) and `llm/claude.py` (`claude-api` — direct `anthropic` SDK, metered billing, ~10-50x fewer tokens per call). Both verified with real (non-mocked) calls through `llm_solver.solve()`. `token_usage.cost_usd`/`.provider` now populated end-to-end from whichever provider actually ran.
- [x] `dcai status`, `dcai stats`, `dcai notes`, `dcai resume` (Phase-1-scoped: re-solves last checkpointed URL only, no multi-exercise traversal yet), `dcai migrate`.
- [x] `dcai migrate` run and verified against the real legacy course
      (`courses/deep-learning-for-images-with-pytorch/`): 39 exercises,
      4 chapters, 86 memory rows imported correctly, idempotent on re-run.
- [x] Offline test suite (12 tests): schema constraints, `instructions_hash` determinism, solver pipeline token-efficiency invariants (cache hit → 0 LLM calls, fresh → 1 call, repair capped at 1 extra call), migration correctness + idempotency.
- [x] `dcai start` verified to fail cleanly (clear error, not a traceback) when no Chrome CDP endpoint is reachable.

## In progress
- [x] **Live Monaco/DOM verification** — done 2026-09-29 against `working-with-the-openai-api` ex. 1-4. See "Live verification findings" above.

## Next up
- **The `exercise_number=1` hardcoding is now the top-priority fix**, not a
  someday item — the cache-leak bug above is a direct, live-demonstrated
  consequence of it, and it will keep causing cross-exercise data
  confusion (in `exercises`, `state`, `course_memory`) the moment `resume`
  or any multi-exercise loop is built on top of it. Needs real
  chapter/exercise-position tracking before Phase 2 traversal.
- Phase 2: deterministic solver tier (MCQ answer-key, regex code patterns) once real usage shows patterns worth hardcoding; multi-exercise/chapter traversal for `resume`; `state`/`course_memory` writes during live solving (currently only written by `migrate`).
- Phase 3: SQL/R exercise types — MCQ and video are now done (see above); SQL/R remain.
- Phase 4: projects/assignments (distinct DOM shape).
- Phase 5: Claude Chrome fallback adapter.
- Add a schema migration mechanism before this leaves Phase 1 — the
  `solutions.instructions_hash` column added this session required
  deleting the local dev DB; that's fine pre-release, not once there's real
  user progress to preserve.

## Known risks / open questions
- Monaco write mechanism (`model.setValue()` + textarea event dispatch) — **confirmed working** live 2026-09-29; model-by-URI selection (`code-editor`) held up against the real page.
- Iframe/execution-context targeting — **resolved**: DataCamp's exercise DOM is main-frame only, no iframe targeting needed; the old best-effort guessing was itself the bug (see findings above).
- Submit button / feedback selectors — **confirmed** live 2026-09-29 (see findings above).
- MCQ solve path and video/non-exercise page handling — **fixed and live-verified** 2026-09-29 (see "Second pass" above).
- Cache correctness (success-gating) — **fixed and live-verified** 2026-09-29, including the deeper cross-exercise leak it exposed (see "Second pass" above).
- One-off stale `starter_code`/editor-content capture on a single live run (ex=5), did not reproduce — see "Second pass" above. Watch for recurrence.

## Key decisions log
- 2026-09-28: Python + raw CDP (via `websocket-client`) chosen over Playwright/Selenium per hard requirement; attaches to the user's own already-authenticated Chrome rather than launching a managed instance.
- 2026-09-28: argparse over click/typer; dataclasses over pydantic; no ORM (hand-written parameterized SQL in `db/repo.py`) — kept dependencies to `websocket-client` + optional `anthropic`.
- 2026-09-28: First vertical slice deliberately excludes the deterministic solver tier, multi-exercise looping, and non-coding exercise types — added once real usage justifies them, not speculatively.
- 2026-09-28: Old `CLAUDE.md` browser-agent workflow retired; its recorded operational notes (Monaco model-by-URI selection, MCQ keyboard-shortcut workaround, 60-90s workspace init) were mined out of `state.json` and encoded directly into `adapters/selectors.py` and `adapters/cdp.py` rather than being rediscovered from scratch.
- 2026-09-29: `claude-code` (subscription auth via the `claude` CLI) made the default LLM provider over `claude-api`, despite measuring ~10-50x more tokens per call (fixed Claude Code overhead didn't hit Anthropic's prompt cache across repeat calls in testing) — explicit user choice to avoid a separate metered API bill, traded off against `dcai`'s own low-token-consumption goal. `claude-api` remains available via `--llm-provider claude-api` for users who'd rather optimize per-call cost.
