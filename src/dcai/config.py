import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Config:
    db_path: Path
    cdp_port: int
    llm_provider: str
    verbose: bool = False


def default_db_path() -> Path:
    data_home = os.environ.get("XDG_DATA_HOME", "~/.local/share")
    return Path(data_home).expanduser() / "dcai" / "dcai.db"


def load_config(
    db_path: str | None = None,
    cdp_port: int | None = None,
    llm_provider: str | None = None,
    verbose: bool = False,
) -> Config:
    return Config(
        db_path=Path(db_path).expanduser() if db_path else default_db_path(),
        cdp_port=cdp_port or int(os.environ.get("DCAI_CDP_PORT", "9222")),
        llm_provider=llm_provider or os.environ.get("DCAI_LLM_PROVIDER", "claude-code"),
        verbose=verbose,
    )
