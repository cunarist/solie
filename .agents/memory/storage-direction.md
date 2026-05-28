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
- Historical Binance download fill should not build Polars candle frames before
  persistence. It streams ZIP CSV rows into `CandleRowWriter`, which writes
  final candle rows directly to per-symbol/year SQLite files; rare unsorted CSVs
  fall back to temporary SQLite sorting.
- Simulation output should also use SQLite rather than Parquet.
- Indicator persistence is optional, but tempdir-backed disk storage is
  preferred when it lowers memory use.
