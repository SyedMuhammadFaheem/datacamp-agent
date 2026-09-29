"""All DOM selectors and JS snippets used against the live DataCamp UI live
here, so markup drift is a one-file fix.

Selectors marked "live-verified" were confirmed against the real DataCamp UI
via CDP inspection on 2026-09-29 (see docs/project-state.md). Ones marked
"placeholder" (hints, editor language) have not been verified and may need
adjusting. DataCamp can change its markup at any time; when a selector drifts,
fixing it here is the intended one-file change.
"""

# Monaco editor read: prefer the model whose URI contains 'code-editor'
# over getModels()[0] — DataCamp exercises can have multiple Monaco models
# open at once (e.g. a shell/config model alongside the actual script.py),
# and getModels()[0] is not reliably the one the user edits. Confirmed the
# hard way in the old workflow (ch3 ex11: setValue hit the wrong model).
JS_GET_MONACO_VALUE = """
(() => {
  const models = window.monaco?.editor?.getModels() ?? [];
  const model = models.find(m => m.uri.toString().includes('code-editor')) ?? models[0];
  return model ? model.getValue() : null;
})()
"""

# Fallback: Monaco keeps a hidden textarea in sync with the model.
JS_GET_TEXTAREA_VALUE = "document.querySelector('textarea.inputarea')?.value ?? null"

JS_SET_MONACO_VALUE = """
(() => {{
  const models = window.monaco?.editor?.getModels() ?? [];
  const model = models.find(m => m.uri.toString().includes('code-editor')) ?? models[0];
  if (!model) return false;
  model.setValue({code});
  const ta = document.querySelector('textarea.inputarea');
  if (ta) {{
    ta.dispatchEvent(new Event('input', {{ bubbles: true }}));
    ta.dispatchEvent(new Event('change', {{ bubbles: true }}));
  }}
  return true;
}})()
"""

# Submit / run button — live-verified via CDP inspection (2026-09-29).
# Double-quoted attribute value: cdp.py's click() embeds this inside a
# single-quoted JS string, so a single-quoted value here would break it.
SELECTOR_SUBMIT_BUTTON = '[data-cy="submit-button"]'
JS_HAS_SUBMIT_BUTTON = f"!!document.querySelector(\"{SELECTOR_SUBMIT_BUTTON}\")"

# Feedback after submission — live-verified via CDP inspection (2026-09-29).
# `.dc-sct-feedback` itself is NOT a reliable signal: on coding exercises it
# only mounts for a wrong/error outcome, but on MCQ pages it's a persistent
# hint-nav container present at all times regardless of submission result.
# `.dc-sct-feedback__title` only renders when there's an actual result
# message on either exercise type, so that's the real "has feedback" check.
SELECTOR_FEEDBACK_TITLE = ".dc-sct-feedback__title"
SELECTOR_FEEDBACK_CONTENT = ".dc-sct-feedback__content"
JS_FEEDBACK_TEXT = "document.querySelector('{selector}')?.innerText?.trim() ?? null"
JS_HAS_FEEDBACK = f"!!document.querySelector('{SELECTOR_FEEDBACK_TITLE}')"

# Positive success confirmation — live-verified (2026-09-29): a correct
# submission has no error/wrong-answer panel at all, so success is
# confirmed by this "Continue" button appearing instead (also confirmed
# against an XP increase in the header), not by the panel's absence alone.
JS_HAS_CONTINUE_BUTTON = (
    "Array.from(document.querySelectorAll('button')).some("
    "b => b.innerText.trim() === 'Continue')"
)
JS_HAS_FEEDBACK_OR_CONTINUE = f"({JS_HAS_FEEDBACK}) || ({JS_HAS_CONTINUE_BUTTON})"

# CAPTCHA / paywall pre-check — checked before any other extraction.
JS_BLOCKED_CHECK = """
(() => {
  const captcha = document.querySelector(
    "iframe[src*='recaptcha'], iframe[src*='hcaptcha']"
  );
  const paywall = document.body.innerText.includes('Upgrade to continue');
  return !!(captcha || paywall);
})()
"""

# MCQ options — live-verified via CDP inspection (2026-09-29).
SELECTOR_MCQ_OPTIONS = '[data-testid="radio-list-option"]'
JS_HAS_MCQ_OPTIONS = f"!!document.querySelector('{SELECTOR_MCQ_OPTIONS}')"
JS_GET_MCQ_OPTIONS = (
    f"JSON.stringify(Array.from(document.querySelectorAll('{SELECTOR_MCQ_OPTIONS}'))"
    ".map(el => el.innerText.trim()))"
)

# Video/theory "continue" control — live-verified (2026-09-29): non-exercise
# pages (course intro videos etc.) have no Monaco editor and no MCQ options,
# only this button. `click_button_with_text` matches by exact innerText
# since there's no stable data-cy/data-testid on it.
GOT_IT_BUTTON_TEXT = "Got It!"
JS_HAS_GOT_IT_BUTTON = (
    "Array.from(document.querySelectorAll('button')).some("
    f"b => b.innerText.trim() === {GOT_IT_BUTTON_TEXT!r})"
)

# Page-ready signal for navigate() — any of the three page kinds dcai
# handles, not just the submit button (a video page has none).
JS_PAGE_READY = f"({JS_HAS_SUBMIT_BUTTON}) || ({JS_HAS_GOT_IT_BUTTON})"

# Instructions pane — live-verified via CDP inspection (2026-09-29). No
# stable data-cy/data-testid on the text container itself; MCQ and coding
# exercises use two different (non-hashed) DataCamp layout classes.
SELECTOR_INSTRUCTIONS = "[data-cy='left-panel'] .dc-panel__body, .exercise--sidebar-content"
JS_GET_INSTRUCTIONS = f"document.querySelector(\"{SELECTOR_INSTRUCTIONS}\")?.innerText?.trim() ?? null"

# Revealed hints — placeholder.
SELECTOR_HINTS = "[data-testid='hint'], .exercise-hint"
JS_GET_HINTS = (
    "Array.from(document.querySelectorAll(\"" + SELECTOR_HINTS + "\"))"
    ".map(el => el.innerText.trim())"
)

# Monaco language marker — placeholder.
JS_GET_EDITOR_LANGUAGE = "window.monaco?.editor?.getModels()?.[0]?.getLanguageId() ?? null"

# Is this a coding exercise at all (Monaco present)?
JS_HAS_MONACO_EDITOR = "!!document.querySelector('.monaco-editor')"
