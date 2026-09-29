from dcai.adapters.base import BrowserAdapter
from dcai.llm.base import LLMProvider, LLMResponse


class FakeBrowserAdapter(BrowserAdapter):
    """In-memory adapter for offline pipeline tests."""

    def __init__(self, feedback: tuple[str, str | None] = ("success", None), got_it_present: bool = True):
        self.editor_content = ""
        self.submitted: list[str] = []
        self.selected_option: int | None = None
        self.clicked_button_texts: list[str] = []
        self._feedback = feedback
        self._got_it_present = got_it_present

    def attach(self, url_hint: str | None = None) -> None:
        pass

    def navigate(self, url: str) -> None:
        pass

    def wait_for(self, js_predicate: str, timeout_s: float = 15) -> bool:
        return True

    def eval_text(self, js_expression: str) -> str | None:
        return None

    def get_editor_content(self) -> str:
        return self.editor_content

    def set_editor_content(self, code: str) -> None:
        self.editor_content = code

    def select_option(self, option_index: int) -> None:
        self.selected_option = option_index

    def click(self, selector: str) -> None:
        pass

    def click_button_with_text(self, text: str) -> bool:
        self.clicked_button_texts.append(text)
        return self._got_it_present

    def submit(self) -> None:
        self.submitted.append(self.editor_content)

    def get_feedback(self) -> tuple[str, str | None]:
        return self._feedback

    def close(self) -> None:
        pass


class FakeLLMProvider(LLMProvider):
    """Returns scripted responses in order; counts calls."""

    def __init__(self, responses: list[str]):
        self._responses = list(responses)
        self.calls = 0

    def complete(self, system: str, user: str, max_tokens: int) -> LLMResponse:
        self.calls += 1
        text = self._responses.pop(0) if self._responses else "pass"
        return LLMResponse(text=text, input_tokens=10, output_tokens=5, model="fake-model")
