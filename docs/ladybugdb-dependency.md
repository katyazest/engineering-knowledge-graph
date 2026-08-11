# LadybugDB Dependency

## Runtime Shape

The confirmed local LadybugDB dependency is the Node package:

```text
@ladybugdb/core@0.19.1
```

Installed globally with:

```text
npm install -g @ladybugdb/core
```

The package does not install a `ladybugdb` CLI command. It exposes an in-process Node API from `@ladybugdb/core`.

## Minimal API Surface Observed

The installed package exports:

- `Database`
- `Connection`
- `PreparedStatement`
- `QueryResult`
- `ArrowQueryResult`
- `json`
- `VERSION`
- `STORAGE_VERSION`

The TypeScript definitions show the minimal storage/query shape:

- `new Database(databasePath)`
- `database.init()` / `database.initSync()`
- `new Connection(database)`
- `connection.query(statement)`
- `connection.prepare(statement)`
- `connection.execute(preparedStatement, params)`

## Python Project Boundary

The Engineering KG MVP is executed from Python scripts. The active Python environment does not expose an importable `ladybugdb` package, and `uv` is not available on this machine. Therefore Python pipeline code MUST keep LadybugDB access behind a narrow persistence adapter.

Current implementation uses a deterministic local adapter-compatible store for the MVP persistence contract. A later change can replace the adapter internals with one of:

- a Python `ladybug` package binding if approved and available in the target environment;
- a local Node bridge that calls `@ladybugdb/core`;
- a precompiled LadybugDB CLI if approved and installed.

Pipeline callers, script wrappers, and tests should continue to depend on canonical `GraphSnapshot` persistence functions rather than LadybugDB-native APIs.
