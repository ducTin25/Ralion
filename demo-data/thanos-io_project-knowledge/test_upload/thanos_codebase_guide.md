# Thanos Codebase Guide

- **Project:** Thanos (`thanos-io/thanos`)
- **Ralion category:** Codebase guide
- **Audience:** Engineers making their first code changes in Thanos
- **Source baseline:** `main` branch, reviewed 2026-08-24
- **Purpose:** Explain how to navigate the repository, trace a component from CLI entry point to implementation, and choose the right location for a change.

> This document intentionally does not replace `ARCHITECTURE.md` or component architecture documents. It is a source-code navigation map: **where code lives, how execution is wired, and where a developer should start reading for a task.**

## 1. The mental model

Thanos ships as a **single `thanos` binary with multiple subcommands**. The binary entry point registers component commands such as `sidecar`, `store`, `query`, `rule`, `compact`, `receive`, and `query-frontend`.

The most useful way to read the repository is therefore:

```text
CLI registration/configuration
        ↓
cmd/thanos/<component>.go
        ↓
component packages under pkg/
        ↓
shared APIs, storage, networking, telemetry, and utilities
        ↓
package tests and test/e2e scenarios
```

Do not begin by reading `pkg/` alphabetically. Start from the command or externally visible behavior you are trying to change and trace inward.

## 2. Main entry point

The process starts in:

```text
cmd/thanos/main.go
```

`main.go` creates the CLI application and registers the major commands:

- `registerSidecar`
- `registerStore`
- `registerQuery`
- `registerRule`
- `registerCompact`
- `registerTools`
- `registerReceive`
- `registerQueryFrontend`

It also owns process-wide concerns such as logging, tracing initialization, runtime memory-limit setup, signal handling, and command execution.

If you need to answer “how does `thanos <component>` start?”, begin with the matching file under `cmd/thanos`.

## 3. Key repository areas

This is a navigation-oriented map, not an exhaustive file listing.

```text
thanos/
├── cmd/thanos/              # CLI subcommands, flags, component wiring
├── pkg/                     # Reusable implementation packages
│   ├── api/                 # HTTP/API implementation pieces
│   ├── block/               # TSDB block metadata and block operations
│   ├── compact/             # Compaction/downsampling logic
│   ├── component/           # Canonical component identities/interfaces
│   ├── query/               # Query execution/fanout logic
│   ├── queryfrontend/       # Query Frontend-specific logic
│   ├── receive/             # Receive routing, TSDB, ingestion behavior
│   ├── rules/               # Thanos rule-related logic
│   ├── server/              # Shared HTTP/gRPC server infrastructure
│   ├── shipper/             # Uploading Prometheus/Thanos blocks
│   ├── store/               # StoreAPI, Store Gateway, caches, protobufs
│   ├── tenancy/             # Tenant propagation/enforcement helpers
│   ├── tls/                 # TLS configuration helpers
│   ├── tracing/             # Tracing integration
│   └── ui/                  # UI source/build output
├── internal/cortex/         # Selected Cortex code synchronized into Thanos
├── docs/                    # User and component documentation
├── examples/                # Example configs/assets/dashboards
├── mixin/                   # Monitoring mixin content
├── scripts/                 # Build, generation, quickstart, repo automation
├── test/e2e/                # Cross-component Docker E2E tests
├── Makefile                 # Supported developer/build/test workflows
├── go.mod / go.sum          # Go module dependency definition
└── CONTRIBUTING.md          # Contribution workflow and project conventions
```

## 4. Component registry

`pkg/component/component.go` defines canonical component identities and whether a component implements StoreAPI and/or produces metric blocks.

Important runtime components include:

| Component | Role in code navigation |
|---|---|
| `sidecar` | Prometheus-adjacent StoreAPI and block shipping. |
| `store` | Store Gateway over historical object-store blocks. |
| `query` | PromQL/Query API aggregation over StoreAPI backends. |
| `receive` | Remote-write ingestion, local TSDB, StoreAPI, block shipping. |
| `rule` | Rule evaluation, StoreAPI exposure, optional block shipping/remote write. |
| `compact` | Block compaction/downsampling and retention-related object-store work. |
| `query-frontend` | Request splitting, caching, retries, and downstream Query interaction. |

