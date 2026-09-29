"""CDP browser adapter. Attaches to a tab in the user's own already-running,
already-authenticated Chrome (launched with --remote-debugging-port) —
never launches or manages its own browser instance, never touches
credentials.
"""

import json
import time

from dcai.adapters import cdp_transport, selectors
from dcai.adapters.base import BrowserAdapter
from dcai.models import BlockedError


class CDPAdapter(BrowserAdapter):
    def __init__(self, port: int):
        self._port = port
        self._session: cdp_transport.CDPSession | None = None
        self._context_id: int | None = None

    def attach(self, url_hint: str | None = None) -> None:
        targets = [t for t in cdp_transport.list_targets(self._port) if t.get("type") == "page"]
        target = next((t for t in targets if "datacamp.com" in t.get("url", "")), None)
        if target is None and url_hint:
            target = cdp_transport.open_new_tab(self._port, url_hint)
        if target is None:
            raise cdp_transport.CDPError(
                "No DataCamp tab found. Open one in your Chrome (with "
                f"--remote-debugging-port={self._port}) or pass a URL to attach to."
            )
        self._session = cdp_transport.CDPSession(target["webSocketDebuggerUrl"])
        self._session.send("Page.enable")
        self._session.send("Runtime.enable")
        self._session.send("DOM.enable")
        # Live-verified: DataCamp's Monaco editor and exercise DOM live in
        # the main frame, not a sandboxed iframe — the default execution
        # context (None) is correct. Drain-and-guess against
        # executionContextCreated events picked up unrelated/short-lived
        # contexts (ad iframes, workers) and crashed Runtime.evaluate with
        # "Cannot find context with specified id".
        self._context_id = None

    def _evaluate(self, expression: str):
        assert self._session is not None
        params = {"expression": expression, "returnByValue": True}
        if self._context_id is not None:
            params["contextId"] = self._context_id
        result = self._session.send("Runtime.evaluate", params)
        return result.get("result", {}).get("value")

    def navigate(self, url: str) -> None:
        assert self._session is not None
        self._session.send("Page.navigate", {"url": url})
        self.wait_for("document.readyState === 'complete'")
        # Exercise workspaces can take 60-90s to spin up (confirmed in the
        # old workflow's operational notes) — wait for real page content
        # (submit control or, on a video page, the continue button) rather
        # than trusting page load alone.
        self.wait_for(selectors.JS_PAGE_READY, timeout_s=100)

    def wait_for(self, js_predicate: str, timeout_s: float = 15) -> bool:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            if self._evaluate(js_predicate):
                return True
            time.sleep(0.2)
        return False

    def eval_text(self, js_expression: str) -> str | None:
        value = self._evaluate(js_expression)
        return value if isinstance(value, str) else None

    def _check_blocked(self) -> None:
        if self._evaluate(selectors.JS_BLOCKED_CHECK):
            raise BlockedError(
                "A CAPTCHA, MFA prompt, or paywall was detected. Complete it "
                "manually in the browser, then re-run."
            )

    def get_editor_content(self) -> str:
        self._check_blocked()
        value = self._evaluate(selectors.JS_GET_MONACO_VALUE)
        if value is None:
            value = self._evaluate(selectors.JS_GET_TEXTAREA_VALUE)
        if value is None:
            raise cdp_transport.CDPError("Could not read editor content (Monaco not found).")
        return value

    def set_editor_content(self, code: str) -> None:
        self._check_blocked()
        js = selectors.JS_SET_MONACO_VALUE.format(code=json.dumps(code))
        ok = self._evaluate(js)
        if not ok:
            raise cdp_transport.CDPError("Could not write editor content (Monaco not found).")

    def select_option(self, option_index: int) -> None:
        # Live-verified (2026-09-29): the `<li data-testid="radio-list-
        # option">` itself has no click handler — the real
        # `<input type="radio">` is nested inside it (via a <label>).
        # Clicking the <li> silently does nothing (no option gets checked);
        # clicking the actual <input> does.
        ok = self._evaluate(
            f"(() => {{ const els = document.querySelectorAll({json.dumps(selectors.SELECTOR_MCQ_OPTIONS)}); "
            f"const el = els[{option_index}]?.querySelector('input[type=\"radio\"]'); "
            "if (!el) return false; el.click(); return true; })()"
        )
        if not ok:
            raise cdp_transport.CDPError(f"MCQ option not found at index {option_index}")

    def click(self, selector: str) -> None:
        # el.click() rather than synthetic Input.dispatchMouseEvent coords:
        # live-verified (2026-09-29) that DataCamp's submit button silently
        # swallows synthetic mouse-event clicks (no request fired at all)
        # but responds correctly to a direct DOM click() call.
        ok = self._evaluate(
            f"(() => {{ const el = document.querySelector({json.dumps(selector)}); "
            "if (!el) return false; el.click(); return true; })()"
        )
        if not ok:
            raise cdp_transport.CDPError(f"Element not found for click: {selector}")

    def submit(self) -> None:
        self.click(selectors.SELECTOR_SUBMIT_BUTTON)

    def click_button_with_text(self, text: str) -> bool:
        return bool(self._evaluate(
            "(() => { const b = Array.from(document.querySelectorAll('button'))"
            f".find(b => b.innerText.trim() === {json.dumps(text)}); "
            "if (!b) return false; b.click(); return true; })()"
        ))

    def get_feedback(self) -> tuple[str, str | None]:
        # Live-verified (2026-09-29): a correct submission renders no
        # `.dc-sct-feedback` panel — instead a "Continue" button appears
        # (confirmed against an XP increase in the header). Wait for
        # whichever shows up first rather than inferring success from the
        # panel's mere absence, which could just mean grading is still in
        # flight.
        found = self.wait_for(selectors.JS_HAS_FEEDBACK_OR_CONTINUE, timeout_s=15)
        if not found:
            return "pending", None
        if self._evaluate(selectors.JS_HAS_CONTINUE_BUTTON) and not self._evaluate(selectors.JS_HAS_FEEDBACK):
            return "success", None
        # The panel mounts before React fills in its text — wait for the
        # title to actually have content rather than reading it immediately.
        title_js = selectors.JS_FEEDBACK_TEXT.format(selector=selectors.SELECTOR_FEEDBACK_TITLE)
        self.wait_for(f"!!({title_js})", timeout_s=5)
        title = self.eval_text(title_js) or ""
        content = self.eval_text(
            selectors.JS_FEEDBACK_TEXT.format(selector=selectors.SELECTOR_FEEDBACK_CONTENT)
        ) or title
        if "error" in title.lower():
            return "error", content
        return "wrong_answer", content

    def close(self) -> None:
        if self._session:
            self._session.close()
