# Runtime And Checks

- Always run `uv run ruff check` and `uv run ty check` after code or docs work.
- Do not run GUI entry points such as `uv run -m solie` or foreground usage
  launchers unless they are bounded or cannot block the agent loop.
- Terminal log output may be disabled in app runs. Inspect saved logs or use
  non-GUI verification instead of relying on terminal-visible logs.
- Startup should not block indefinitely on internet/CoinGecko access. Coin
  metadata and image fetch failures should fall back to empty metadata or the
  bundled blank coin icon.
