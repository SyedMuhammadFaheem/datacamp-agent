# Contributing to dcai

Thanks for helping! Some ground rules keep this project useful and on the right side of the platform it drives.

## Ground rules

- **Stay within normal access.** dcai drives the user-facing UI of a browser the user is already logged in to.
  Contributions that bypass authentication, CAPTCHAs, MFA, paywalls, rate limits or other access controls, use
  undocumented APIs, or scrape at scale will not be accepted.
- **Token frugality is a core goal.** The only thing that may reach an LLM prompt is the small normalised
  `Exercise` struct (`instructions`, `starter_code`, `context`, `hints`, `error_output`) — never raw HTML or
  screenshots. Prefer cache and deterministic solving over another LLM call.
- **Never fabricate success.** A run is only "solved" when the UI confirms it.
- **Keep it small.** No new dependencies or abstractions without a clear need (there is one runtime dependency).

## Development setup

Requires Python ≥ 3.11.

```bash
git clone https://github.com/SyedMuhammadFaheem/datacamp-agent.git
cd datacamp-agent
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,claude]"
```

## Before opening a pull request

```bash
ruff check src tests
pytest
```

- Tests are offline: use `tests/fakes.py` (`FakeBrowserAdapter`, `FakeLLMProvider`); don't hit DataCamp or a real
  LLM in tests.
- All DOM selectors and injected JS live in `src/dcai/adapters/selectors.py`. If DataCamp's markup drifts, fix it
  there and note in the PR how you verified it against the live page.
- **Do not commit** course content, solutions, your database, credentials, or screenshots of exercises.
- Update `README.md` / `CHANGELOG.md` when behaviour or CLI options change.

## Reporting bugs and security issues

Use the issue templates. For vulnerabilities follow [SECURITY.md](SECURITY.md) instead of opening a public issue.

By contributing, you agree that your contributions are licensed under the [MIT License](LICENSE).
