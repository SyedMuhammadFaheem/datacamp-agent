# Changelog

All notable changes are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
- README rewrite (responsible-use section, accurate CLI defaults), contributing guide, security policy, code of
  conduct, issue/PR templates, CI (ruff + pytest), and `docs/project-state.md`.
- Test that editor content is embedded into the injected JavaScript as a safe string literal.
- `ruff` configuration and MIT license.

### Changed
- Editor content is now embedded into the page script with `json.dumps` instead of Python `repr`, which could
  emit escapes that are not valid JavaScript for some non-printable characters.
- `dcai notes --out` writes UTF-8 explicitly.
- Selector-module docstring now reflects what has been live-verified.

## [0.1.0]

Phase 1 vertical slice: CDP adapter, exercise normalisation, cache → LLM → submit → validate → repair pipeline
(coding, MCQ and video pages verified live), SQLite storage, and `start` / `resume` / `status` / `stats` / `notes`
/ `migrate` commands.
