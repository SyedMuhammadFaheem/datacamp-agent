# Security policy

## Supported versions

Only the latest commit on `main` is supported while the project is pre-1.0.

## Reporting a vulnerability

Please **do not open a public issue** for security problems. Use GitHub's private reporting:
[Report a vulnerability](https://github.com/SyedMuhammadFaheem/datacamp-agent/security/advisories/new).

Include what you found, how to reproduce it, and the impact. You should get an initial response within a few
days; this is a volunteer-maintained project, so fixes are best-effort.

## Things to know when running dcai

- **The Chrome debug port is powerful.** A browser started with `--remote-debugging-port` can be fully
  controlled by anything that can reach the port and (with `--remote-allow-origins`) pass the origin check.
  Use a **dedicated Chrome profile** (`--user-data-dir`) that is used only for this tool, don't browse other
  sites in it, and don't expose the port beyond localhost.
- **dcai never handles your DataCamp credentials.** It attaches to a browser you already logged in. It reads
  page text and clicks through the normal UI.
- **What leaves your machine.** Exercise instructions, starter code and (on failure) the error text are sent to
  the LLM provider you choose. Nothing else is sent, and no HTML or screenshots.
- **What is stored locally.** The SQLite database (`~/.local/share/dcai/dcai.db` by default) contains exercise
  text, generated solutions, attempts and token usage. It contains no credentials. Treat it as private.
- **API keys** (`ANTHROPIC_API_KEY`) are read from the environment only, never logged or written to the database.
