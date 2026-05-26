# Storage Direction

- Candle data uses per-symbol, per-UTC-year SQLite files through `aiosqlite`.
- Use the fresh year-first layout `team/candles/{year}/{symbol}.sqlite`.
- Existing pre-year-split files can be ignored unless migration is explicitly
  requested.
- SQLite migrations use `yoyo-migrations` and ordered SQL files.
- Candle timestamps are Unix milliseconds.
- Never write candle rows with null OHLCV values. Missing candles are absent
  rows.
- Use Polars only for intentional in-memory columnar work.
- Simulation output should also use SQLite rather than Parquet.
- Indicator persistence is optional, but tempdir-backed disk storage is
  preferred when it lowers memory use.
