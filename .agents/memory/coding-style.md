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
