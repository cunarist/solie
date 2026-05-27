# Coding Style

- Pursue the strongest type safety Python can reasonably provide. Prefer
  concrete annotations, typed records, `Protocol`, precise library types, and
  explicit runtime checks over broad `Any`, `object`, casts, or compatibility
  shims.
- Prefer `NamedTuple` over bare `tuple` for small immutable payloads, keys, and
  records when fields have meaning. Do not introduce `@dataclass` for domain
  records.
- Prefer composition over inheritance. Do not subclass for convenience.
- Never use `__new__`.
- Do not use `typing.cast`.
- Do not use `typing.TYPE_CHECKING` except in worker team cycle-breaking code.
- Do not add `.pyi` files.
- Use only short `# type:ignore` comments when an ignore is unavoidable.
- Do not hide dynamic conversion in broad unwrap/cast helpers.
- Do not create DataFrame or Series abstraction layers. Use Polars directly.
- Import Polars classes and data types directly, such as
  `from polars import DataFrame, Series, Float64`.
- Import the Polars module as `pl` when calling functions or expression
  builders, such as `pl.col("timestamp")` and `pl.concat(frames)`.
- Prefer package-level Solie imports when the package surface exports the name.
- Do not use `asyncio.to_thread`; use `solie.common.spawn_blocking` for
  blocking work.
- `spawn` and `spawn_blocking` are explicit module-scope lifecycle exceptions:
  keep task retention and the process pool/sync manager behind `spawn`,
  `prepare_process_pool`, `get_sync_manager`, and `spawn_blocking` instead of
  wrapping them in context-manager scopes.
- Do not call `asyncio.create_task` outside `solie.common.concurrency`; use
  `spawn` everywhere else.
- Prefer `ExitStack` and `AsyncExitStack` for resource aggregation.
- Avoid `contextlib.suppress` and `contextlib.closing`; use explicit
  `try`/`except` and stack callbacks instead.
- Ruff ignores `SIM105` so it does not suggest `contextlib.suppress`.
- Overlay content uses class variables for static popup metadata such as
  `title` and `close_button`; live state like `widget`, `done_event`, and
  `result` stays instance-owned.