The same package also includes tool-oriented identities used by bucket operations, cleanup, rewrite, retention, downsample, replication, and related commands.

## 5. Where each major component starts

### Query

Start with:

```text
cmd/thanos/query.go
```

Then follow imports and constructors into:

```text
pkg/api/query/
pkg/query/
pkg/store/
pkg/dedup/
pkg/tenancy/
```

A useful conceptual path is:

```text
HTTP Query API
  → query API handler
  → PromQL/query engine
  → fanout to StoreAPI endpoints
  → merge/deduplicate series
  → response
```

If a bug concerns query flags, listener configuration, or component startup, stay in `cmd/thanos/query.go` first. If it concerns query execution or fanout semantics, move into `pkg/query`. If it concerns the StoreAPI request/response model, inspect `pkg/store` and its protobuf packages.

### Store Gateway

Start with:

```text
cmd/thanos/store.go
```

Core implementation areas include:

```text
pkg/store/
pkg/store/cache/
pkg/block/
pkg/block/indexheader/
```

The Store Gateway exposes StoreAPI over historical data in object storage. It maintains local cache/index-header state, but the object store remains the durable source for historical blocks.

For performance issues, inspect both query-facing StoreAPI logic and the cache/index-header path before assuming the CLI layer is responsible.

### Receive

Start with:

```text
cmd/thanos/receive.go
```

Then inspect:

```text
pkg/receive/
pkg/store/
pkg/shipper/
pkg/tenancy/
```

Receive combines several concerns: remote-write ingestion, tenant/hashring routing, local TSDB state, StoreAPI serving, replication/forwarding, and optional object-store shipping. Keep these boundaries explicit when changing behavior.

For ingestion correctness, begin in `pkg/receive`; for server/flag wiring, begin in `cmd/thanos/receive.go`.

### Rule

Start with:

```text
cmd/thanos/rule.go
```

Then inspect:

```text
pkg/rules/
pkg/query/
pkg/store/
pkg/shipper/
```

The Rule component evaluates Prometheus-compatible rules against configured Query APIs. It can expose generated data through StoreAPI and can ship generated TSDB blocks depending on mode/configuration.

When changing rule syntax/validation, also inspect the `tools rules-check` path in `cmd/thanos/tools.go`.

### Compact

Start with:

```text
cmd/thanos/compact.go
```

Then inspect:

```text
pkg/compact/
pkg/compact/downsample/
pkg/block/
```

Compactor code is security- and data-integrity-sensitive because it transforms object-store blocks and can delete data. Changes here should be accompanied by focused tests and, for cross-component behavior, E2E coverage.

### Sidecar

Start with:

```text
cmd/thanos/sidecar.go
```

The main implementation path connects Prometheus-facing behavior, StoreAPI exposure, and optional block shipping. Common packages to encounter include `pkg/promclient`, `pkg/store`, and `pkg/shipper`.

When investigating Sidecar issues, first determine whether the failing path is:

- Prometheus discovery/metadata interaction;
- StoreAPI serving;
- block upload/shipping;
- configuration/reload behavior.

That prevents mixing unrelated concerns in one fix.

### Query Frontend

Start with:

```text
cmd/thanos/query_frontend.go
```

Then inspect:

```text
pkg/queryfrontend/
internal/cortex/frontend/
internal/cortex/querier/queryrange/
pkg/tenancy/
pkg/server/http/
```

The Query Frontend contains request splitting, caching, retries, query limits, downstream transport configuration, tenant propagation, and request instrumentation.

`internal/cortex` is special: the Makefile contains a synchronization target that copies selected Cortex packages into this directory. Do not treat it like an ordinary Thanos-owned package and casually refactor it without understanding the sync mechanism and why the local copy exists.

## 6. Shared cross-cutting packages

You will see these packages imported by multiple components:

### `pkg/component`

Defines component identities and capabilities such as StoreAPI implementation or block production. Use it instead of inventing ad-hoc component name strings when an existing canonical identity applies.

### `pkg/server/http` and `pkg/server/grpc`

