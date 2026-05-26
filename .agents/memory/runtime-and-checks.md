# Runtime And Checks

- Always run `uv run ruff check` and `uv run ty check` after code or docs work.
- Do not run GUI entry points such as `uv run -m solie` or foreground usage
  launchers unless they are bounded or cannot block the agent loop.
- Terminal log output may be disabled in app runs. Inspect saved logs or use
  non-GUI verification instead of relying on terminal-visible logs.

