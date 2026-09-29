from abc import ABC, abstractmethod


class BrowserAdapter(ABC):
    """Drives a browser to interact with DataCamp's UI. Every method
    returns only text/attribute strings or performs a UI action — never
    raw HTML or a screenshot — so there is no path for a full page to
    reach an LLM prompt through this interface.

    Implementations must attach to a browser the user already controls
    (e.g. their own already-authenticated Chrome) rather than launching
    and driving a fresh, credential-holding session themselves.
    """

    @abstractmethod
    def attach(self, url_hint: str | None = None) -> None: ...

    @abstractmethod
    def navigate(self, url: str) -> None: ...

    @abstractmethod
    def wait_for(self, js_predicate: str, timeout_s: float = 15) -> bool: ...

    @abstractmethod
    def eval_text(self, js_expression: str) -> str | None: ...

    @abstractmethod
    def get_editor_content(self) -> str: ...

    @abstractmethod
    def set_editor_content(self, code: str) -> None: ...

    @abstractmethod
    def select_option(self, option_index: int) -> None: ...

    @abstractmethod
    def click(self, selector: str) -> None: ...

    @abstractmethod
    def click_button_with_text(self, text: str) -> bool:
        """Clicks the first <button> whose exact innerText matches. Returns
        whether one was found (for controls with no stable selector, e.g.
        a video's "Got It!" continue button)."""
        ...

    @abstractmethod
    def submit(self) -> None: ...

    @abstractmethod
    def get_feedback(self) -> tuple[str, str | None]:
        """Returns (result, error_text) where result is one of
        'success' | 'error' | 'wrong_answer' | 'pending'."""
        ...

    @abstractmethod
    def close(self) -> None: ...