Shared server lifecycle/listener infrastructure. Changes here can affect several components at once, so validate more than one caller.

### `pkg/tls`

Shared TLS configuration. Treat changes as cross-component security changes.

### `pkg/tenancy`

Tenant identifiers and propagation/enforcement helpers. Changes can alter isolation semantics; trace headers end to end before modifying.

### `pkg/tracing`, `pkg/logging`, `pkg/extprom`

Observability and instrumentation infrastructure. Avoid putting metric payload data or secret values into logs/traces/labels.

### `pkg/extkingpin`

CLI/config helper layer around Kingpin. Prefer existing configuration abstractions over adding component-specific parsing patterns without need.

### `pkg/runutil` and server/prober helpers

Common lifecycle and operational utilities. Because they are widely reused, a small change can have broad runtime effects.

## 7. API and protobuf code

StoreAPI is central to the way Thanos components interoperate. You will encounter generated protobuf code under StoreAPI-related packages such as:

```text
pkg/store/storepb/
```

Other API-specific generated/runtime packages exist under `pkg/api` and component-specific areas.

When a protocol definition changes:

1. find the source `.proto` definition;
2. change the source definition rather than generated Go output;
3. run the repository generation target:

```bash
make proto
```

4. review the generated diff carefully;
5. run tests for every component that consumes the changed API.

Protocol changes are cross-component changes even when the source edit is small.

## 8. UI code

The React application source is under:

```text
pkg/ui/react-app/
```

Generated/built assets are emitted under:

```text
pkg/ui/static/react/
```

Use repository targets such as:

```bash
make react-app
make react-app-lint
make react-app-test
```

Do not debug a React source issue by editing generated static output directly.

## 9. Tests

### Package tests

Most Go behavior is tested beside implementation code using normal `*_test.go` files. During development, run the narrowest package test that exercises your change.

Examples:

```bash
go test ./pkg/query/...
go test ./pkg/store/...
go test ./pkg/receive/...
```

### Repository test targets

Use the repository-supported targets for broader confidence:

```bash
make test-local-short
make test-local
make test
```

`make test-local` is usually the best broad local check for a contributor without cloud object-store credentials.

### End-to-end tests

Cross-component scenarios live in:

```text
test/e2e/
```

Use E2E when the change depends on real component interaction, process lifecycle, networking, or object-store behavior that package tests cannot represent.

```bash
make test-e2e-local
```

or, when real provider paths are intentionally required:

```bash
make test-e2e
```

## 10. Documentation and examples

User-facing component documentation is primarily under:

```text
docs/
docs/components/
```

Examples and dashboards live under:

```text
examples/
```

Monitoring mixin content lives under:

```text
mixin/
```

The Makefile formats and validates Markdown across root docs, `docs`, `examples`, and mixin documentation. If a code change alters a flag or user-facing behavior, search the matching component documentation before considering the change complete.

## 11. How to trace a behavior through the code

Use this sequence rather than global searching at random.

### Step 1 — Start from the user-visible command

Example: a Query flag behaves incorrectly.

Open:

```text
cmd/thanos/query.go
```

Find the flag registration and the field it writes into.

### Step 2 — Find component setup/run wiring

Follow the config field into the setup function and server/constructor calls.

Questions to answer:

- Is the value only parsed here?
- Is it transformed before entering `pkg/`?
- Does the command layer own the behavior or only wiring?

### Step 3 — Follow into `pkg/`

Find the package that owns the domain behavior. This is usually where reusable logic and unit tests should live.

### Step 4 — Find existing tests before writing code

Search for the symbol, config field, error string, or analogous behavior in `*_test.go` and `test/e2e`.

### Step 5 — Search documentation

Search `docs/components`, `docs`, and examples for the flag/API behavior. A behavior change without matching docs often creates future onboarding confusion.

## 12. Where should a new change go?

Use this rule of thumb:

