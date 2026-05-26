# Agent Notes

This repository is a Python/PySide application for Binance futures trading,
collection, graphing, and simulation. Follow the existing style before adding
new abstractions.

## Working Memory

- Store any agent-authored memory, notes, plans, or durable handoff context
  under `.agents/memory`.
- Do not scatter agent memory into source, documentation, or module-level
  scratch files.
- Keep memory files concise and organized by subject, not by date. Update an
  existing subject file instead of creating endless dated memory files.

## Local Patterns

- Pursue the strongest type safety Python can reasonably provide. Prefer
  concrete annotations, typed records, `Protocol`, precise library types, and
  explicit runtime checks over broad `Any`, `object`, casts, or compatibility
  shims.
- Prefer `NamedTuple` over bare `tuple` for small typed records, keys, and
  cross-layer payloads when fields have meaning.
- Use `BaseModel` when parsing, validation, serialization, or mutability is
  needed.
- Do not introduce `@dataclass` for new domain records unless the local pattern
  has already changed.
- Prefer composition over inheritance. Do not introduce new subclasses for
  convenience wrappers; use `Protocol`, typed records, or an inner member owned
  by a wrapper class instead.
- Never use `__new__` in this codebase. Use normal constructors, composition,
  factory functions, or explicit call sites instead of allocation tricks.
- Do not use `typing.TYPE_CHECKING` except in `team.py`/`united.py`-style worker
  cycle-breaking modules. Prefer real imports, `Protocol`, stubs, or short
  `type:ignore` comments instead.
- Do not add `.pyi` stub files in this codebase. Keep typing in normal source
  files with concrete types, `Protocol`, or explicit short `type:ignore` comments.
- Never use checker-specific ignore directives or long ignore codes. When an
  ignore is truly necessary, use only the short `# type:ignore` form.
- Do not hide dynamic type conversion in generic helpers such as unwrap/cast
  functions returning `object`. Keep conversion boundaries local and explicit,
  with concrete branch types.
- Do not create DataFrame or Series abstraction layers. There must be no
  `tabular.py`-style compatibility module or similar wrapper. Adapt call sites
  to the actual Polars API directly.
- Import Polars classes and data types directly, for example
  `from polars import DataFrame, Series, Float64`.
- Import the Polars module as `pl` when calling functions or expression
  builders, for example `import polars as pl` and `pl.col("timestamp")`.
- Prefer importing from package surfaces such as `solie.utility` or
  `solie.logic` instead of lower implementation modules when the package
  surface exports the needed name.
- Keep runtime ownership on the `Window` object or worker instances attached to
  it. Avoid module-level global state for file handles, database connections,
  stores, caches, or managers.
- Existing workers generally hold `self._window = window` and derive worker
  paths from `window.datapath`.
- Prefer small focused utility modules and worker-owned state over broad shared
  services.
- Keep Markdown documentation in sync with code/API/storage changes. When
  dependencies, strategy APIs, storage formats, or user-visible behavior change,
  update the relevant `.md` docs in the same task.
- Backward compatibility with removed table storage is not required unless a
  task explicitly asks for it. Remove old migration and compatibility paths
  instead of preserving previous table-file storage behavior.
- After any code or documentation task, run the full project checks:
  `uv run ruff check` and `uv run ty check`. Fix issues before handing work
  back unless explicitly blocked.
- Do not run GUI entry points such as `uv run -m solie` or foreground usage
  launchers unless you are sure they will not block the agent loop. Prefer
  non-GUI checks, direct storage inspection, or an explicitly bounded/background
  launch.
- Terminal log output may be disabled in normal app runs. Do not rely on
  terminal-visible logs to diagnose runtime behavior; inspect saved logs under
  the datapath `+logs` directory or add visible/non-GUI verification.

## Table Storage Direction

The project is moving candle data, indicators, graph data, and simulation
records away from in-memory table-first storage. Persistent and core data paths
should use SQLite streams, Polars only for intentional bulk table work, and
typed records.

### Candle Data

- Use SQLite for candle data storage.
- Use `aiosqlite` for the async database layer.
- Store one SQLite file per symbol per UTC year, under a year-first directory,
  for example `team/candles/2026/BTCUSDT.sqlite`.
- Existing pre-year-split candle files can be ignored unless a task explicitly
  asks for migration.
- Every symbol-year database should have the same schema.
- Keep SQLite connection ownership in classes such as `CandleData`, with a
  window-owned `CandleDataStore` resolving symbol/year files. Prefer
  `NamedTuple` keys or records over bare `(symbol, year)` tuples.
- Use persistent write connections where useful, and dedicated read connections
  for long scans such as simulation.
- Do not use loose module-level/global SQLite handlers.
- Use WAL mode, a busy timeout, foreign keys, and explicit transactions.
- Candle timestamps are Unix milliseconds.
- The candle table shape should be:

```sql
CREATE TABLE candles (
    timestamp INTEGER PRIMARY KEY,
    open REAL NOT NULL,
    high REAL NOT NULL,
    low REAL NOT NULL,
    close REAL NOT NULL,
    volume REAL NOT NULL
);
```

- Never write candle rows with null OHLCV values.
- Missing candles should be absent rows, not rows with nulls.
- When a bulk in-memory representation is truly necessary, use Polars.

### Migrations

- Use `yoyo-migrations` for SQLite schema migrations.
- Keep migrations as ordered SQL files.
- Run migrations when opening/initializing each SQLite file.
- Treat migration state and checksums as part of the storage contract.

### Simulation

- Simulation should strongly prefer reading and writing directly from disk.
- For candle input, iterate per-symbol SQLite streams and row-match by timestamp.
- If a symbol is missing a timestamp, skip that symbol for the current cycle and
  let the stream catch up.
- Do not require loading all candle data into memory for simulation.
- Simulation output should also use SQLite rather than Parquet.
- Indicators do not need permanent persistence, but disk-backed temporary
  storage is preferred for memory control. Temporary indicator files may live in
  a temp directory and should be removed when the calculation finishes.
- Use Polars only when columnar in-memory work is genuinely necessary.

## Dependency Guidance

- `aiosqlite` is the preferred SQLite integration for new async database code.
- `yoyo-migrations` is the chosen migration dependency.
- Avoid adding ORM-style abstractions unless the storage layer clearly needs
  them.
