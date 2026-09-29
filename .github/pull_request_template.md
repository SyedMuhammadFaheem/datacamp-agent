## What and why

<!-- What does this change, and why? Link the issue if there is one. -->

## Checklist

- [ ] `ruff check src tests` and `pytest` pass
- [ ] Tests added/updated (offline; no live DataCamp or real LLM calls)
- [ ] No bypassing of authentication, CAPTCHA/MFA, paywalls or rate limits
- [ ] Only the normalised `Exercise` struct reaches LLM prompts (no raw HTML/screenshots)
- [ ] No course content, solutions, database files or credentials committed
- [ ] Selector changes were checked against the live page (describe how)
- [ ] README / CHANGELOG updated if behaviour or CLI options changed