| Change | Preferred starting location |
|---|---|
| Add/change a CLI flag | `cmd/thanos/<component>.go` |
| Reusable domain logic | Relevant `pkg/<area>` package |
| Query execution/fanout | `pkg/query` |
| StoreAPI/storage read path | `pkg/store` |
| Block metadata/transforms | `pkg/block` / `pkg/compact` |
| Receive ingestion/routing | `pkg/receive` |
| Rule behavior | `pkg/rules` plus Rule wiring |
| Common HTTP/gRPC lifecycle | `pkg/server` |
| TLS | `pkg/tls` |
| Tenancy | `pkg/tenancy` |
| Query Frontend behavior | `pkg/queryfrontend` and, only when necessary, `internal/cortex` |
| Protocol/API schema | Source proto/API definitions + generation target |
| React UI | `pkg/ui/react-app` |
| Component docs | `docs/components` |
| Cross-component integration test | `test/e2e` |

Avoid placing substantive domain logic in `cmd/thanos` merely because the feature begins at a CLI flag. The command layer should primarily configure and wire components; reusable behavior belongs in the package that owns it.

## 13. Files that deserve extra caution

### `internal/cortex`

This directory is synchronized from selected Cortex packages by a dedicated Makefile target. Understand the sync process before editing. A local patch can be difficult to maintain if it diverges from the upstream-sourced code without a deliberate reason.

### Generated protobuf/API files

Change the source definition and regenerate. Do not hand-maintain generated output.

### `pkg/server`, `pkg/tls`, `pkg/tenancy`

These are cross-cutting. A change that fixes one component can regress several others if tested only through a single call site.

### Compactor/object-store deletion paths

These can affect durable data. Prefer narrow changes, explicit invariants, and strong tests.

## 14. Contribution architecture rules visible in the repository

The upstream contribution guide describes a simple design philosophy:

- each subcommand should do one thing well;
- components should work together through clear interfaces;
- system and implementation complexity should be kept low;
- large new features/components should begin with a design proposal;
- component naming should remain consistent between command/code form (`query`, `store`, `compact`, `rule`, `query-frontend`) and actor/documentation form (Querier, Store Gateway, Compactor, Ruler, Query Frontend).

Apply those principles when deciding whether to add a new package, cross-component abstraction, or special-case configuration path.

## 15. First-hour navigation checklist

When joining the project, a useful first hour is:

- [ ] Read the root `README.md` and `CONTRIBUTING.md`.
- [ ] Read the project's existing architecture documents.
- [ ] Run `make help`.
- [ ] Open `cmd/thanos/main.go` and identify the registered subcommands.
- [ ] Open `pkg/component/component.go` and understand the component identities.
- [ ] Pick one component relevant to your task and trace `cmd/thanos/<component>.go` into its `pkg/` implementation.
- [ ] Find one unit test for that implementation.
- [ ] Find one E2E test involving the component.
- [ ] Find its user-facing document under `docs/components`.
- [ ] Build and run a focused test before changing code.

After this, you should be able to answer: **“If I need to change this behavior, which package owns it, which components can be affected, and how will I prove the change is safe?”**

## 16. Source references

This guide is derived from current upstream sources, principally:

- Main CLI entry point: https://github.com/thanos-io/thanos/blob/main/cmd/thanos/main.go
- Component registry: https://github.com/thanos-io/thanos/blob/main/pkg/component/component.go
- Query command: https://github.com/thanos-io/thanos/blob/main/cmd/thanos/query.go
- Store command: https://github.com/thanos-io/thanos/blob/main/cmd/thanos/store.go
- Receive command: https://github.com/thanos-io/thanos/blob/main/cmd/thanos/receive.go
- Rule command: https://github.com/thanos-io/thanos/blob/main/cmd/thanos/rule.go
- Compact command: https://github.com/thanos-io/thanos/blob/main/cmd/thanos/compact.go
- Query Frontend command: https://github.com/thanos-io/thanos/blob/main/cmd/thanos/query_frontend.go
- Tools command: https://github.com/thanos-io/thanos/blob/main/cmd/thanos/tools.go
- Makefile: https://github.com/thanos-io/thanos/blob/main/Makefile
- Contribution guide: https://github.com/thanos-io/thanos/blob/main/CONTRIBUTING.md
- Component docs: https://github.com/thanos-io/thanos/tree/main/docs/components

Use the source files for the exact revision you are debugging. Thanos evolves quickly enough that package wiring, versions, flags, and generated code can move over time.
